#!/usr/bin/env python3
"""
Unit tests for the subtitle format converter module.
"""
import pytest
import tempfile
from pathlib import Path

# Import the convert module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from convert import convert_subtitle, get_supported_input_formats, get_supported_output_formats


# Sample subtitle content in different formats
SAMPLE_SRT = """1
00:00:00,000 --> 00:00:02,000
Hello world

2
00:00:02,000 --> 00:00:04,000
This is a test
"""

SAMPLE_VTT = """WEBVTT

1
00:00:00.000 --> 00:00:02.000
Hello world

2
00:00:02.000 --> 00:00:04.000
This is a test
"""

SAMPLE_SRT_WITH_HTML = """1
00:00:00,000 --> 00:00:02,000
Hello  &amp;   world

2
00:00:02,000 --> 00:00:04,000
Test  with   spaces
"""


class TestFormatLists:
    """Test that format lists are populated correctly."""

    def test_input_formats_not_empty(self):
        """Test that input formats list is not empty."""
        formats = get_supported_input_formats()
        assert len(formats) > 0
        assert "srt" in formats
        assert "vtt" in formats

    def test_output_formats_not_empty(self):
        """Test that output formats list is not empty."""
        formats = get_supported_output_formats()
        assert len(formats) > 0
        assert "srt" in formats
        assert "vtt" in formats

    def test_common_formats_in_both(self):
        """Test that common formats are in both input and output lists."""
        input_formats = get_supported_input_formats()
        output_formats = get_supported_output_formats()
        
        common_formats = ["srt", "vtt", "ass", "ssa", "sub", "sbv", "txt"]
        for fmt in common_formats:
            assert fmt in input_formats, f"{fmt} should be in input formats"
            assert fmt in output_formats, f"{fmt} should be in output formats"


class TestConvertSubtitle:
    """Test the convert_subtitle function."""

    def test_srt_to_srt(self):
        """Test converting SRT to SRT (identity conversion)."""
        result = convert_subtitle(
            input_content=SAMPLE_SRT,
            output_format="srt",
            input_format="srt",
            preserve_formatting=True
        )
        result_str = result.decode('utf-8')
        assert "Hello world" in result_str
        assert "This is a test" in result_str

    def test_srt_to_vtt(self):
        """Test converting SRT to VTT."""
        result = convert_subtitle(
            input_content=SAMPLE_SRT,
            output_format="vtt",
            input_format="srt",
            preserve_formatting=True
        )
        result_str = result.decode('utf-8')
        assert "WEBVTT" in result_str
        assert "Hello world" in result_str
        # VTT uses dots instead of commas for milliseconds
        assert "00:00:00.000" in result_str

    def test_srt_to_json(self):
        """Test converting SRT to JSON."""
        result = convert_subtitle(
            input_content=SAMPLE_SRT,
            output_format="json",
            input_format="srt",
            preserve_formatting=True
        )
        result_str = result.decode('utf-8')
        assert "Hello world" in result_str
        assert "0.0" in result_str  # JSON uses numeric timestamps

    def test_vtt_to_srt(self):
        """Test converting VTT to SRT."""
        result = convert_subtitle(
            input_content=SAMPLE_VTT,
            output_format="srt",
            input_format="vtt",
            preserve_formatting=True
        )
        result_str = result.decode('utf-8')
        assert "Hello world" in result_str
        # SRT uses commas for milliseconds
        assert "00:00:00,000" in result_str

    def test_preserve_formatting(self):
        """Test that preserve_formatting=True keeps original formatting."""
        result = convert_subtitle(
            input_content=SAMPLE_SRT_WITH_HTML,
            output_format="srt",
            input_format="srt",
            preserve_formatting=True
        )
        result_str = result.decode('utf-8')
        # With preserve_formatting=True, HTML entities should be kept
        assert "&amp;" in result_str

    def test_normalize_text(self):
        """Test that preserve_formatting=False normalizes text."""
        result = convert_subtitle(
            input_content=SAMPLE_SRT_WITH_HTML,
            output_format="srt",
            input_format="srt",
            preserve_formatting=False
        )
        result_str = result.decode('utf-8')
        # With preserve_formatting=False, HTML entities should be decoded
        assert "&amp;" not in result_str
        assert "Hello & world" in result_str
        # Multiple spaces should be collapsed
        assert "  " not in result_str  # No double spaces

    def test_auto_detect_format(self):
        """Test auto-detection of input format (defaults to srt for string input)."""
        result = convert_subtitle(
            input_content=SAMPLE_SRT,
            output_format="vtt",
            input_format="auto",
            preserve_formatting=True
        )
        result_str = result.decode('utf-8')
        assert "WEBVTT" in result_str
        assert "Hello world" in result_str

    def test_explicit_srt_format(self):
        """Test explicit SRT format specification."""
        result = convert_subtitle(
            input_content=SAMPLE_SRT,
            output_format="vtt",
            input_format="srt",
            preserve_formatting=True
        )
        result_str = result.decode('utf-8')
        assert "WEBVTT" in result_str
        assert "Hello world" in result_str

    def test_invalid_output_format(self):
        """Test that invalid output format raises ValueError."""
        with pytest.raises(ValueError):
            convert_subtitle(
                input_content=SAMPLE_SRT,
                output_format="invalid_format",
                input_format="srt",
                preserve_formatting=True
            )

    def test_empty_input(self):
        """Test handling of empty input."""
        # Empty input might fail or produce minimal output depending on the library
        with pytest.raises((RuntimeError, ValueError)):
            convert_subtitle(
                input_content="",
                output_format="srt",
                input_format="srt",
                preserve_formatting=True
            )

    def test_write_to_file(self):
        """Test writing output to a file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            result = convert_subtitle(
                input_content=SAMPLE_SRT,
                output_format="srt",
                input_format="srt",
                preserve_formatting=True,
                output_path=tmp_path
            )
            # File should exist and contain the converted content
            assert tmp_path.exists()
            file_content = tmp_path.read_text(encoding='utf-8')
            assert "Hello world" in file_content
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_multiline_text(self):
        """Test handling of multiline subtitle text."""
        multiline_srt = """1
00:00:00,000 --> 00:00:02,000
Line one
Line two
Line three
"""
        result = convert_subtitle(
            input_content=multiline_srt,
            output_format="srt",
            input_format="srt",
            preserve_formatting=True
        )
        result_str = result.decode('utf-8')
        assert "Line one" in result_str
        assert "Line two" in result_str
        assert "Line three" in result_str

    def test_special_characters(self):
        """Test handling of special characters."""
        special_srt = """1
00:00:00,000 --> 00:00:02,000
Hello 世界 🌍
"""
        result = convert_subtitle(
            input_content=special_srt,
            output_format="srt",
            input_format="srt",
            preserve_formatting=True
        )
        result_str = result.decode('utf-8')
        assert "世界" in result_str
        assert "🌍" in result_str

    def test_long_timestamps(self):
        """Test handling of long timestamps (hours)."""
        long_srt = """1
01:30:45,123 --> 01:30:47,456
Long timestamp test
"""
        result = convert_subtitle(
            input_content=long_srt,
            output_format="srt",
            input_format="srt",
            preserve_formatting=True
        )
        result_str = result.decode('utf-8')
        assert "01:30:45,123" in result_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
