"""
Subtitle Toolkit - A collection of utilities for working with subtitle files.

This package provides utilities for:
    - Time‑shifting subtitle timestamps
    - Translating subtitles using AI models
    - Extracting subtitles from MKV files

Example usage:
    from src.timeshift import shift_timestamp, timestamp_to_seconds
    from src.translate import split_into_units, chunk_units
    from src.mkv2srt import extract_subtitles, clean_srt_content
"""

# Package version – kept in sync with pyproject.toml
__version__: str = "0.9.5"

__all__ = [
    # Timeshift functions
    "shift_timestamp",
    "timestamp_to_seconds",
    # Translate functions
    "detect_line_ending",
    "read_file",
    "write_file",
    "split_into_units",
    "chunk_units",
    # MKV2SRT functions
    "extract_subtitles",
    "extract_all_subtitles",
    "clean_srt_content",
    # Version
    "__version__",
]

# Import public API from submodules
from .timeshift import shift_timestamp, timestamp_to_seconds
from .translate import (
    detect_line_ending,
    read_file,
    write_file,
    split_into_units,
    chunk_units,
)
from .mkv2srt import extract_subtitles, extract_all_subtitles, clean_srt_content
