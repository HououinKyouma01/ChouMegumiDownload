import sys
import re
import shutil
import logging
from pathlib import Path, PurePosixPath
import subprocess
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
import requests
import os
import psutil
import asyncio
import aiohttp
import asyncssh

console = Console()

class SingleInstanceChecker:
    def __init__(self):
        self.lockfile = Path(tempfile.gettempdir()) / 'megumi_download.lock'
        self.lock_handle = None

    def __enter__(self):
        if self.try_lock():
            return self
        else:
            console.print("[bold red]Another instance of Megumi Download is already running. Exiting.[/bold red]")
            sys.exit(1)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unlock()

    def try_lock(self):
        if self.lockfile.exists():
            if self.is_lock_stale():
                self.unlock()
            else:
                return False

        try:
            self.lock_handle = open(self.lockfile, 'w')
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(self.lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            self.lock_handle.write(str(os.getpid()))
            self.lock_handle.flush()
            return True
        except (IOError, OSError):
            return False

    def is_lock_stale(self):
        try:
            with open(self.lockfile, 'r') as f:
                pid = int(f.read().strip())
            return not psutil.pid_exists(pid)
        except (IOError, ValueError):
            return True

    def unlock(self):
        if self.lock_handle is not None:
            try:
                if sys.platform == 'win32':
                    import msvcrt
                    msvcrt.locking(self.lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.lock_handle, fcntl.LOCK_UN)
            except Exception:
                pass
            finally:
                self.lock_handle.close()
                try:
                    self.lockfile.unlink()
                except OSError:
                    pass
        elif self.lockfile.exists():
            try:
                self.lockfile.unlink()
            except OSError:
                pass

class MegumiDownload:
    def __init__(self):
        self.script_dir = self.get_script_dir()
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

    def get_script_dir(self):
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent
        else:
            return Path(os.path.dirname(os.path.abspath(__file__)))

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
            dict(zip(['file_name', 'folder_name', 'season_number', 'replace_url'], 
                     (line.strip().split('|') + [''])[:4]))
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

    async def download_chunk_async(self, session, conn, remote_path, file, start, end, chunk_file, file_task):
        async with conn.start_sftp_client() as sftp:
            async with await sftp.open(str(PurePosixPath(remote_path) / file), 'rb') as remote_file:
                await remote_file.seek(start)
                bytes_to_read = end - start
                with open(chunk_file, 'wb') as f:
                    while bytes_to_read > 0:
                        chunk_size = min(bytes_to_read, 32768)  # 32 KB chunks
                        data = await remote_file.read(chunk_size)
                        if not data:
                            break
                        f.write(data)
                        bytes_to_read -= len(data)
                        self.progress.update(file_task, advance=len(data))
        return chunk_file

    async def download_file_async(self, conn, remote_path, file):
        local_path = self.temp_dir / file
        remote_file_path = PurePosixPath(remote_path) / file
        if local_path.exists():
            local_path.unlink()
        self.log(f"Starting download: {file}")

        try:
            async with conn.start_sftp_client() as sftp:
                file_size = (await sftp.stat(str(remote_file_path))).size
                file_task = self.progress.add_task(file, total=file_size)

                async with sftp.open(str(remote_file_path), 'rb') as remote_file:
                    with open(local_path, 'wb') as local_file:
                        chunk_size = 1024 * 1024  # 1 MB chunks
                        downloaded = 0
                        while True:
                            chunk = await remote_file.read(chunk_size)
                            if not chunk:
                                break
                            local_file.write(chunk)
                            downloaded += len(chunk)
                            self.progress.update(file_task, completed=downloaded)

                if local_path.stat().st_size == file_size:
                    await sftp.remove(str(remote_file_path))
                    self.log(f"Successfully downloaded and removed remote file: {file}")
                    self.progress.remove_task(file_task)
                    return file, "success"
                else:
                    self.log(f"Downloaded file {file} size mismatch. Deleting local copy.")
                    local_path.unlink()
                    self.progress.remove_task(file_task)
                    return file, "error"

        except Exception as e:
            self.log(f"Error downloading {file}: {str(e)}")
            if file_task:
                self.progress.remove_task(file_task)
            return file, "error"

    async def download_files_async(self):
        if self.config.get('MOVELOCAL', 'OFF').upper() == 'OFF':
            try:
                asyncssh.set_debug_level(1)  # Reduce debug output

                async with asyncssh.connect(
                    self.config['HOST'],
                    username=self.config['USER'],
                    password=self.config['PASSWORD'],
                    known_hosts=None
                ) as conn:
                    remote_path = self.config['REMOTEPATCH']
                    self.log(f"Attempting to list directory: {remote_path}")

                    async with conn.start_sftp_client() as sftp:
                        remote_files = await sftp.listdir(remote_path)
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
                
                    if not files_to_download:
                        self.log("No files to download. Check your group settings and remote directory contents.")
                        return None

                    overall_task = self.progress.add_task("Overall", total=len(files_to_download))
                    
                    max_concurrent_downloads = 3  # Adjust this value as needed
                    semaphore = asyncio.Semaphore(max_concurrent_downloads)
                    
                    async def download_with_semaphore(file):
                        async with semaphore:
                            return await self.download_file_async(conn, remote_path, file)

                    tasks = [asyncio.create_task(download_with_semaphore(file)) for file in files_to_download]
                    
                    successful_downloads = []
                    failed_downloads = []

                    for task in asyncio.as_completed(tasks):
                        try:
                            file, status = await task
                            if status == "success":
                                self.log(f"Successfully downloaded: {file}")
                                successful_downloads.append(file)
                            elif status == "error":
                                self.log(f"Failed to download: {file}")
                                failed_downloads.append(file)
                            
                            self.progress.update(overall_task, advance=1)
                        except Exception as e:
                            self.log(f"Exception occurred during download: {str(e)}")
                            failed_downloads.append(str(e))
                            self.progress.update(overall_task, advance=1)

                    self.log(f"Download process completed. {len(successful_downloads)} files downloaded successfully.")
                    
                    if failed_downloads:
                        self.log(f"The following {len(failed_downloads)} files failed to download: {', '.join(map(str, failed_downloads))}")

            except Exception as e:
                self.log(f"Error during SFTP operations: {str(e)}")
                return None
        else:
            self.log("MOVELOCAL option is ON. Processing local MKV files.")
            self.temp_dir = Path(self.config['LOCALTEMP'])
            if not self.temp_dir.exists():
                self.log(f"Local temp directory not found: {self.temp_dir}")
                return None
            
            files_to_process = list(self.temp_dir.glob('*.mkv'))
            if not files_to_process:
                self.log(f"No MKV files found in {self.temp_dir}")
                return None
            self.log(f"Found {len(files_to_process)} MKV files to process in {self.temp_dir}")

        return self.temp_dir

    def download_files(self):
        try:
            temp_dir = asyncio.run(self.download_files_async())
            if temp_dir is None:
                self.log("Error: Failed to download or locate files. Check your configuration and network connection.")
                return None
            return temp_dir
        except Exception as e:
            self.log(f"Error in download_files: {str(e)}")
            return None

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
                        with open(dest_dir / "filelist.txt", "a") as info_file:
                            info_file.write(f"{file.name} ({new_name})\n")
                        self.log(f"Saved file info to: {dest_dir / 'filelist.txt'}")

                    # Validate replace.txt file before processing subtitles
                    replace_file = dest_dir / "replace.txt"
                    if replace_file.exists():
                        if self.validate_replace_file(replace_file):
                            self.log(f"replace.txt for {matched_series['folder_name']} Season {matched_series['season_number']} is valid.")
                            self.process_subtitles(dest_dir, dest_file)
                        else:
                            self.log(f"Warning: Invalid replace.txt found for {matched_series['folder_name']} Season {matched_series['season_number']}. Skipping subtitle processing.")
                    else:
                        self.log(f"No replace.txt found for {matched_series['folder_name']} Season {matched_series['season_number']}. Skipping subtitle processing.")
                else:
                    self.log(f"Could not extract episode number from MKV filename: {file.name}")
            else:
                self.log(f"No matching series found for MKV file: {file.name}")

        self.log("File moving process completed")

    def process_subtitles(self, dest_dir, file_path):
        replace_file = dest_dir / "replace.txt"
        self.log(f"Processing subtitles for {file_path.name}")

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

        try:
            with open(replace_file, 'r', encoding='utf-8') as f:
                replacements = [line.strip().split('|') for line in f if '|' in line.strip()]
        except Exception as e:
            self.log(f"Error reading replace.txt for {file_path.name}: {e}")
            return

        for old, new in replacements:
            old_escaped = re.escape(old)
            pattern = r'(?<!\w)' + old_escaped + r'(?!\w)'
            
            def replace_func(match):
                matched = match.group(0)
                if matched.endswith("'s"):
                    return new + "'s"
                elif matched.endswith("'"):
                    return new + "'"
                elif '-' in new and '-' not in matched:
                    return new
                else:
                    return new

            content = re.sub(pattern, replace_func, content)

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

    def validate_replace_file(self, replace_file):
        try:
            with open(replace_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                if '|' not in line:
                    self.log(f"Warning: Invalid format in replace.txt at line {i}. Expected '|' separator.")
                    return False
                
                parts = line.split('|')
                if len(parts) != 2:
                    self.log(f"Warning: Invalid format in replace.txt at line {i}. Expected exactly one '|' separator.")
                    return False
                
                if not parts[0].strip() or not parts[1].strip():
                    self.log(f"Warning: Empty replacement found in replace.txt at line {i}.")
                    return False

            return True
        except Exception as e:
            self.log(f"Error validating replace.txt: {e}")
            return False

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
            ("\\N", " \\N "), ("\\h", "\\h "),
        ]
        for old, new in replacements:
            text = text.replace(old, new)
        return text

    def download_replace_file(self, series):
        if not series['replace_url']:
            return

        self.log(f"Downloading replace.txt for {series['folder_name']} Season {series['season_number']}")
        
        try:
            response = requests.get(series['replace_url'])
            response.raise_for_status()
            content = response.text

            if not self.is_plain_text(content):
                self.log(f"Warning: The content at {series['replace_url']} is not plain text. Skipping.")
                return

            dest_dir = Path(self.config['LOCALPATCH']) / series['folder_name'] / f"Season {series['season_number']}"
            dest_dir.mkdir(parents=True, exist_ok=True)

            replace_file = dest_dir / "replace.txt"
            
            # Always write the new content
            with open(replace_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self.log(f"Updated replace.txt for {series['folder_name']} Season {series['season_number']}")

            if not self.validate_replace_file(replace_file):
                self.log(f"Warning: Downloaded replace.txt for {series['folder_name']} Season {series['season_number']} has invalid format.")
            else:
                self.log(f"Successfully validated replace.txt for {series['folder_name']} Season {series['season_number']}")

        except requests.RequestException as e:
            self.log(f"Error downloading replace.txt for {series['folder_name']} Season {series['season_number']}: {e}")

    def is_plain_text(self, content):
        try:
            content.encode('ascii')
            return True
        except UnicodeEncodeError:
            return False

    def run(self):
        with self.live:
            self.log("Starting Megumi Download")

            # Download replace.txt files
            for series in self.series_list:
                self.download_replace_file(series)

            temp_dir = self.download_files()
            if temp_dir is None:
                self.log("Aborting due to download failure.")
                return

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
    with SingleInstanceChecker() as instance_check:
        try:
            downloader = MegumiDownload()
            downloader.run()
        except Exception as e:
            console.print_exception()
        finally:
            print("Megumi Download completed.")
