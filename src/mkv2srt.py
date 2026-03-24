#!/usr/bin/env python3
"""
MKV to SRT conversion module for extracting subtitles from video files.

DEPRECATED: This module is deprecated and will be removed in a future version.
Please use the `subtitle_tracks` module instead, which provides enhanced functionality:
- List all subtitle tracks with metadata
- Extract by track index, language, forced/hearing impaired filters
- Merge multiple subtitle files
- Support for all ffmpeg formats (not just MKV)

Public API (deprecated):
    - extract_subtitles: Extract subtitles from an MKV file to SRT format
    - extract_all_subtitles: Extract all subtitle tracks from an MKV file
    - clean_srt_content: Remove ASS/SSA formatting tags from SRT content
"""
import argparse
import sys
from pathlib import Path
from typing import List, Optional

# Import from subtitle_tracks for backward compatibility
try:
    from .subtitle_tracks import (
        extract_track,
        extract_all_tracks,
        clean_srt_content,
        list_tracks,
    )
except ImportError:
    # Running as a script, use absolute import
    from subtitle_tracks import (
        extract_track,
        extract_all_tracks,
        clean_srt_content,
        list_tracks,
    )

__all__ = ["extract_subtitles", "extract_all_subtitles", "clean_srt_content"]


def extract_subtitles(mkv_file: Path, language: Optional[str] = None, output_file: Optional[Path] = None) -> Path:
    """
    Extract subtitles from an MKV file using ffmpeg.
    
    DEPRECATED: Use subtitle_tracks.extract_track() instead.
    
    Args:
        mkv_file: Path to the input MKV file
        language: Language code to filter subtitles (optional)
        output_file: Path to output SRT file (optional)
        
    Returns:
        Path to the extracted SRT file
        
    Raises:
        FileNotFoundError: If MKV file not found
        ValueError: If no matching subtitle track found
        RuntimeError: If ffmpeg fails
    """
    print("Warning: extract_subtitles() is deprecated. Use subtitle_tracks.extract_track() instead.")
    
    # Use the new subtitle_tracks module internally
    return extract_track(
        video_file=mkv_file,
        language=language,
        output_file=output_file
    )


def extract_all_subtitles(mkv_file: Path) -> List[Path]:
    """
    Extract all subtitle tracks from MKV file and save each to a separate SRT file.
    
    DEPRECATED: Use subtitle_tracks.extract_all_tracks() instead.
    
    Args:
        mkv_file: Path to the input MKV file
        
    Returns:
        List of paths to extracted SRT files
    """
    print("Warning: extract_all_subtitles() is deprecated. Use subtitle_tracks.extract_all_tracks() instead.")
    
    # Use the new subtitle_tracks module internally
    srt_files, _ = extract_all_tracks(video_file=mkv_file, as_zip=False)
    
    # Clean formatting tags from all extracted files (preserve old behavior)
    for srt_file in srt_files:
        try:
            with open(srt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            cleaned_content = clean_srt_content(content)
            with open(srt_file, 'w', encoding='utf-8') as f:
                f.write(cleaned_content)
            print(f"Cleaned formatting tags from {srt_file}")
        except Exception as e:
            print(f"Error processing {srt_file}: {e}")
    
    return srt_files


def check_ffmpeg() -> bool:
    """Check if ffmpeg is installed and provide helpful error messages if not.

    DEPRECATED: Use subtitle_tracks.check_ffmpeg() instead.
    """
    print("Warning: check_ffmpeg() is deprecated. Use subtitle_tracks.check_ffmpeg() instead.")
    try:
        from .subtitle_tracks import check_ffmpeg as _check_ffmpeg
    except ImportError:
        from subtitle_tracks import check_ffmpeg as _check_ffmpeg
    return _check_ffmpeg()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract subtitles from MKV files and convert to SRT format (DEPRECATED - use subtitle_tracks instead)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
DEPRECATED: This tool is deprecated. Please use 'subtitle-tracks' instead:

  # List all subtitle tracks
  subtitle-tracks list video.mkv

  # Extract English subtitles
  subtitle-tracks extract video.mkv --language en

  # Extract all tracks
  subtitle-tracks extract video.mkv --all

Examples:
  %(prog)s --input video.mkv
  %(prog)s --input video.mkv --language en
  %(prog)s --input video.mkv --output subtitles.srt
        """
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
    
    # Print deprecation warning
    print("Warning: mkv2srt.py is deprecated. Please use subtitle_tracks.py instead.")
    print("See: subtitle-tracks --help\n")
    
    # Validate input file
    if not args.input.is_file():
        sys.exit(f"Error: Input file does not exist: {args.input}")
    
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
                print(f"Successfully extracted {len(srt_files)} subtitle track(s):")
                for file in srt_files:
                    print(f"  - {file}")
            else:
                print("No subtitle tracks were extracted.")
        
    except Exception as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
