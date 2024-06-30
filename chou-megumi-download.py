import os
import sys
import re
import shutil
import paramiko
from pathlib import Path, PurePosixPath
import subprocess
import logging
from tqdm import tqdm
import concurrent.futures
import threading
import math
import tempfile
import atexit
from functools import lru_cache

class ProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)

class SingleInstanceChecker:
    def __init__(self):
        self.lockfile = Path(tempfile.gettempdir()) / 'megumi_download.lock'
        self.lock_handle = None

    def try_lock(self):
        try:
            if sys.platform == 'win32':
                import msvcrt
                self.lock_handle = open(self.lockfile, 'w')
                msvcrt.locking(self.lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                self.lock_handle = open(self.lockfile, 'w')
                fcntl.lockf(self.lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            atexit.register(self.unlock)
            return True
        except (IOError, OSError):
            return False

    def unlock(self):
        if self.lock_handle is not None:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(self.lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.lockf(self.lock_handle, fcntl.LOCK_UN)
            self.lock_handle.close()
            try:
                self.lockfile.unlink()
            except OSError:
                pass

class MegumiDownload:
    def __init__(self):
        self.script_dir = Path(__file__).parent.resolve()
        self.setup_logging()
        self.config = self.load_config()
        self.groups = self.load_groups()
        self.series_list = self.load_series_list()
        self.temp_dir = Path(self.config.get('LOCALTEMP', self.script_dir / 'temp'))
        self.lock = threading.Lock()
        self.chunks = int(self.config.get('CHUNKS', '3'))
        self.use_chunks = self.config.get('USE_CHUNKS', 'ON').upper() == 'ON'
        self.mkvextract_path = self.find_executable('mkvextract')
        self.mkvmerge_path = self.find_executable('mkvmerge')

    @lru_cache(maxsize=None)
    def find_executable(self, name):
        system_path = shutil.which(name)
        if system_path:
            return system_path
        local_path = self.script_dir / (name + ('.exe' if sys.platform == 'win32' else ''))
        return str(local_path) if local_path.exists() else None

    def setup_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    def load_file_with_encodings(self, file_path, process_func):
        encodings = ['utf-8', 'utf-16', 'cp932', 'iso-8859-1']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return process_func(f)
            except UnicodeDecodeError:
                continue
        logging.error(f"Unable to read file {file_path} with any of the attempted encodings: {encodings}")
        sys.exit(1)

    def load_config(self):
        config_path = self.script_dir / 'config.megumi'
        if not config_path.exists():
            logging.error(f"Config file not found: {config_path}")
            sys.exit(1)
        return self.load_file_with_encodings(config_path, lambda f: dict(line.strip().split('=', 1) for line in f if '=' in line))

    def load_groups(self):
        groups_path = self.script_dir / 'groups.megumi'
        if not groups_path.exists():
            logging.error(f"Groups file not found: {groups_path}")
            sys.exit(1)
        return self.load_file_with_encodings(groups_path, lambda f: [line.strip() for line in f if line.strip()])

    def load_series_list(self):
        series_list_path = self.script_dir / 'serieslist.megumi'
        if not series_list_path.exists():
            logging.error(f"Series list file not found: {series_list_path}")
            sys.exit(1)
        return self.load_file_with_encodings(series_list_path, lambda f: [
            dict(zip(['file_name', 'folder_name', 'season_number'], line.strip().split('|')))
            for line in f if '|' in line
        ])

    def download_chunk(self, ssh, remote_path, file, start, end, chunk_file, pbar):
        sftp = ssh.open_sftp()
        try:
            with sftp.open(str(PurePosixPath(remote_path) / file), 'rb') as remote_file:
                remote_file.seek(start)
                bytes_to_read = end - start
                with open(chunk_file, 'wb') as f:
                    while bytes_to_read > 0:
                        data = remote_file.read(min(bytes_to_read, 1048576))
                        if not data:
                            break
                        f.write(data)
                        bytes_to_read -= len(data)
                        pbar.update(len(data))
        finally:
            sftp.close()

    def download_file(self, ssh, remote_path, file, overall_pbar):
        local_path = self.temp_dir / file
        remote_file_path = PurePosixPath(remote_path) / file
        if local_path.exists():
            local_path.unlink()
        logging.info(f"Attempting to download: {file}")

        with ssh.open_sftp() as sftp:
            file_size = sftp.stat(str(remote_file_path)).st_size

        if self.use_chunks and file_size > 1024 * 1024:
            chunk_size = math.ceil(file_size / self.chunks)
            with ProgressBar(total=file_size, desc=file, unit='B', unit_scale=True, unit_divisor=1024, miniters=1) as pbar:
                chunk_files = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.chunks) as executor:
                    futures = [
                        executor.submit(self.download_chunk, ssh, remote_path, file, 
                                        i * chunk_size, min((i + 1) * chunk_size, file_size), 
                                        local_path.with_suffix(f'.part{i}'), pbar)
                        for i in range(self.chunks)
                    ]
                    concurrent.futures.wait(futures)
                    chunk_files = [future.result() for future in futures]

            with open(local_path, 'wb') as outfile:
                for chunk_file in chunk_files:
                    with open(chunk_file, 'rb') as infile:
                        shutil.copyfileobj(infile, outfile)
                    Path(chunk_file).unlink()
        else:
            with ssh.open_sftp() as sftp, ProgressBar(total=file_size, desc=file, unit='B', unit_scale=True, unit_divisor=1024, miniters=1) as pbar:
                sftp.get(str(remote_file_path), str(local_path), callback=pbar.update_to)

        if local_path.stat().st_size > 0:
            with self.lock:
                logging.info(f"Successfully downloaded: {file}")
            with ssh.open_sftp() as sftp:
                sftp.remove(str(remote_file_path))
                with self.lock:
                    logging.info(f"Removed remote file: {file}")
            self.process_subtitles(self.temp_dir, local_path)
        else:
            with self.lock:
                logging.error(f"Downloaded file {file} is empty. Deleting local copy.")
            local_path.unlink()

        overall_pbar.update(1)

    def download_files(self):
        if self.config.get('MOVELOCAL', 'OFF').upper() == 'OFF':
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                ssh.connect(self.config['HOST'], username=self.config['USER'], password=self.config['PASSWORD'])

                remote_path = self.config['REMOTEPATCH']
                logging.info(f"Attempting to list directory: {remote_path}")

                with ssh.open_sftp() as sftp:
                    remote_files = sftp.listdir(remote_path)
                    logging.info(f"Successfully listed directory: {remote_path}")

                self.temp_dir.mkdir(parents=True, exist_ok=True)
                logging.info(f"Files will be temporarily downloaded to: {self.temp_dir}")

                for temp_file in self.temp_dir.glob('*.mkv'):
                    if temp_file.name in remote_files:
                        temp_file.unlink()
                        logging.info(f"Removed existing temporary file: {temp_file.name}")

                files_to_download = [
                    file for file in remote_files 
                    if file.lower().endswith('.mkv') and 
                    any(f"[{group}]" in file or f"【{group}】" in file for group in self.groups)
                ]
            
                logging.info(f"Found {len(files_to_download)} MKV files to download")
			
                with tqdm(total=len(files_to_download), desc="Overall Progress", unit="file") as overall_pbar:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        futures = [executor.submit(self.download_file, ssh, remote_path, file, overall_pbar) for file in files_to_download]
                        concurrent.futures.wait(futures)

                ssh.close()
            except Exception as e:
                logging.error(f"Error during SFTP operations: {e}")
                sys.exit(1)
        else:
            logging.info("MOVELOCAL option is ON. Processing local MKV files.")
            self.temp_dir = Path(self.config['LOCALTEMP'])
            if not self.temp_dir.exists():
                logging.error(f"Local temp directory not found: {self.temp_dir}")
                sys.exit(1)
            
            files_to_process = list(self.temp_dir.glob('*.mkv'))
            logging.info(f"Found {len(files_to_process)} MKV files to process in {self.temp_dir}")

        return self.temp_dir

    def move_files(self, temp_dir):
        for file in temp_dir.glob('*.mkv'):
            if file.stat().st_size == 0:
                logging.warning(f"Skipping empty MKV file: {file.name}")
                continue
            
            matched_series = next((series for series in self.series_list if series['file_name'] in file.name), None)
            
            if matched_series:
                ep_match = re.search(r'\s(\d{2})(\s(\(.*?\)|\[.*?\])).*(\..*)|\s(\d{2})(\..*)', file.name)
                if ep_match:
                    ep_num = ep_match.group(1) or ep_match.group(5)
                    ext = ep_match.group(4) or ep_match.group(6)
                    
                    dest_dir = Path(self.config['LOCALPATCH']) / matched_series['folder_name'] / f"Season {matched_series['season_number']}"
                    dest_dir.mkdir(parents=True, exist_ok=True)

                    new_name = f"S{matched_series['season_number'].zfill(2)}E{ep_num}{ext}" if self.config.get('RENAME', 'ON').upper() == 'ON' else file.name

                    dest_file = dest_dir / new_name
                    if dest_file.exists():
                        logging.warning(f"Destination file already exists. Overwriting: {dest_file}")
                        dest_file.unlink()

                    shutil.move(str(file), str(dest_file))
                    logging.info(f"Moved file: {file.name} to {dest_file}")

                    if self.config.get('SAVEINFO', 'OFF').upper() == 'ON':
                        with open(dest_dir / "info.txt", "a") as info_file:
                            info_file.write(f"{file.name} ({new_name})\n")
                        logging.info(f"Saved file info to: {dest_dir / 'info.txt'}")

                    self.process_subtitles(dest_dir, dest_file)
                else:
                    logging.warning(f"Could not extract episode number from MKV filename: {file.name}")
            else:
                logging.warning(f"No matching series found for MKV file: {file.name}")

    def process_subtitles(self, dest_dir, file_path):
        replace_file = dest_dir / "replace.txt"
        if replace_file.exists():
            logging.info(f"Processing subtitles for: {file_path.name}")
            subtitle_path = file_path.with_suffix('.ass')
            try:
                subprocess.run([self.mkvextract_path, str(file_path), 'tracks', f"2:{subtitle_path}"], check=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"Error extracting subtitles: {e}")
                return

            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()

            content = self.apply_standard_replacements(content)

            with open(replace_file, 'r', encoding='utf-8') as f:
                replacements = dict(line.strip().split('|') for line in f if '|' in line)

            for old, new in replacements.items():
                content = re.sub(r'\b' + re.escape(old) + r'\b', new, content)

            with open(subtitle_path, 'w', encoding='utf-8') as f:
                f.write(content)

            output_file = file_path.with_name(file_path.stem + "_remuxed" + file_path.suffix)
            try:
                subprocess.run([self.mkvmerge_path, '-o', str(output_file), '--no-subtitles', str(file_path), 
                                '--language', '0:eng', '--track-name', '0:MegumiDownloadFixed', str(subtitle_path)], check=True)
                
                file_path.unlink()
                output_file.rename(file_path)
                subtitle_path.unlink()
                logging.info(f"Processed subtitles for: {file_path.name}")
            except subprocess.CalledProcessError as e:
                logging.error(f"Error remuxing file: {e}")
                return
        else:
            logging.info(f"No replace.txt found for {file_path.name}. Skipping subtitle processing.")

    @staticmethod
    def apply_standard_replacements(text):
        replacements = [
            ("Wh-wh", "W-Wh"), ("Wh-Wh", "W-Wh"), ("Th-th", "T-Th"), ("Th-Th", "T-Th"),
            ("A-a", "A-A"), ("B-b", "B-B"), ("C-c", "C-C"), ("D-d", "D-D"), ("E-e", "E-E"),
            ("F-f", "F-F"), ("G-g", "G-G"), ("H-h", "H-H"), ("I-i", "I-I"), ("J-j", "J-J"),
            ("K-k", "K-K"), ("L-l", "L-L"), ("M-m", "M-M"), ("N-n", "N-N"), ("O-o", "O-O"),
            ("P-p", "P-P"), ("Q-q", "Q-Q"), ("R-r", "R-R"), ("S-s", "S-S"), ("T-t", "T-T"),
            ("U-u", "U-U"), ("W-w", "W-W"), ("Y-y", "Y-Y"), ("Z-z", "Z-Z"),
            ("\\N", "\\N "), ("\\h", "\\h "),
        ]
        for old, new in replacements:
            text = text.replace(old, new)
        return text

    def run(self):
        logging.info("Starting Megumi Download")
        temp_dir = self.download_files()
        self.move_files(temp_dir)
        logging.info("Megumi Download completed")

if __name__ == "__main__":
    instance_checker = SingleInstanceChecker()
    
    if instance_checker.try_lock():
        try:
            downloader = MegumiDownload()
            downloader.run()
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
        finally:
            instance_checker.unlock()
    else:
        print("Another instance of Megumi Download is already running. Exiting.")
        sys.exit(1)
