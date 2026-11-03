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


def run_check(args: List[str]) -> int:
    """Run the synccheck.py script."""
    script_path = get_script_dir() / "synccheck.py"
    cmd = [sys.executable, str(script_path)] + args
    return subprocess.run(cmd).returncode


def run_preview(args: List[str]) -> int:
    """Open the Sync Preview web UI with a video and SRT pre-loaded."""
    import argparse
    import socket
    import time
    import urllib.parse
    import webbrowser

    parser = argparse.ArgumentParser(
        prog="subtitle-tk preview",
        description="Open the Sync Preview web UI with a video and subtitle file pre-loaded, "
                    "then adjust offset/drift live and export a fixed SRT.",
    )
    parser.add_argument("video", help="Path to the video file")
    parser.add_argument("srt", help="Path to the subtitle file (.srt)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to serve on (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to serve on (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser window")
    parsed = parser.parse_args(args)

    video = Path(parsed.video).expanduser().resolve()
    srt = Path(parsed.srt).expanduser().resolve()
    if not video.exists():
        print(f"Error: video not found: {video}", file=sys.stderr)
        return 1
    if not srt.exists():
        print(f"Error: subtitle file not found: {srt}", file=sys.stderr)
        return 1

    url = (f"http://{parsed.host}:{parsed.port}/sync-preview"
           f"?video={urllib.parse.quote(str(video))}"
           f"&srt={urllib.parse.quote(str(srt))}")

    def port_open() -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((parsed.host, parsed.port)) == 0

    server = None
    if not port_open():
        app_path = get_script_dir() / "web" / "app.py"
        server = subprocess.Popen(
            [sys.executable, str(app_path), "--host", parsed.host, "--port", str(parsed.port)])
        for _ in range(120):
            if port_open():
                break
            time.sleep(0.25)
        if not port_open():
            server.terminate()
            server.wait()
            print("Error: web server did not start.", file=sys.stderr)
            return 1
        print(f"Started web server (pid {server.pid}); press Ctrl+C to stop.")
    else:
        print("Using the web server already running on this port.")

    print(f"Open in your browser: {url}")
    if not parsed.no_browser:
        webbrowser.open(url)

    try:
        if server is not None:
            server.wait()
    except KeyboardInterrupt:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
    return 0


def get_help_epilog() -> str:
    """Get the help epilog text."""
    return """
Commands:
    translate        Translate subtitles using AI
    translate-batch  Batch translate multiple subtitle files in a directory
    timeshift        Shift timestamps in SRT files (uniform shift)
    autosync         Apply drift correction to subtitles (time-varying offset)
    check            Diagnose out-of-sync subtitles (offset, drift, wrong version)
    preview          Open the live Sync Preview web UI with files pre-loaded
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
    subtitle-tk check movie.mkv subtitles.srt
    subtitle-tk check movie.mkv subtitles.srt --json
    subtitle-tk preview movie.mkv subtitles.srt
    subtitle-tk preview movie.mkv subtitles.srt --port 8080 --no-browser
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
    
    if command not in ["translate", "translate-batch", "timeshift", "subtitle-tracks", "convert", "autosync", "check", "preview", "web"]:
        parser = argparse.ArgumentParser(
            prog="subtitle-tk",
            description="Subtitle Toolkit - A collection of utilities for working with subtitle files"
        )
        parser.add_argument("command", nargs="?", choices=["translate", "translate-batch", "timeshift", "subtitle-tracks", "convert", "autosync", "check", "preview", "web"])
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
    elif command == "check":
        sys.exit(run_check(remaining_args))
    elif command == "preview":
        sys.exit(run_preview(remaining_args))
    elif command == "web":
        sys.exit(run_web(remaining_args))


if __name__ == "__main__":
    main()
