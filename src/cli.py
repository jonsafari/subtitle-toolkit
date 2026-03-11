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


def run_timeshift(args: List[str]) -> int:
    """Run the timeshift.py script."""
    script_path = get_script_dir() / "timeshift.py"
    cmd = [sys.executable, str(script_path)] + args
    return subprocess.run(cmd).returncode


def run_mkv2srt(args: List[str]) -> int:
    """Run the mkv2srt.py script."""
    script_path = get_script_dir() / "mkv2srt.py"
    cmd = [sys.executable, str(script_path)] + args
    return subprocess.run(cmd).returncode


def run_web(args: List[str]) -> int:
    """Run the web interface."""
    script_path = get_script_dir() / "web" / "app.py"
    cmd = [sys.executable, str(script_path)] + args
    return subprocess.run(cmd).returncode


def main() -> None:
    if len(sys.argv) < 2:
        parser = argparse.ArgumentParser(
            prog="subtitle-tk",
            description="Subtitle Toolkit - A collection of utilities for working with subtitle files",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Commands:
    translate   Translate subtitles using AI
    timeshift   Shift timestamps in SRT files
    mkv2srt     Extract subtitles from MKV files
    web         Start the web interface

Examples:
    subtitle-tk translate input.srt --instructions instructions.txt
    subtitle-tk timeshift --shift-seconds 2.5 < input.srt > output.srt
    subtitle-tk mkv2srt --input video.mkv --language en
    subtitle-tk web --host 0.0.0.0 --port 8000
        """
        )
        parser.print_help()
        sys.exit(0)
    
    command = sys.argv[1]
    
    if command in ["-h", "--help"]:
        parser = argparse.ArgumentParser(
            prog="subtitle-tk",
            description="Subtitle Toolkit - A collection of utilities for working with subtitle files",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Commands:
    translate   Translate subtitles using AI
    timeshift   Shift timestamps in SRT files
    mkv2srt     Extract subtitles from MKV files
    web         Start the web interface

Examples:
    subtitle-tk translate input.srt --instructions instructions.txt
    subtitle-tk timeshift --shift-seconds 2.5 < input.srt > output.srt
    subtitle-tk mkv2srt --input video.mkv --language en
    subtitle-tk web --host 0.0.0.0 --port 8000
        """
        )
        parser.print_help()
        sys.exit(0)
    
    if command not in ["translate", "timeshift", "mkv2srt", "web"]:
        parser = argparse.ArgumentParser(
            prog="subtitle-tk",
            description="Subtitle Toolkit - A collection of utilities for working with subtitle files"
        )
        parser.add_argument("command", nargs="?", choices=["translate", "timeshift", "mkv2srt", "web"])
        parser.print_help()
        sys.exit(1)
    
    remaining_args = sys.argv[2:]
    
    if command == "translate":
        sys.exit(run_translate(remaining_args))
    elif command == "timeshift":
        sys.exit(run_timeshift(remaining_args))
    elif command == "mkv2srt":
        sys.exit(run_mkv2srt(remaining_args))
    elif command == "web":
        sys.exit(run_web(remaining_args))


if __name__ == "__main__":
    main()
