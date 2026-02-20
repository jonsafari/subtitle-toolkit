#!/usr/bin/env python3
"""
subtitle_mkv2srt.py

Extracts subtitles from MKV files and converts them to SRT format.
By default, extracts all subtitles and saves them to individual files.

Usage:
    python subtitle_mkv2srt.py --input input.mkv
    python subtitle_mkv2srt.py --input input.mkv --output output.srt
    python subtitle_mkv2srt.py --input input.mkv --language en
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import json

def extract_subtitles(mkv_file: Path, language: str = None, output_file: Path = None) -> Path:
    """
    Extract subtitles from an MKV file using ffmpeg.
    
    Args:
        mkv_file: Path to the input MKV file
        language: Language code to filter subtitles (optional)
        output_file: Path to output SRT file (optional)
        
    Returns:
        Path to the extracted SRT file
    """
    if not mkv_file.exists():
        raise FileNotFoundError(f"MKV file not found: {mkv_file}")
    
    # If no output file specified, generate one based on input filename
    if output_file is None:
        output_file = mkv_file.with_suffix('.srt')
    
    # Build ffmpeg command
    cmd = ['ffmpeg', '-loglevel', 'error', '-i', str(mkv_file), '-f', 'srt']
    
    # Add language filter if specified
    if language:
        # Find subtitle track by language using ffprobe first
        try:
            probe_cmd = ['ffprobe', '-loglevel', 'error', '-v', 'quiet', '-print_format', 'json', '-show_streams', str(mkv_file)]
            result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            
            # Find subtitle track with matching language
            subtitle_tracks = []
            for stream in info['streams']:
                if stream['codec_type'] == 'subtitle':
                    if 'tags' in stream and 'language' in stream['tags']:
                        if stream['tags']['language'] == language:
                            subtitle_tracks.append(stream)
            
            if subtitle_tracks:
                # Use the first matching track
                track_index = subtitle_tracks[0]['index']
                cmd.extend(['-map', f'0:s:{track_index}'])
            else:
                print(f"Warning: No subtitle track found with language '{language}'")
                # Try to extract all subtitles if specific language not found
                cmd.extend(['-map', '0:s'])
        except Exception as e:
            print(f"Warning: Could not determine subtitle track by language: {e}")
            # Fall back to extracting all subtitles
            cmd.extend(['-map', '0:s'])
    else:
        # Extract all subtitle tracks
        cmd.extend(['-map', '0:s'])
    
    # Add output file
    cmd.append(str(output_file))
    
    try:
        # Run ffmpeg command
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"Successfully extracted subtitles to {output_file}")
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"Error extracting subtitles: {e.stderr}")
        raise Exception("Error extracting subtitles")


def extract_all_subtitles(mkv_file: Path) -> list:
    """
    Extract all subtitle tracks from MKV file and save each to a separate SRT file.
    
    Args:
        mkv_file: Path to the input MKV file
        
    Returns:
        List of paths to extracted SRT files
    """
    # First, get information about subtitle tracks using ffprobe
    cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', str(mkv_file)]
    
    try:
        import json
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        
        srt_files = []
        subtitle_tracks = []
        
        # Find all subtitle streams
        for stream in info['streams']:
            if stream['codec_type'] == 'subtitle':
                subtitle_tracks.append(stream)
        
        if not subtitle_tracks:
            print("No subtitle tracks found in the MKV file")
            return []
        
        # Extract each subtitle track
        for i, stream in enumerate(subtitle_tracks):
            # Determine language for naming the output file
            language = "unknown"
            if 'tags' in stream and 'language' in stream['tags']:
                language = stream['tags']['language']
            elif 'codec_name' in stream and 'dvd' in stream['codec_name']:
                # For DVD subtitle streams, we might want to use a different naming convention
                language = "dvd"
            
            # Generate output filename based on language or track index
            if language != "unknown" and language != "dvd":
                output_file = mkv_file.with_name(f"{mkv_file.stem}.{language}.srt")
            else:
                output_file = mkv_file.with_name(f"{mkv_file.stem}_sub{i:02d}.srt")
            
            # Build ffmpeg command for this specific subtitle track
            cmd = ['ffmpeg', '-loglevel', 'error', '-i', str(mkv_file), '-map', f'0:s:{i}', '-f', 'srt', str(output_file)]
            
            try:
                subprocess.run(cmd, capture_output=True, check=True)
                print(f"Successfully extracted subtitle track {i} ({language}) to {output_file}")
                srt_files.append(output_file)
            except subprocess.CalledProcessError as e:
                print(f"Error extracting subtitle track {i}: {e.stderr}")
                
        return srt_files
        
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error getting subtitle information: {e}")
        return []


def clean_srt_content(content: str) -> str:
    """
    Clean SRT content by removing ASS/SSA formatting tags like {\an7} that 
    aren't properly interpreted by video players, while preserving SRT structure.
    
    Args:
        content: Raw SRT content
        
    Returns:
        Cleaned SRT content
    """
    import re
    
    # Split content into blocks (each block is separated by empty lines)
    blocks = content.split('\n\n')
    
    cleaned_blocks = []
    
    for block in blocks:
        if not block.strip():
            # Empty block - keep it as is
            cleaned_blocks.append('')
            continue
            
        # Split block into lines
        lines = block.split('\n')
        
        # First two lines are sequence number and timecodes - preserve them
        cleaned_lines = []
        
        # Process text lines (skip sequence number and timecodes)
        for i, line in enumerate(lines):
            if i < 2:
                # Keep sequence number and timecodes as-is
                cleaned_lines.append(line)
            else:
                # Clean text lines - remove ASS/SSA formatting tags
                if line.strip():
                    # Remove ASS/SSA formatting tags like {\an7}, {\b1}, {\i1}, etc.
                    cleaned_line = re.sub(r'\{[^}]*\}', '', line)
                    # Remove any remaining backslashes that might be left over
                    cleaned_line = re.sub(r'\\[a-zA-Z][0-9]*', '', cleaned_line)
                    # Only add non-empty lines
                    if cleaned_line.strip():
                        cleaned_lines.append(cleaned_line)
        
        # Join the cleaned lines back together
        cleaned_block = '\n'.join(cleaned_lines)
        if cleaned_block.strip():  # Only add non-empty blocks
            cleaned_blocks.append(cleaned_block)
    
    # Join blocks back with double newlines
    result = '\n\n'.join(cleaned_blocks)
    
    # Remove any trailing newlines
    result = result.rstrip('\n')
    
    return result


def process_srt_files(srt_files: list) -> None:
    """
    Process SRT files to clean up formatting tags.
    
    Args:
        srt_files: List of SRT file paths to process
    """
    for srt_file in srt_files:
        try:
            # Read the content
            with open(srt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Clean the content
            cleaned_content = clean_srt_content(content)
            
            # Write back the cleaned content
            with open(srt_file, 'w', encoding='utf-8') as f:
                f.write(cleaned_content)
                
            print(f"Cleaned formatting tags from {srt_file}")
            
        except Exception as e:
            print(f"Error processing {srt_file}: {e}")


def check_ffmpeg():
    """Check if ffmpeg is installed and provide helpful error messages if not."""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Provide helpful installation instructions based on platform
        import platform
        system = platform.system().lower()
        
        if system == "darwin":  # macOS
            install_msg = "To install ffmpeg on macOS, run: brew install ffmpeg"
        elif system == "linux":
            # Try to detect common Linux distributions
            try:
                with open('/etc/os-release', 'r') as f:
                    os_release = f.read().lower()
                if 'ubuntu' in os_release or 'debian' in os_release:
                    install_msg = "To install ffmpeg on Ubuntu/Debian, run: sudo apt update && sudo apt install ffmpeg"
                elif 'centos' in os_release or 'red hat' in os_release or 'fedora' in os_release:
                    install_msg = "To install ffmpeg on CentOS/RHEL/Fedora, run: sudo dnf install ffmpeg"
                else:
                    install_msg = "To install ffmpeg on Linux, use your distribution's package manager (e.g., apt, dnf, pacman)"
            except:
                install_msg = "To install ffmpeg on Linux, use your distribution's package manager (e.g., apt, dnf, pacman)"
        else:  # Windows or other
            install_msg = "To install ffmpeg on Windows, download it from https://ffmpeg.org/download.html or use: choco install ffmpeg"
        
        sys.exit(f"Error: ffmpeg is required but not found. {install_msg}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract subtitles from MKV files and convert to SRT format"
    )
    parser.add_argument(
        '--input',
        '-i',
        type=Path,
        required=True,
        help='Path to the input MKV file'
    )
    parser.add_argument(
        '--output',
        '-o',
        type=Path,
        help='Output SRT file path (default: input filename with .srt extension)'
    )
    parser.add_argument(
        '--language',
        '-l',
        type=str,
        help='Language code to filter subtitles (e.g., "en", "es")'
    )
    
    args = parser.parse_args()
    
    # Validate input file
    if not args.input.is_file():
        sys.exit(f"Error: Input file does not exist: {args.input}")
    
    # Check if ffmpeg is available
    check_ffmpeg()
    
    try:
        # If specific output file is specified, extract to that file
        if args.output:
            output_file = extract_subtitles(
                args.input, 
                args.language, 
                args.output
            )
            print(f"Subtitle extraction completed: {output_file}")
        else:
            # By default, extract all subtitles to individual files
            srt_files = extract_all_subtitles(args.input)
            if srt_files:
                print(f"Successfully extracted {len(srt_files)} subtitle tracks:")
                for file in srt_files:
                    print(f"  - {file}")
                
                # Clean formatting tags from all extracted files
                process_srt_files(srt_files)
            else:
                print("No subtitle tracks were extracted.")
        
    except Exception as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()