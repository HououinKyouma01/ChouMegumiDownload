from datetime import timedelta
import ffmpeg
import ass
import os
import sys
import shutil
import subprocess
import time
from typing import List
from tqdm import tqdm

def check_ffmpeg_installed():
    """Check if ffmpeg executable is available"""
    if shutil.which("ffmpeg") is None:
        print("Error: ffmpeg executable not found in PATH")
        print("Please install ffmpeg from https://ffmpeg.org/download.html")
        print("1. Download the Windows build")
        print("2. Extract the zip file")
        print("3. Add the bin folder to your system PATH")
        print("4. Restart your command prompt")
        sys.exit(1)

def extract_existing_subtitles(video_path: str) -> str:
    """Extract existing English subtitles from video"""
    try:
        # Verify video file exists first
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
            
        # Properly escape Windows paths
        if os.name == 'nt':
            video_path = video_path.replace('\\', '/')
            
        streams = ffmpeg.probe(video_path)['streams']
        sub_streams = [s for s in streams if s['codec_type'] == 'subtitle' 
                      and s.get('tags', {}).get('language', '').lower() == 'eng']
        
        if not sub_streams:
            return None
            
        # Extract first English subtitle stream to temporary file
        sub_stream = sub_streams[0]
        output_path = os.path.join(os.path.dirname(video_path), 'temp_extracted.ass')
        
        try:
            (
                ffmpeg.input(video_path)
                .output(output_path, map=f"0:{sub_stream['index']}")
                .overwrite_output()
                .run(quiet=True)
            )
        except ffmpeg.Error as e:
            print(f"FFmpeg error: {e.stderr.decode()}")
            raise
        
        return output_path
    except Exception as e:
        print(f"Warning: Could not extract subtitles - {str(e)}")
        return None

def reencode_video(input_path: str) -> str:
    """Re-encode video with proper keyframe placement"""
    print("\nRe-encoding video...")
    try:
        # Create re-encoded file in same directory as source
        source_dir = os.path.dirname(input_path)
        output_path = os.path.join(source_dir, 'temp_reencoded.mkv')
        
        # Run ffmpeg with standard output
        (
            ffmpeg.input(input_path)
            .filter('scale', -2, 720)  # Scale to 720p height, maintain aspect ratio
            .output(output_path, 
                   vcodec='libx264', 
                   acodec='copy',  # Copy audio without re-encoding
                   preset='medium',  # Better quality/compression balance
                   g=250,  # Maximum keyframe interval
                   keyint_min=24,  # Minimum keyframe interval
                   sc_threshold=40,  # Scene change detection sensitivity
                   crf=23,
                   x264opts='keyint=250:min-keyint=24:scenecut=40:no-mbtree',
                   format='matroska')  # Use MKV container
            .overwrite_output()
            .run(cmd='ffmpeg')  # This will show standard ffmpeg output
        )
        print("\nRe-encoding complete!")
        return output_path
    except ffmpeg.Error as e:
        print(f"\nFFmpeg error during re-encoding: {e.stderr.decode()}")
        raise

def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds"""
    try:
        probe = ffmpeg.probe(video_path)
        return float(probe['format']['duration'])
    except Exception as e:
        print(f"Error getting video duration: {str(e)}")
        raise

def adjust_subtitles(ass_path: str, keyframes: List[float] = None) -> str:
    """Adjust subtitle timings to align with scene changes"""
    # Normalize path for Windows
    ass_path = os.path.normpath(ass_path)
    
    # Read and validate ASS file content
    try:
        with open(ass_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
            
            # Basic validation of ASS file structure
            if "[Script Info]" not in original_content:
                raise ValueError("Invalid ASS file: Missing [Script Info] section")
            if "[Events]" not in original_content:
                raise ValueError("Invalid ASS file: Missing [Events] section")
                
            # Parse with error handling
            try:
                doc = ass.parse_string(original_content)
            except Exception as e:  # Catch any parsing errors
                # Try to parse just the events section
                events_start = original_content.find("[Events]")
                if events_start == -1:
                    raise ValueError("Could not find [Events] section in ASS file")
                    
                # Create minimal valid ASS structure
                minimal_ass = """[Script Info]
ScriptType: v4.00+
PlayResX: 384
PlayResY: 288

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

""" + original_content[events_start:]
                
                doc = ass.parse_string(minimal_ass)
                
    except Exception as e:
        print(f"Error reading/parsing ASS file: {str(e)}")
        raise
    
    events = sorted(doc.events, key=lambda x: x.start)
    
    # Get keyframes from the re-encoded video
    video_path = os.path.normpath(os.path.join(os.path.dirname(ass_path), 'temp_reencoded.mkv'))
    if not os.path.exists(video_path):
        print(f"Warning: Re-encoded video not found: {video_path}")
        keyframes = []
    else:
        try:
            # Use ffprobe to get keyframe timestamps with better detection
            command = [
                'ffprobe', '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'packet=pts_time,flags',
                '-of', 'csv=p=0',
                '-skip_frame', 'nokey',  # Only process keyframes
                video_path
            ]
            
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                raise ValueError(f"FFprobe error: {stderr.decode()}")
            
            output = stdout.decode('utf-8')
            keyframes = []
            
            for line in output.splitlines():
                parts = line.split(',')
                if len(parts) == 2 and 'K' in parts[1]:  # Check for keyframe flag
                    try:
                        timestamp = int(float(parts[0]) * 1000)  # Convert to milliseconds
                        keyframes.append(timestamp)
                    except (ValueError, IndexError):
                        continue
            
            if not keyframes:
                print("Warning: No keyframes found in video")
    
        except Exception as e:
            print(f"Warning: Could not get keyframes - {str(e)}")
            keyframes = []
    
    # Adjust subtitles to nearest keyframe
    if keyframes:
        print(f"Found {len(keyframes)} keyframes for timing adjustments")
        print(f"First few keyframes: {keyframes[:5]}...")
        
        for event in events:
            # Convert timedelta to milliseconds
            def timedelta_to_ms(td):
                return int(td.total_seconds() * 1000)
            
            start_ms = timedelta_to_ms(event.start)
            end_ms = timedelta_to_ms(event.end)
            
            # Find nearest keyframe for start and end
            nearest_start = min(keyframes, key=lambda x: abs(x - start_ms))
            nearest_end = min(keyframes, key=lambda x: abs(x - end_ms))
            
            # Only adjust if within 500ms of a keyframe
            start_diff = abs(nearest_start - start_ms)
            end_diff = abs(nearest_end - end_ms)
            
            if start_diff <= 500:
                # Convert milliseconds to timedelta
                event.start = timedelta(milliseconds=nearest_start)
                print(f"Adjusted start: {start_ms}ms -> {nearest_start}ms (diff: {start_diff}ms)")
            
            if end_diff <= 500:
                # Convert milliseconds to timedelta
                event.end = timedelta(milliseconds=nearest_end)
                print(f"Adjusted end: {end_ms}ms -> {nearest_end}ms (diff: {end_diff}ms)")
            
            # Ensure minimum duration using timedelta
            min_duration = timedelta(milliseconds=100)  # Minimum duration as timedelta
            
            if event.end <= event.start:
                # Add minimum duration to start time
                event.end = event.start + min_duration
                print(f"Extended duration to minimum {min_duration.total_seconds()*1000}ms")
    else:
        print("No keyframes available - skipping timing adjustments")
    
    # Process subtitles with new timing logic
    MAX_GAP_MS = 650  # Maximum allowed gap between subtitles
    MAX_OVERLAP_MS = 0  # Maximum allowed overlap
    BIAS_END = True  # Bias adjustments towards end of subtitles
    
    # First pass: Adjust to keyframes with end bias
    for i, event in enumerate(events):
        # Convert timedelta to milliseconds
        def timedelta_to_ms(td):
            return int(td.total_seconds() * 1000)
        
        start_ms = timedelta_to_ms(event.start)
        end_ms = timedelta_to_ms(event.end)
        
        # Find nearest keyframes with end bias
        if keyframes:
            # For start time, find keyframe before or at the same time
            possible_starts = [k for k in keyframes if k <= start_ms]
            nearest_start = max(possible_starts) if possible_starts else start_ms
            
            # For end time, find keyframe after or at the same time
            possible_ends = [k for k in keyframes if k >= end_ms]
            nearest_end = min(possible_ends) if possible_ends else end_ms
            
            # Only adjust if within 500ms of a keyframe
            start_diff = abs(nearest_start - start_ms)
            end_diff = abs(nearest_end - end_ms)
            
            if start_diff <= 500:
                event.start = timedelta(milliseconds=nearest_start)
            
            if end_diff <= 500:
                event.end = timedelta(milliseconds=nearest_end)
            
            # Ensure minimum duration
            min_duration = timedelta(milliseconds=100)
            if event.end <= event.start:
                event.end = event.start + min_duration
    
    # Second pass: Make adjacent subtitles continuous
    for i in range(len(events) - 1):
        current = events[i]
        next_event = events[i + 1]
        
        current_end_ms = timedelta_to_ms(current.end)
        next_start_ms = timedelta_to_ms(next_event.start)
        
        gap = next_start_ms - current_end_ms
        
        if 0 < gap <= MAX_GAP_MS:
            # Adjust next subtitle start to current end
            next_event.start = current.end
        elif gap < 0 and abs(gap) <= MAX_OVERLAP_MS:
            # Adjust current end to next start
            current.end = next_event.start
    
    # Save adjusted subtitles while preserving original file structure
    output_path = os.path.normpath(ass_path.replace('.ass', '_fixed.ass'))
    
    # Split original content into header and events
    header_end = original_content.find("[Events]")
    if header_end == -1:
        header_end = len(original_content)
    
    header = original_content[:header_end]
    events_section = original_content[header_end:]
    
    with open(output_path, 'w', encoding='utf-8', newline='\r\n') as f:
        # Write original header
        f.write(header)
        
        # Write modified events
        if "[Events]" not in header:
            f.write("[Events]\n")
            f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        
        for event in doc.events:
            # Convert timedelta to ASS time format
            def format_ass_time(td):
                total_seconds = int(td.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                centiseconds = int(td.microseconds / 10000)
                return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"
            
            start_time = format_ass_time(event.start)
            end_time = format_ass_time(event.end)
            f.write(f"Dialogue: {event.layer},{start_time},{end_time},{event.style},{event.name},"
                   f"{event.margin_l},{event.margin_r},{event.margin_v},{event.effect},{event.text}\n")
    
    return output_path

def mux_subtitles(video_path: str, ass_path: str) -> None:
    """Mux subtitles back into original video using mkvtoolnix, overwriting the original file"""
    # Normalize paths for Windows
    video_path = os.path.normpath(video_path)
    ass_path = os.path.normpath(ass_path)
    
    print("\nMuxing subtitles with mkvtoolnix...")
    
    # Check if mkvmerge is available
    if shutil.which("mkvmerge") is None:
        print("Error: mkvmerge executable not found in PATH")
        print("Please install mkvtoolnix from https://mkvtoolnix.download/")
        sys.exit(1)
    
    # Create temporary output path
    temp_output = video_path + '.temp.mkv'
    
    try:
        # Verify input files exist
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        if not os.path.exists(ass_path):
            raise FileNotFoundError(f"Subtitle file not found: {ass_path}")
            
        # Build mkvmerge command with more robust options
        command = [
            'mkvmerge',
            '-o', temp_output,
            '--no-subtitles',  # Remove all existing subtitles
            video_path,
            '--language', '0:eng',  # Set subtitle language to English
            '--track-name', '0:FixedTiming',  # Set track name
            '--default-track', '0:yes',  # Set as default track
            '--forced-track', '0:no',  # Not forced
            ass_path
        ]
        
        # Run mkvmerge with timeout
        process = subprocess.Popen(
            command, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Read output in real-time
        output = []
        while True:
            line = process.stdout.readline()
            if line == '' and process.poll() is not None:
                break
            if line:
                output.append(line)
                print(line.strip())  # Print progress
        
        # Check return code
        if process.returncode != 0:
            error_msg = f"mkvmerge failed with return code {process.returncode}\n"
            error_msg += "Command: " + ' '.join(command) + "\n"
            error_msg += "Output:\n" + ''.join(output) + "\n"
            error_msg += "Error output:\n" + process.stderr.read()
            raise RuntimeError(error_msg)
        
        # Verify output file exists and has content
        if not os.path.exists(temp_output) or os.path.getsize(temp_output) == 0:
            raise RuntimeError("mkvmerge failed to create output file")
        
        # Replace original file with the new version
        os.remove(video_path)
        os.rename(temp_output, video_path)
        
        print("\nMuxing complete! Original file has been updated.")
        
    except Exception as e:
        # Clean up temp file if something went wrong
        if os.path.exists(temp_output):
            os.remove(temp_output)
        print(f"\nError during muxing: {str(e)}")
        # Save error log in script directory
        error_log_path = os.path.join(os.path.dirname(__file__), 'mux_error.log')
        with open(error_log_path, 'w') as f:
            f.write(f"Error: {str(e)}\n")
            f.write(f"Video: {video_path}\n")
            f.write(f"Subtitles: {ass_path}\n")
        print(f"Error details saved to: {error_log_path}")
        raise

def fix_timing(video_path: str, ass_path: str = None, debug: bool = False) -> str:
    """
    Full workflow:
    1. Extract existing English subtitles if no ASS file provided
    2. Re-encode video with proper keyframes
    3. Extract keyframes
    4. Adjust subtitles to keyframes
    5. Mux subtitles back into original video
    6. Clean up temporary files unless debug mode is enabled

    Args:
        video_path: Path to video file
        ass_path: Optional path to ASS subtitle file
        debug: If True, keeps temporary files for debugging
    """
    # Step 1: Extract existing subtitles if needed
    if not ass_path:
        ass_path = extract_existing_subtitles(video_path)
        if not ass_path:
            print("Error: No subtitles found in video and no ASS file provided")
            sys.exit(1)
    
    # Step 2: Re-encode video if needed
    reencoded_path = reencode_video(video_path)
    
    # Step 3: Get video duration for timing adjustments
    duration = get_video_duration(reencoded_path)
    
    # Step 4: Adjust subtitles using detected keyframes
    fixed_ass_path = adjust_subtitles(ass_path)
    
    # Step 5: Mux subtitles back into original file
    try:
        # Verify the fixed ASS file exists
        if not os.path.exists(fixed_ass_path):
            raise FileNotFoundError(f"Fixed subtitle file not found: {fixed_ass_path}")
            
        mux_subtitles(video_path, fixed_ass_path)
        print(f"\nSuccessfully updated subtitles in: {video_path}")
    except ffmpeg.Error as e:
        print(f"\nError during muxing: {e.stderr.decode()}")
        raise
    
    # Step 6: Clean up unless in debug mode
    if not debug:
        try:
            if os.path.exists(reencoded_path):
                os.remove(reencoded_path)
            if ass_path.endswith('_extracted.ass') and os.path.exists(ass_path):
                os.remove(ass_path)
            if os.path.exists(fixed_ass_path):
                os.remove(fixed_ass_path)
        except Exception as e:
            print(f"Warning during cleanup: {str(e)}")
    else:
        print("\nDebug mode - keeping temporary files:")
        print(f"  Re-encoded video: {reencoded_path}")
        if ass_path.endswith('_extracted.ass'):
            print(f"  Extracted subtitles: {ass_path}")
        print(f"  Adjusted subtitles: {fixed_ass_path}")
    
    return fixed_ass_path

if __name__ == "__main__":
    # Check for ffmpeg executable first
    check_ffmpeg_installed()
    
    if len(sys.argv) < 2:
        print("Usage: python program.py <video.mp4> [subtitles.ass] [--debug]")
        print("If no ASS file is provided, will attempt to extract English subtitles from video")
        print("Add --debug flag to keep temporary files for debugging")
        sys.exit(1)
        
    video_path = args[0]
    ass_path = None
    debug = False
    
    # Parse arguments
    for arg in args[1:]:
        if arg == '--debug':
            debug = True
        elif arg.endswith('.ass'):
            ass_path = arg
    
    if not os.path.exists(video_path):
        print(f"Video file not found: {video_path}")
        sys.exit(1)
        
    # Only check ass_path if it was provided
    if ass_path is not None and not os.path.exists(ass_path):
        print(f"Subtitle file not found: {ass_path}")
        sys.exit(1)
    
    try:
        result_path = fix_timing(video_path, ass_path, debug)
        print(f"Success! Updated file: {result_path}")
    except Exception as e:
        print(f"Error processing files: {str(e)}")
        sys.exit(1)
