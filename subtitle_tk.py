#!/usr/bin/env python3
"""
subtitle-tk - A unified command-line interface for the Subtitle Toolkit

Usage:
    subtitle-tk <command> [options]

Commands:
    translate   Translate subtitles using AI
    timeshift   Shift timestamps in SRT files
    mkv2srt     Extract subtitles from MKV files

Options:
    -h, --help  Show this help message

Examples:
    subtitle-tk translate input.srt --instructions instructions.txt
    subtitle-tk timeshift --shift-seconds 2.5 < input.srt > output.srt
    subtitle-tk mkv2srt --input video.mkv --language en
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path


def get_script_dir() -> Path:
    """Get the directory where this script is located."""
    return Path(__file__).parent.resolve()


def run_translate(args: list) -> int:
    """Run the subtitle_translate.py script."""
    script_path = get_script_dir() / "subtitle_translate.py"
    cmd = [sys.executable, str(script_path)] + args
    return subprocess.run(cmd).returncode


def run_timeshift(args: list) -> int:
    """Run the subtitle_timeshift.py script."""
    script_path = get_script_dir() / "subtitle_timeshift.py"
    cmd = [sys.executable, str(script_path)] + args
    return subprocess.run(cmd).returncode


def run_mkv2srt(args: list) -> int:
    """Run the subtitle_mkv2srt.py script."""
    script_path = get_script_dir() / "subtitle_mkv2srt.py"
    cmd = [sys.executable, str(script_path)] + args
    return subprocess.run(cmd).returncode


def main():
    if len(sys.argv) < 2:
        parser = argparse.ArgumentParser(
            prog="subtitle-tk",
            description="Subtitle Toolkit - A unified CLI for subtitle operations",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Commands:
    translate   Translate subtitles using AI
    timeshift   Shift timestamps in SRT files
    mkv2srt     Extract subtitles from MKV files

Examples:
    subtitle-tk translate input.srt --instructions instructions.txt
    subtitle-tk timeshift --shift-seconds 2.5 < input.srt > output.srt
    subtitle-tk mkv2srt --input video.mkv --language en
        """
        )
        parser.print_help()
        sys.exit(0)
    
    command = sys.argv[1]
    
    if command in ["-h", "--help"]:
        parser = argparse.ArgumentParser(
            prog="subtitle-tk",
            description="Subtitle Toolkit - A unified CLI for subtitle operations",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Commands:
    translate   Translate subtitles using AI
    timeshift   Shift timestamps in SRT files
    mkv2srt     Extract subtitles from MKV files

Examples:
    subtitle-tk translate input.srt --instructions instructions.txt
    subtitle-tk timeshift --shift-seconds 2.5 < input.srt > output.srt
    subtitle-tk mkv2srt --input video.mkv --language en
        """
        )
        parser.print_help()
        sys.exit(0)
    
    if command not in ["translate", "timeshift", "mkv2srt"]:
        parser = argparse.ArgumentParser(
            prog="subtitle-tk",
            description="Subtitle Toolkit - A unified CLI for subtitle operations"
        )
        parser.add_argument("command", nargs="?", choices=["translate", "timeshift", "mkv2srt"])
        parser.print_help()
        sys.exit(1)
    
    remaining_args = sys.argv[2:]
    
    if command == "translate":
        sys.exit(run_translate(remaining_args))
    elif command == "timeshift":
        sys.exit(run_timeshift(remaining_args))
    elif command == "mkv2srt":
        sys.exit(run_mkv2srt(remaining_args))


if __name__ == "__main__":
    main()