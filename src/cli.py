#!/usr/bin/env python3
"""
CLI module - Unified command-line interface for the Subtitle Toolkit.

Public API:
    - main: Entry point for the subtitle-tk command
"""
import argparse
import subprocess
import sys
import os
from pathlib import Path
from typing import List

__all__ = ["main"]


def get_script_dir() -> Path:
    """Get the directory where this script is located."""
    return Path(__file__).parent.resolve()


def run_translate(args: List[str]) -> int:
    """Run the translate.py script."""
    script_path = get_script_dir() / "translate.py"
    cmd = [sys.executable, str(script_path)] + args
    return subprocess.run(cmd).returncode


def run_translate_batch(args: List[str]) -> int:
    """Run the translate_batch.py script."""
    script_path = get_script_dir() / "translate_batch.py"
    cmd = [sys.executable, str(script_path)] + args
    return subprocess.run(cmd).returncode


def run_timeshift(args: List[str]) -> int:
    """Run the timeshift.py script."""
    script_path = get_script_dir() / "timeshift.py"
    cmd = [sys.executable, str(script_path)] + args
    return subprocess.run(cmd).returncode


def run_subtitle_tracks(args: List[str]) -> int:
    """Run the subtitle_tracks.py script."""
    script_path = get_script_dir() / "subtitle_tracks.py"
    cmd = [sys.executable, str(script_path)] + args
    return subprocess.run(cmd).returncode


def run_web(args: List[str]) -> int:
    """Run the web interface."""
    script_path = get_script_dir() / "web" / "app.py"
    cmd = [sys.executable, str(script_path)] + args
    return subprocess.run(cmd).returncode


def run_convert(args: List[str]) -> int:
    """Run the convert.py script."""
    script_path = get_script_dir() / "convert.py"
    cmd = [sys.executable, str(script_path)] + args
    return subprocess.run(cmd).returncode


def run_autosync(args: List[str]) -> int:
    """Run the autosync.py script."""
    script_path = get_script_dir() / "autosync.py"
    cmd = [sys.executable, str(script_path)] + args
    return subprocess.run(cmd).returncode


def get_help_epilog() -> str:
    """Get the help epilog text."""
    return """
Commands:
    translate        Translate subtitles using AI
    translate-batch  Batch translate multiple subtitle files in a directory
    timeshift        Shift timestamps in SRT files (uniform shift)
    autosync         Apply drift correction to subtitles (time-varying offset)
    subtitle-tracks  Manage subtitle tracks - list, extract, merge
    convert          Convert subtitles between formats (SRT, VTT, ASS, TTML, etc.)
    web              Start the web interface

Examples:
    subtitle-tk translate input.srt --instructions instructions.txt
    subtitle-tk translate-batch /path/to/season --source-lang en --target-lang es
    subtitle-tk translate-batch /path/to/season --source-lang en --target-lang es --recursive --dry-run
    subtitle-tk timeshift --shift-seconds 2.5 < input.srt > output.srt
    subtitle-tk autosync --correct-at 00:00:30 --offset-at 00:10:00 --offset 5.0 < input.srt
    subtitle-tk autosync --point 00:00:30:0 00:05:00:2.5 00:10:00:5.0 < input.srt
    subtitle-tk subtitle-tracks list video.mkv
    subtitle-tk subtitle-tracks extract video.mkv --language eng
    subtitle-tk subtitle-tracks extract video.mkv --all --as-zip
    subtitle-tk subtitle-tracks merge subs1.srt subs2.srt -o merged.srt
    subtitle-tk convert input.srt --output-format vtt -o output.vtt
    subtitle-tk web --host 0.0.0.0 --port 8000
        """


def main() -> None:
    if len(sys.argv) < 2:
        parser = argparse.ArgumentParser(
            prog="subtitle-tk",
            description="Subtitle Toolkit - A collection of utilities for working with subtitle files",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=get_help_epilog()
        )
        parser.print_help()
        sys.exit(0)
    
    command = sys.argv[1]
    
    if command in ["-h", "--help"]:
        parser = argparse.ArgumentParser(
            prog="subtitle-tk",
            description="Subtitle Toolkit - A collection of utilities for working with subtitle files",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=get_help_epilog()
        )
        parser.print_help()
        sys.exit(0)
    
    if command not in ["translate", "translate-batch", "timeshift", "subtitle-tracks", "convert", "autosync", "web"]:
        parser = argparse.ArgumentParser(
            prog="subtitle-tk",
            description="Subtitle Toolkit - A collection of utilities for working with subtitle files"
        )
        parser.add_argument("command", nargs="?", choices=["translate", "translate-batch", "timeshift", "subtitle-tracks", "convert", "autosync", "web"])
        parser.print_help()
        sys.exit(1)
    
    remaining_args = sys.argv[2:]
    
    if command == "translate":
        sys.exit(run_translate(remaining_args))
    elif command == "translate-batch":
        sys.exit(run_translate_batch(remaining_args))
    elif command == "timeshift":
        sys.exit(run_timeshift(remaining_args))
    elif command == "subtitle-tracks":
        sys.exit(run_subtitle_tracks(remaining_args))
    elif command == "convert":
        sys.exit(run_convert(remaining_args))
    elif command == "autosync":
        sys.exit(run_autosync(remaining_args))
    elif command == "web":
        sys.exit(run_web(remaining_args))


if __name__ == "__main__":
    main()
