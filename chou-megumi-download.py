import sys
import re
import shutil
import paramiko
import logging
from pathlib import Path, PurePosixPath
import subprocess
import concurrent.futures
import threading
import math
import tempfile
import atexit
from functools import lru_cache
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
import time
from rich.text import Text

console = Console()

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
            try:
                if sys.platform == 'win32':
                    import msvcrt
                    msvcrt.locking(self.lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.lockf(self.lock_handle, fcntl.LOCK_UN)
            except ValueError:
                pass
            finally:
                try:
                    self.lock_handle.close()
                except:
                    pass
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
        self.progress = Progress(
            TextColumn("[bold blue]{task.description}", justify="right"),
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>3.1f}%",
            TimeRemainingColumn()
        )
        self.layout = Layout()
        self.layout.split(
            Layout(Panel(self.progress, title="Download Progress", border_style="green"), name="progress"),
            Layout(Panel("", title="Log", border_style="yellow", expand=True), name="log")
        )
        self.log_content = ""
        self.mkvmerge_content = ""
        self.mkvmerge_layout_ready = False
        self.live = Live(self.layout, refresh_per_second=4)

    def setup_logging(self):
        logging.basicConfig(
            level="INFO",
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(rich_tracebacks=True, console=console)]
        )

    @lru_cache(maxsize=None)
    def find_executable(self, name):
        system_path = shutil.which(name)
        if system_path:
            return system_path
        local_path = self.script_dir / (name + ('.exe' if sys.platform == 'win32' else ''))
        return str(local_path) if local_path.exists() else None

    def load_file_with_encodings(self, file_path, process_func):
        encodings = ['utf-8', 'utf-16', 'cp932', 'iso-8859-1']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return process_func(f)
            except UnicodeDecodeError:
                continue
        self.log(f"Unable to read file {file_path} with any of the attempted encodings: {encodings}")
        sys.exit(1)

    def load_config(self):
        config_path = self.script_dir / 'config.megumi'
        if not config_path.exists():
            self.log(f"Config file not found: {config_path}")
            sys.exit(1)
        return self.load_file_with_encodings(config_path, lambda f: dict(line.strip().split('=', 1) for line in f if '=' in line))

    def load_groups(self):
        groups_path = self.script_dir / 'groups.megumi'
        if not groups_path.exists():
            self.log(f"Groups file not found: {groups_path}")
            sys.exit(1)
        return self.load_file_with_encodings(groups_path, lambda f: [line.strip() for line in f if line.strip()])

    def load_series_list(self):
        series_list_path = self.script_dir / 'serieslist.megumi'
        if not series_list_path.exists():
            self.log(f"Series list file not found: {series_list_path}")
            sys.exit(1)
        return self.load_file_with_encodings(series_list_path, lambda f: [
            dict(zip(['file_name', 'folder_name', 'season_number'], line.strip().split('|')))
            for line in f if '|' in line
        ])

    def log(self, message):
        self.log_content += f"{message}\n"
        self.layout["log"].update(Panel(self.log_content.strip(), title="Log", border_style="yellow", expand=True))
        self.live.refresh()

    def mkvmerge_log(self, message):
        self.mkvmerge_content += f"{message}\n"
        if self.mkvmerge_layout_ready:
            self.layout["mkvmerge"].update(Panel(self.mkvmerge_content.strip(), title="MKVMerge Output", border_style="blue", expand=True))
            self.live.refresh()

    def download_chunk(self, ssh, remote_path, file, start, end, chunk_file, file_task):
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
                        self.progress.update(file_task, advance=len(data))
            return chunk_file
        finally:
            sftp.close()

    def download_file(self, ssh, remote_path, file):
        local_path = self.temp_dir / file
        remote_file_path = PurePosixPath(remote_path) / file
        if local_path.exists():
            local_path.unlink()
        self.log(f"Attempting to download: {file}")

        with ssh.open_sftp() as sftp:
            file_size = sftp.stat(str(remote_file_path)).st_size

        file_task = self.progress.add_task(file, total=file_size)

        if self.use_chunks and file_size > 1024 * 1024:
            chunk_size = math.ceil(file_size / self.chunks)
            chunk_files = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.chunks) as executor:
                futures = [
                    executor.submit(self.download_chunk, ssh, remote_path, file, 
                                    i * chunk_size, min((i + 1) * chunk_size, file_size), 
                                    local_path.with_suffix(f'.part{i}'), file_task)
                    for i in range(self.chunks)
                ]
                concurrent.futures.wait(futures)
                chunk_files = [f.result() for f in futures if f.result() is not None]

            with open(local_path, 'wb') as outfile:
                for chunk_file in chunk_files:
                    with open(chunk_file, 'rb') as infile:
                        shutil.copyfileobj(infile, outfile)
                    Path(chunk_file).unlink()
        else:
            with ssh.open_sftp() as sftp:
                sftp.get(str(remote_file_path), str(local_path), 
                         callback=lambda current, total: self.progress.update(file_task, completed=current))

        if local_path.stat().st_size > 0:
            self.log(f"Successfully downloaded: {file}")
            with ssh.open_sftp() as sftp:
                sftp.remove(str(remote_file_path))
                self.log(f"Removed remote file: {file}")
        else:
            self.log(f"Downloaded file {file} is empty. Deleting local copy.")
            local_path.unlink()

        self.progress.remove_task(file_task)

    def download_files(self):
        if self.config.get('MOVELOCAL', 'OFF').upper() == 'OFF':
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                ssh.connect(self.config['HOST'], username=self.config['USER'], password=self.config['PASSWORD'])

                remote_path = self.config['REMOTEPATCH']
                self.log(f"Attempting to list directory: {remote_path}")

                with ssh.open_sftp() as sftp:
                    remote_files = sftp.listdir(remote_path)
                    self.log(f"Successfully listed directory: {remote_path}")

                self.temp_dir.mkdir(parents=True, exist_ok=True)
                self.log(f"Files will be temporarily downloaded to: {self.temp_dir}")

                for temp_file in self.temp_dir.glob('*.mkv'):
                    if temp_file.name in remote_files:
                        temp_file.unlink()
                        self.log(f"Removed existing temporary file: {temp_file.name}")

                files_to_download = [
                    file for file in remote_files 
                    if file.lower().endswith('.mkv') and 
                    any(f"[{group}]" in file or f"【{group}】" in file for group in self.groups)
                ]
            
                self.log(f"Found {len(files_to_download)} MKV files to download")
            
                overall_task = self.progress.add_task("Overall", total=len(files_to_download))
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(self.download_file, ssh, remote_path, file) for file in files_to_download]
                    concurrent.futures.wait(futures)

                ssh.close()
            except Exception as e:
                self.log(f"Error during SFTP operations: {e}")
                sys.exit(1)
        else:
            self.log("MOVELOCAL option is ON. Processing local MKV files.")
            self.temp_dir = Path(self.config['LOCALTEMP'])
            if not self.temp_dir.exists():
                self.log(f"Local temp directory not found: {self.temp_dir}")
                sys.exit(1)
            
            files_to_process = list(self.temp_dir.glob('*.mkv'))
            self.log(f"Found {len(files_to_process)} MKV files to process in {self.temp_dir}")

        return self.temp_dir

    def move_files(self, temp_dir):
        self.log(f"Starting to move files from {temp_dir}")

        for file in temp_dir.glob('*.mkv'):
            if file.stat().st_size == 0:
                self.log(f"Skipping empty MKV file: {file.name}")
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
                        self.log(f"Destination file already exists. Overwriting: {dest_file}")
                        dest_file.unlink()

                    shutil.move(str(file), str(dest_file))
                    self.log(f"Moved file: {file.name} to {dest_file}")

                    if self.config.get('SAVEINFO', 'OFF').upper() == 'ON':
                        with open(dest_dir / "info.txt", "a") as info_file:
                            info_file.write(f"{file.name} ({new_name})\n")
                        self.log(f"Saved file info to: {dest_dir / 'info.txt'}")

                    self.process_subtitles(dest_dir, dest_file)
                else:
                    self.log(f"Could not extract episode number from MKV filename: {file.name}")
            else:
                self.log(f"No matching series found for MKV file: {file.name}")

        self.log("File moving process completed")

    def process_subtitles(self, dest_dir, file_path):
        replace_file = dest_dir / "replace.txt"
        self.log(f"Checking for replace.txt in: {dest_dir}")

        if not replace_file.exists():
            self.log(f"No replace.txt found for {file_path.name}. Skipping subtitle processing.")
            return

        self.log(f"replace.txt found for {file_path.name}. Proceeding with subtitle processing.")

        subtitle_path = file_path.with_suffix('.ass')
        try:
            self.log(f"Extracting subtitles from {file_path.name}")
            result = subprocess.run([self.mkvextract_path, str(file_path), 'tracks', f"2:{subtitle_path}"], 
                                    check=True, capture_output=True, text=True)
            self.mkvmerge_log("mkvextract output:")
            self.mkvmerge_log(self.format_progress_output(result.stdout))
        except subprocess.CalledProcessError as e:
            self.log(f"Error extracting subtitles: {e}")
            self.mkvmerge_log("mkvextract error output:")
            self.mkvmerge_log(e.stdout)
            self.mkvmerge_log(e.stderr)
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
            self.log(f"Remuxing file: {file_path.name}")
            mkvmerge_command = [self.mkvmerge_path, '-o', str(output_file), '--no-subtitles', str(file_path), 
                                '--language', '0:eng', '--track-name', '0:MegumiDownloadFixed', str(subtitle_path)]
            
            result = subprocess.run(mkvmerge_command, check=True, capture_output=True, text=True)
            self.mkvmerge_log("mkvmerge output:")
            self.mkvmerge_log(self.format_progress_output(result.stdout))
            
            file_path.unlink()
            output_file.rename(file_path)
            subtitle_path.unlink()
            self.log(f"Processed subtitles for: {file_path.name}")
        except subprocess.CalledProcessError as e:
            self.log(f"Error remuxing file: {e}")
            self.mkvmerge_log("mkvmerge error output:")
            self.mkvmerge_log(e.stdout)
            self.mkvmerge_log(e.stderr)

    def format_progress_output(self, output):
        lines = output.split('\n')
        formatted_lines = []
        progress_line = ""
        for line in lines:
            if line.startswith("Progress:"):
                progress_line = line
            else:
                if progress_line:
                    formatted_lines.append(progress_line)
                    progress_line = ""
                formatted_lines.append(line)
        if progress_line:
            formatted_lines.append(progress_line)
        return '\n'.join(formatted_lines)

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
        with self.live:
            self.log("Starting Megumi Download")

            temp_dir = self.download_files()

            # Remove the progress layout after downloading and add MKVMerge output layout
            self.layout["progress"].visible = False
            self.layout.split(
                Layout(Panel(self.log_content.strip(), title="Log", border_style="yellow", expand=True), name="log"),
                Layout(Panel(self.mkvmerge_content.strip(), title="MKVMerge Output", border_style="blue", expand=True), name="mkvmerge")
            )
            self.mkvmerge_layout_ready = True

            self.log("Download completed. Starting file moving process.")

            self.move_files(temp_dir)

            self.log("Megumi Download completed")

            # Keep the live display active for a moment to ensure all messages are visible
            time.sleep(2)

if __name__ == "__main__":
    instance_checker = SingleInstanceChecker()
    
    if instance_checker.try_lock():
        try:
            downloader = MegumiDownload()
            downloader.run()
        except Exception as e:
            console.print_exception()
        finally:
            instance_checker.unlock()
    else:
        console.print("[bold red]Another instance of Megumi Download is already running. Exiting.[/bold red]")
        sys.exit(1)
