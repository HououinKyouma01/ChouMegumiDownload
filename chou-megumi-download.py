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

class ProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)

class SingleInstanceChecker:
    def __init__(self):
        self.lockfile = os.path.join(tempfile.gettempdir(), 'megumi_download.lock')
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
                os.remove(self.lockfile)
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

    def find_executable(self, name):
        # First, check if the executable is in the system PATH
        system_path = shutil.which(name)
        if system_path:
            return system_path

        # If not found in PATH, check in the script directory
        local_path = self.script_dir / name
        if sys.platform == 'win32':
            local_path = local_path.with_suffix('.exe')

        if local_path.exists():
            return str(local_path)

    def setup_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    def load_config(self):
        config_path = self.script_dir / 'config.megumi'
        if not config_path.exists():
            logging.error(f"Config file not found: {config_path}")
            sys.exit(1)
        
        encodings = ['utf-8', 'utf-16', 'cp932', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(config_path, 'r', encoding=encoding) as f:
                    config = {}
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            config[key.strip()] = value.strip()
                    return config
            except UnicodeDecodeError:
                continue
        
        logging.error(f"Unable to read config file with any of the attempted encodings: {encodings}")
        sys.exit(1)

    def load_groups(self):
        groups_path = self.script_dir / 'groups.megumi'
        if not groups_path.exists():
            logging.error(f"Groups file not found: {groups_path}")
            sys.exit(1)
        
        encodings = ['utf-8', 'utf-16', 'cp932', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(groups_path, 'r', encoding=encoding) as f:
                    return [line.strip() for line in f if line.strip()]
            except UnicodeDecodeError:
                continue
        
        logging.error(f"Unable to read groups file with any of the attempted encodings: {encodings}")
        sys.exit(1)

    def load_series_list(self):
        series_list_path = self.script_dir / 'serieslist.megumi'
        if not series_list_path.exists():
            logging.error(f"Series list file not found: {series_list_path}")
            sys.exit(1)
        
        encodings = ['utf-8', 'utf-16', 'cp932', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(series_list_path, 'r', encoding=encoding) as f:
                    series_list = []
                    for line in f:
                        if '|' in line:
                            file_name, folder_name, season_number = line.strip().split('|')
                            series_list.append({
                                'file_name': file_name,
                                'folder_name': folder_name,
                                'season_number': season_number
                            })
                    return series_list
            except UnicodeDecodeError:
                continue
        
        logging.error(f"Unable to read series list file with any of the attempted encodings: {encodings}")
        sys.exit(1)

    def download_chunk(self, ssh, remote_path, file, start, end, chunk_file, pbar):
        sftp = ssh.open_sftp()
        try:
            with sftp.open(str(PurePosixPath(remote_path) / file), 'rb') as remote_file:
                remote_file.seek(start)
                bytes_to_read = end - start
                with open(chunk_file, 'wb') as f:
                    while bytes_to_read > 0:
                        data = remote_file.read(min(bytes_to_read, 1048576))  # Read in 8KB chunks
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

        sftp = ssh.open_sftp()
        try:
            file_size = sftp.stat(str(remote_file_path)).st_size
        finally:
            sftp.close()

        if self.use_chunks and file_size > 1024 * 1024:  # Only use chunks for files larger than 1MB
            chunk_size = math.ceil(file_size / self.chunks)
            with ProgressBar(total=file_size, desc=file, unit='B', unit_scale=True, unit_divisor=1024, miniters=1) as pbar:
                chunk_files = []
                futures = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.chunks) as executor:
                    for i in range(self.chunks):
                        start = i * chunk_size
                        end = min((i + 1) * chunk_size, file_size)
                        chunk_file = local_path.with_suffix(f'.part{i}')
                        chunk_files.append(chunk_file)
                        futures.append(executor.submit(self.download_chunk, ssh, remote_path, file, start, end, chunk_file, pbar))
                    concurrent.futures.wait(futures)

            # Combine chunks
            with open(local_path, 'wb') as outfile:
                for chunk_file in chunk_files:
                    with open(chunk_file, 'rb') as infile:
                        shutil.copyfileobj(infile, outfile)
                    chunk_file.unlink()
        else:
            sftp = ssh.open_sftp()
            try:
                with ProgressBar(total=file_size, desc=file, unit='B', unit_scale=True, unit_divisor=1024, miniters=1) as pbar:
                    sftp.get(str(remote_file_path), str(local_path), callback=pbar.update_to)
            finally:
                sftp.close()

        if local_path.stat().st_size > 0:
            with self.lock:
                logging.info(f"Successfully downloaded: {file}")
            sftp = ssh.open_sftp()
            try:
                sftp.remove(str(remote_file_path))
                with self.lock:
                    logging.info(f"Removed remote file: {file}")
            finally:
                sftp.close()
        else:
            with self.lock:
                logging.error(f"Downloaded file {file} is empty. Deleting local copy.")
            local_path.unlink()

        overall_pbar.update(1)

    def download_files(self):
        if self.config.get('MOVELOCAL', 'OFF') == 'OFF':
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                ssh.connect(self.config['HOST'], username=self.config['USER'], password=self.config['PASSWORD'])

                remote_path = self.config['REMOTEPATCH']
                logging.info(f"Attempting to list directory: {remote_path}")

                sftp = ssh.open_sftp()
                try:
                    remote_files = sftp.listdir(remote_path)
                    logging.info(f"Successfully listed directory: {remote_path}")
                except IOError as e:
                    logging.error(f"Failed to list directory {remote_path}: {e}")
                    sys.exit(1)
                finally:
                    sftp.close()

                self.temp_dir.mkdir(parents=True, exist_ok=True)
                logging.info(f"Files will be temporarily downloaded to: {self.temp_dir}")

                # Remove existing temporary files
                for temp_file in self.temp_dir.iterdir():
                    if temp_file.name in remote_files:
                        temp_file.unlink()
                        logging.info(f"Removed existing temporary file: {temp_file.name}")

                files_to_download = [file for file in remote_files if any(f"[{group}]" in file or f"【{group}】" in file for group in self.groups)]
                
                with tqdm(total=len(files_to_download), desc="Overall Progress", unit="file") as overall_pbar:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        futures = [executor.submit(self.download_file, ssh, remote_path, file, overall_pbar) for file in files_to_download]
                        concurrent.futures.wait(futures)

                ssh.close()
            except Exception as e:
                logging.error(f"Error during SFTP operations: {e}")
                sys.exit(1)
        else:
            if not self.temp_dir.exists():
                logging.error(f"Local temp directory not found: {self.temp_dir}")
                sys.exit(1)

        return self.temp_dir

    def move_files(self, temp_dir):
        for file in temp_dir.iterdir():
            if not file.is_file():
                continue
            if file.stat().st_size == 0:
                logging.warning(f"Skipping empty file: {file.name}")
                continue
            for series in self.series_list:
                if series['file_name'] in file.name:
                    ep_match = re.search(r'\s(\d{2})(\s(\(.*?\)|\[.*?\])).*(\..*)|\s(\d{2})(\..*)', file.name)
                    if ep_match:
                        ep_num = ep_match.group(1) or ep_match.group(5)
                        ext = ep_match.group(4) or ep_match.group(6)
                        
                        dest_dir = Path(self.config['LOCALPATCH']) / series['folder_name'] / f"Season {series['season_number']}"
                        dest_dir.mkdir(parents=True, exist_ok=True)

                        if self.config.get('RENAME', 'ON') == 'ON':
                            new_name = f"S{series['season_number'].zfill(2)}E{ep_num}{ext}"
                        else:
                            new_name = file.name

                        dest_file = dest_dir / new_name
                        if dest_file.exists():
                            dest_file.unlink()

                        shutil.move(str(file), str(dest_file))
                        logging.info(f"Moved file: {file.name} to {dest_file}")

                        if self.config.get('SAVEINFO', 'OFF') == 'ON':
                            info_file_path = dest_dir / "info.txt"
                            with open(info_file_path, "a") as info_file:
                                info_file.write(f"{file.name} ({new_name})\n")

                        self.process_subtitles(dest_dir, dest_file)
                        break  # Stop searching for matching series after finding one

    def process_subtitles(self, dest_dir, file_path):
        replace_file = dest_dir / "replace.txt"
        if replace_file.exists():
            # Extract subtitles
            subtitle_path = file_path.with_suffix('.ass')
            try:
                subprocess.run(['mkvextract', str(file_path), 'tracks', f"2:{subtitle_path}"], check=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"Error extracting subtitles: {e}")
                return

            # Process subtitles
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Apply standard replacements
            content = self.apply_standard_replacements(content)

            # Apply custom replacements from replace.txt
            with open(replace_file, 'r', encoding='utf-8') as f:
                replacements = dict(line.strip().split('|') for line in f if '|' in line)

            for old, new in replacements.items():
                content = re.sub(r'\b' + re.escape(old) + r'\b', new, content)

            with open(subtitle_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # Remux file
            output_file = file_path.with_name(file_path.stem + "_remuxed" + file_path.suffix)
            try:
                subprocess.run(['mkvmerge', '-o', str(output_file), '--no-subtitles', str(file_path), 
                                '--language', '0:eng', '--track-name', '0:MegumiDownloadFixed', str(subtitle_path)], check=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"Error remuxing file: {e}")
                return

            # Replace original file with remuxed file
            file_path.unlink()
            output_file.rename(file_path)
            subtitle_path.unlink()
            logging.info(f"Processed subtitles for: {file_path.name}")

    def apply_standard_replacements(self, text):
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
        downloader = MegumiDownload()
        downloader.run()
    else:
        print("Another instance of Megumi Download is already running. Exiting.")
        sys.exit(1)