#!/usr/bin/env python3
"""
Subtitle Tracks Management module for listing, extracting, and merging subtitle tracks.

This module provides tools to:
- List all subtitle tracks in video files (MKV, MP4, AVI, MOV, WEBM, etc.)
- Extract specific tracks by index, language, or filter (forced, hearing impaired)
- Extract all tracks from a video file
- Merge multiple subtitle files with configurable priority handling

Public API:
    - TrackInfo: Data class for track metadata
    - list_tracks: List all subtitle tracks in a video file
    - extract_track: Extract a specific subtitle track
    - extract_all_tracks: Extract all subtitle tracks
    - merge_subtitles: Merge multiple subtitle files
"""
import argparse
import json
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import List, Optional, Tuple

__all__ = [
    "TrackInfo",
    "list_tracks",
    "extract_track",
    "extract_all_tracks",
    "merge_subtitles",
    "SubtitleEntry",
    "parse_srt",
    "write_srt",
    "clean_srt_content",
]


@dataclass
class TrackInfo:
    """Data class for subtitle track metadata.
    
    Attributes:
        index: Track index in the container (0-based)
        language: Language code (e.g., 'eng', 'spa', 'fra')
        codec: Subtitle codec (e.g., 'subrip', 'mov_text', 'dvbsub')
        title: Optional title/description of the track
        is_forced: True if this is a forced subtitles track (foreign dialogue only)
        is_hearing_impaired: True if this track is for hearing impaired
    """
    index: int
    language: str
    codec: str
    title: Optional[str] = None
    is_forced: bool = False
    is_hearing_impaired: bool = False
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        parts = [f"Track {self.index}: {self.language.upper()}"]
        if self.title:
            parts.append(f"({self.title})")
        parts.append(f"- {self.codec}")
        flags = []
        if self.is_forced:
            flags.append("Forced")
        if self.is_hearing_impaired:
            flags.append("Hearing Impaired")
        if flags:
            parts.append(f"[{', '.join(flags)}]")
        return " ".join(parts)


@dataclass
class SubtitleEntry:
    """Data class for a single subtitle entry.
    
    Attributes:
        index: Sequence number
        start: Start time as timedelta
        end: End time as timedelta
        text: Subtitle text (can be multi-line)
    """
    index: int
    start: timedelta
    end: timedelta
    text: str
    
    def __repr__(self) -> str:
        return f"SubtitleEntry({self.index}, {self.start}, {self.end}, {self.text[:30]}...)"


def check_ffmpeg() -> bool:
    """Check if ffmpeg/ffprobe is installed.
    
    Returns:
        True if ffmpeg is available
        
    Raises:
        SystemExit with helpful installation instructions if not found
    """
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        import platform
        system = platform.system().lower()
        
        if system == "darwin":  # macOS
            install_msg = "To install ffmpeg on macOS, run: brew install ffmpeg"
        elif system == "linux":
            try:
                with open('/etc/os-release', 'r') as f:
                    os_release = f.read().lower()
                if 'ubuntu' in os_release or 'debian' in os_release:
                    install_msg = "To install ffmpeg on Ubuntu/Debian, run: sudo apt update && sudo apt install ffmpeg"
                elif 'centos' in os_release or 'red hat' in os_release or 'fedora' in os_release:
                    install_msg = "To install ffmpeg on CentOS/RHEL/Fedora, run: sudo dnf install ffmpeg"
                else:
                    install_msg = "To install ffmpeg on Linux, use your distribution's package manager (e.g., apt, dnf, pacman)"
            except Exception:
                install_msg = "To install ffmpeg on Linux, use your distribution's package manager (e.g., apt, dnf, pacman)"
        else:  # Windows or other
            install_msg = "To install ffmpeg on Windows, download from https://ffmpeg.org/download.html or run: choco install ffmpeg"
        
        sys.exit(f"Error: ffmpeg is required but not found. {install_msg}")


def _parse_ffprobe_output(video_file: Path) -> dict:
    """Run ffprobe and parse JSON output.
    
    Args:
        video_file: Path to the video file
        
    Returns:
        Parsed JSON as dictionary
        
    Raises:
        RuntimeError if ffprobe fails
    """
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        '-show_format',
        str(video_file)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed: {e.stderr}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse ffprobe output: {e}")


def list_tracks(video_file: Path) -> List[TrackInfo]:
    """List all subtitle tracks in a video file.
    
    Supports all ffmpeg-compatible formats: MKV, MP4, AVI, MOV, WEBM, FLV, etc.
    
    Args:
        video_file: Path to the video file
        
    Returns:
        List of TrackInfo objects containing track metadata
        
    Raises:
        FileNotFoundError: If video file doesn't exist
        RuntimeError: If ffprobe fails
    """
    if not video_file.exists():
        raise FileNotFoundError(f"Video file not found: {video_file}")
    
    check_ffmpeg()
    info = _parse_ffprobe_output(video_file)
    
    tracks = []
    for stream in info.get('streams', []):
        if stream.get('codec_type') == 'subtitle':
            tags = stream.get('tags', {})
            
            # Extract language
            language = tags.get('language', 'und')  # 'und' = undetermined
            
            # Extract title
            title = tags.get('title')
            
            # Check for hearing impaired flag
            is_hi = tags.get('handler_name', '').lower().find('hearing') >= 0
            
            # Check for forced subtitles flag
            is_forced = stream.get('disposition', {}).get('forced', False)
            
            tracks.append(TrackInfo(
                index=stream.get('index', 0),
                language=language,
                codec=stream.get('codec_name', 'unknown'),
                title=title,
                is_forced=is_forced,
                is_hearing_impaired=is_hi
            ))
    
    return tracks


def extract_track(
    video_file: Path,
    track_index: Optional[int] = None,
    language: Optional[str] = None,
    output_file: Optional[Path] = None,
    forced_only: bool = False,
    no_forced: bool = False
) -> Path:
    """Extract a specific subtitle track from a video file.
    
    Args:
        video_file: Path to the video file
        track_index: Track index to extract (0-based). If None, uses first matching track.
        language: Language code to filter by (e.g., 'eng', 'spa'). Case-insensitive.
        output_file: Output SRT file path. If None, auto-generates from input name.
        forced_only: Only extract forced subtitle tracks
        no_forced: Exclude forced subtitle tracks
        
    Returns:
        Path to the extracted SRT file
        
    Raises:
        FileNotFoundError: If video file doesn't exist
        ValueError: If no matching track found
        RuntimeError: If ffmpeg fails
    """
    if not video_file.exists():
        raise FileNotFoundError(f"Video file not found: {video_file}")
    
    check_ffmpeg()
    
    # Get all tracks and filter
    all_tracks = list_tracks(video_file)
    
    # Apply filters
    filtered_tracks = []
    for track in all_tracks:
        # Language filter
        if language and track.language.lower() != language.lower():
            continue
        # Forced filter
        if forced_only and not track.is_forced:
            continue
        if no_forced and track.is_forced:
            continue
        filtered_tracks.append(track)
    
    if not filtered_tracks:
        filter_desc = []
        if language:
            filter_desc.append(f"language={language}")
        if forced_only:
            filter_desc.append("forced-only")
        if no_forced:
            filter_desc.append("no-forced")
        raise ValueError(
            f"No subtitle track found{' ' + ', '.join(filter_desc) if filter_desc else ''} "
            f"in {video_file}. Available tracks: {', '.join(str(t) for t in all_tracks) if all_tracks else 'none'}"
        )
    
    # Select track
    if track_index is not None:
        # Use specific index (must pass filters)
        for track in filtered_tracks:
            if track.index == track_index:
                selected_track = track
                break
        else:
            raise ValueError(f"Track {track_index} not found or doesn't match filters")
    else:
        # Use first matching track
        selected_track = filtered_tracks[0]
    
    # Generate output filename if not specified
    if output_file is None:
        lang_suffix = selected_track.language if selected_track.language != 'und' else ''
        forced_suffix = '_forced' if selected_track.is_forced else ''
        hi_suffix = '_hi' if selected_track.is_hearing_impaired else ''
        
        if lang_suffix or forced_suffix or hi_suffix:
            suffix = f".{lang_suffix}{forced_suffix}{hi_suffix}.srt"
        else:
            suffix = f"_{selected_track.index}.srt"
        
        output_file = video_file.with_name(f"{video_file.stem}{suffix}")
    
    # Build ffmpeg command
    # Note: ffmpeg's -map 0:s:X uses the index among subtitle streams only,
    # not the global stream index. We need to find the subtitle stream index.
    subtitle_stream_index = 0
    global_index = 0
    info = _parse_ffprobe_output(video_file)
    for stream in info.get('streams', []):
        if stream.get('codec_type') == 'subtitle':
            if stream.get('index') == selected_track.index:
                break
            subtitle_stream_index += 1
    
    cmd = [
        'ffmpeg',
        '-loglevel', 'error',
        '-i', str(video_file),
        '-map', f'0:s:{subtitle_stream_index}',
        '-f', 'srt',
        str(output_file)
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return output_file
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg failed to extract track: {e.stderr}")


def extract_all_tracks(
    video_file: Path,
    output_dir: Optional[Path] = None,
    as_zip: bool = False
) -> Tuple[List[Path], Optional[Path]]:
    """Extract all subtitle tracks from a video file.
    
    Args:
        video_file: Path to the video file
        output_dir: Directory for output files. If None, uses video file's directory.
        as_zip: If True, package all extracted files into a ZIP archive
        
    Returns:
        Tuple of (list of extracted SRT file paths, ZIP file path if as_zip=True)
        
    Raises:
        FileNotFoundError: If video file doesn't exist
        RuntimeError: If ffmpeg fails
    """
    if not video_file.exists():
        raise FileNotFoundError(f"Video file not found: {video_file}")
    
    if output_dir is None:
        output_dir = video_file.parent
    elif not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
    
    check_ffmpeg()
    all_tracks = list_tracks(video_file)
    
    if not all_tracks:
        print(f"No subtitle tracks found in {video_file}")
        return [], None
    
    extracted_files = []
    
    for track in all_tracks:
        # Generate unique filename
        lang_suffix = track.language if track.language != 'und' else ''
        forced_suffix = '_forced' if track.is_forced else ''
        hi_suffix = '_hi' if track.is_hearing_impaired else ''
        
        if lang_suffix or forced_suffix or hi_suffix:
            suffix = f".{lang_suffix}{forced_suffix}{hi_suffix}.srt"
        else:
            suffix = f"_{track.index}.srt"
        
        output_file = output_dir / f"{video_file.stem}{suffix}"
        
        # Handle filename conflicts
        counter = 1
        while output_file.exists():
            if lang_suffix or forced_suffix or hi_suffix:
                suffix = f".{lang_suffix}{forced_suffix}{hi_suffix}_{counter}.srt"
            else:
                suffix = f"_{track.index}_{counter}.srt"
            output_file = output_dir / f"{video_file.stem}{suffix}"
            counter += 1
        
        # Extract using ffmpeg
        # Note: ffmpeg's -map 0:s:X uses the index among subtitle streams only
        cmd = [
            'ffmpeg',
            '-loglevel', 'error',
            '-i', str(video_file),
            '-map', f'0:s:{all_tracks.index(track)}',
            '-f', 'srt',
            str(output_file)
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            extracted_files.append(output_file)
            print(f"Extracted: {output_file.name}")
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to extract track {track.index}: {e.stderr}")
    
    # Create ZIP if requested
    zip_path = None
    if as_zip and extracted_files:
        zip_path = output_dir / f"{video_file.stem}_subtitles.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in extracted_files:
                zf.write(f, arcname=f.name)
        print(f"Created ZIP archive: {zip_path}")
    
    return extracted_files, zip_path


def _parse_srt_time(time_str: str) -> timedelta:
    """Parse SRT timestamp format (HH:MM:SS,mmm or HH:MM:SS.mmm).
    
    Args:
        time_str: Timestamp string
        
    Returns:
        timedelta object
    """
    # Handle both comma and period as decimal separator
    time_str = time_str.strip().replace(',', '.')
    
    parts = time_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    
    # Seconds might have milliseconds
    sec_parts = parts[2].split('.')
    seconds = int(sec_parts[0])
    milliseconds = int(sec_parts[1].ljust(3, '0')[:3]) if len(sec_parts) > 1 else 0
    
    return timedelta(
        hours=hours,
        minutes=minutes,
        seconds=seconds,
        milliseconds=milliseconds
    )


def _format_srt_time(td: timedelta) -> str:
    """Format timedelta to SRT timestamp format.
    
    Args:
        td: timedelta object
        
    Returns:
        Formatted timestamp string (HH:MM:SS,mmm)
    """
    total_seconds = int(td.total_seconds())
    milliseconds = int(td.microseconds / 1000)
    
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def parse_srt(content: str) -> List[SubtitleEntry]:
    """Parse SRT content into SubtitleEntry objects.
    
    Args:
        content: SRT file content as string
        
    Returns:
        List of SubtitleEntry objects
    """
    entries = []
    
    # Split into blocks (separated by blank lines)
    blocks = re.split(r'\n\s*\n', content)
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        
        # First line should be index
        try:
            index = int(lines[0])
        except ValueError:
            continue
        
        # Second line should be timestamp
        time_match = re.match(r'(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})', lines[1])
        if not time_match:
            continue
        
        start = _parse_srt_time(time_match.group(1))
        end = _parse_srt_time(time_match.group(2))
        
        # Remaining lines are text
        text = '\n'.join(lines[2:])
        
        entries.append(SubtitleEntry(
            index=index,
            start=start,
            end=end,
            text=text
        ))
    
    return entries


def write_srt(entries: List[SubtitleEntry], output_file: Path) -> None:
    """Write SubtitleEntry objects to SRT file.
    
    Args:
        entries: List of SubtitleEntry objects
        output_file: Output file path
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        for i, entry in enumerate(entries, 1):
            f.write(f"{i}\n")
            f.write(f"{_format_srt_time(entry.start)} --> {_format_srt_time(entry.end)}\n")
            f.write(f"{entry.text}\n\n")


def clean_srt_content(content: str) -> str:
    r"""Clean SRT content by removing ASS/SSA formatting tags.
    
    Removes formatting tags like {\an7}, {\b1}, {\i1}, <font>, etc. that
    aren't properly interpreted by video players, while preserving SRT structure.
    
    Args:
        content: Raw SRT content
        
    Returns:
        Cleaned SRT content
    """
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
                    # Remove HTML-like tags like <font>, </font>
                    cleaned_line = re.sub(r'<[^>]+>', '', cleaned_line)
                    # Remove any remaining backslash formatting like \h, \N
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


def clean_srt_file(srt_file: Path) -> None:
    """Clean an SRT file in-place by removing formatting tags.
    
    Args:
        srt_file: Path to the SRT file to clean
    """
    with open(srt_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    cleaned_content = clean_srt_content(content)
    
    with open(srt_file, 'w', encoding='utf-8') as f:
        f.write(cleaned_content)


def merge_subtitles(
    input_files: List[Path],
    output_file: Path,
    priority: str = "first"
) -> Path:
    """Merge multiple subtitle files into one.
    
    Combines subtitles from multiple files, handling overlapping timestamps
    based on the specified priority mode.
    
    Args:
        input_files: List of subtitle file paths to merge (in order)
        output_file: Output SRT file path
        priority: How to handle overlapping timestamps:
            - "first": Keep subtitle from first file
            - "second": Keep subtitle from second/later file
            - "combine": Stack both subtitles with line break between
            
    Returns:
        Path to the merged SRT file
        
    Raises:
        FileNotFoundError: If any input file doesn't exist
        ValueError: If priority mode is invalid
    """
    if priority not in ("first", "second", "combine"):
        raise ValueError(f"Invalid priority mode: {priority}. Must be 'first', 'second', or 'combine'")
    
    # Validate input files
    for f in input_files:
        if not f.exists():
            raise FileNotFoundError(f"Input file not found: {f}")
    
    # Parse all input files
    all_entries: List[Tuple[int, SubtitleEntry]] = []  # (file_index, entry)
    
    for file_idx, input_file in enumerate(input_files):
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        entries = parse_srt(content)
        for entry in entries:
            all_entries.append((file_idx, entry))
    
    if not all_entries:
        print("Warning: No subtitle entries found in any input file")
    
    # Sort by start time
    all_entries.sort(key=lambda x: (x[1].start, x[0]))
    
    # Merge entries, handling overlaps
    merged_entries: List[SubtitleEntry] = []
    used_indices = set()
    
    for file_idx, entry in all_entries:
        if (file_idx, entry.index) in used_indices:
            continue
        
        # Check for overlapping entries
        overlapping = []
        for other_file_idx, other_entry in all_entries:
            if (other_file_idx, other_entry.index) in used_indices:
                continue
            if (other_file_idx, other_entry.index) == (file_idx, entry.index):
                continue
            
            # Check if timestamps overlap
            if other_entry.start <= entry.end and other_entry.end >= entry.start:
                overlapping.append((other_file_idx, other_entry))
        
        if not overlapping:
            # No overlap, just add this entry
            merged_entries.append(entry)
            used_indices.add((file_idx, entry.index))
        else:
            # Handle overlap based on priority
            if priority == "first":
                # Keep only the first file's entry
                merged_entries.append(entry)
                used_indices.add((file_idx, entry.index))
            elif priority == "second":
                # Keep only the last file's entry
                last_entry = overlapping[-1][1]
                merged_entries.append(last_entry)
                used_indices.add((overlapping[-1][0], last_entry.index))
                used_indices.add((file_idx, entry.index))
            else:  # combine
                # Combine all overlapping entries
                combined_text = [entry.text]
                for other_file_idx, other_entry in overlapping:
                    combined_text.append(other_entry.text)
                    used_indices.add((other_file_idx, other_entry.index))
                
                combined_entry = SubtitleEntry(
                    index=entry.index,
                    start=entry.start,
                    end=entry.end,
                    text='\n'.join(combined_text)
                )
                merged_entries.append(combined_entry)
                used_indices.add((file_idx, entry.index))
    
    # Re-sort merged entries by start time
    merged_entries.sort(key=lambda x: x.start)
    
    # Re-number sequence
    final_entries = [
        SubtitleEntry(index=i, start=e.start, end=e.end, text=e.text)
        for i, e in enumerate(merged_entries, 1)
    ]
    
    # Write output
    write_srt(final_entries, output_file)
    
    return output_file


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manage subtitle tracks in video files - list, extract, and merge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all subtitle tracks in a video
  %(prog)s list video.mkv
  
  # Extract English subtitles
  %(prog)s extract video.mkv --language eng
  
  # Extract all tracks
  %(prog)s extract video.mkv --all --as-zip
  
  # Extract forced subtitles only
  %(prog)s extract video.mkv --forced-only
  
  # Merge two subtitle files
  %(prog)s merge subs1.srt subs2.srt -o merged.srt --priority combine
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List subtitle tracks in a video file')
    list_parser.add_argument('video', type=Path, help='Path to video file')
    list_parser.add_argument('--format', '-f', choices=['text', 'json'], default='text',
                            help='Output format (default: text)')
    
    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract subtitle track(s) from video')
    extract_parser.add_argument('video', type=Path, help='Path to video file')
    extract_parser.add_argument('--track', '-t', type=int, help='Track index to extract (0-based)')
    extract_parser.add_argument('--language', '-l', type=str, help='Language code (e.g., eng, spa)')
    extract_parser.add_argument('--all', '-a', action='store_true', help='Extract all tracks')
    extract_parser.add_argument('--output', '-o', type=Path, help='Output file or directory')
    extract_parser.add_argument('--as-zip', action='store_true', help='Package output as ZIP')
    extract_parser.add_argument('--forced-only', action='store_true', help='Only extract forced tracks')
    extract_parser.add_argument('--no-forced', action='store_true', help='Exclude forced tracks')
    
    # Merge command
    merge_parser = subparsers.add_parser('merge', help='Merge multiple subtitle files')
    merge_parser.add_argument('inputs', type=Path, nargs='+', help='Input subtitle files')
    merge_parser.add_argument('--output', '-o', type=Path, required=True, help='Output file')
    merge_parser.add_argument('--priority', '-p', choices=['first', 'second', 'combine'],
                             default='first', help='Overlap priority (default: first)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == 'list':
            tracks = list_tracks(args.video)
            if args.format == 'json':
                print(json.dumps([
                    {
                        'index': t.index,
                        'language': t.language,
                        'codec': t.codec,
                        'title': t.title,
                        'is_forced': t.is_forced,
                        'is_hearing_impaired': t.is_hearing_impaired
                    }
                    for t in tracks
                ], indent=2))
            else:
                if not tracks:
                    print(f"No subtitle tracks found in {args.video}")
                else:
                    print(f"Found {len(tracks)} subtitle track(s) in {args.video}:")
                    for track in tracks:
                        print(f"  {track}")
        
        elif args.command == 'extract':
            if args.all:
                output_dir = args.output if args.output else args.video.parent
                files, zip_file = extract_all_tracks(args.video, output_dir, args.as_zip)
                if files:
                    print(f"\nExtracted {len(files)} subtitle track(s)")
                    if zip_file:
                        print(f"ZIP archive: {zip_file}")
            else:
                output_file = extract_track(
                    args.video,
                    track_index=args.track,
                    language=args.language,
                    output_file=args.output,
                    forced_only=args.forced_only,
                    no_forced=args.no_forced
                )
                print(f"Extracted subtitle to: {output_file}")
        
        elif args.command == 'merge':
            output_file = merge_subtitles(args.inputs, args.output, args.priority)
            print(f"Merged subtitles to: {output_file}")
    
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
