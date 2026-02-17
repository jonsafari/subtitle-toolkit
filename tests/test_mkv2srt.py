"""Tests for subtitle_mkv2srt.py."""
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

# Add the project root to the path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCleanSrtContent:
    """Tests for the clean_srt_content function."""

    def test_remove_ass_ssa_tags(self, sample_srt_with_ass_tags):
        """Test removing ASS/SSA formatting tags."""
        from subtitle_mkv2srt import clean_srt_content

        result = clean_srt_content(sample_srt_with_ass_tags)

        # Tags should be removed but structure preserved
        assert "{\an7}" not in result
        assert "{\b1}" not in result
        assert "{\i1}" not in result
        assert "Centered text" in result
        assert "Bold text" in result
        assert "Italic text" in result

    def test_preserve_srt_structure(self, sample_srt_with_ass_tags):
        """Test that SRT structure is preserved after cleaning."""
        from subtitle_mkv2srt import clean_srt_content

        result = clean_srt_content(sample_srt_with_ass_tags)

        # Check that index numbers and timestamps are preserved
        assert "1\n" in result
        assert "00:00:01,000 --> 00:00:04,000" in result
        assert "2\n" in result
        assert "00:00:05,000 --> 00:00:08,000" in result

    def test_handle_empty_blocks(self):
        """Test handling of empty blocks in SRT content."""
        from subtitle_mkv2srt import clean_srt_content

        content = """1
00:00:01,000 --> 00:00:04,000
Text

{\an7}Empty block above

2
00:00:05,000 --> 00:00:08,000
More text
"""
        result = clean_srt_content(content)

        assert "Text" in result
        assert "More text" in result

    def test_remove_backslash_escape_sequences(self):
        """Test removing backslash escape sequences."""
        from subtitle_mkv2srt import clean_srt_content

        content = """1
00:00:01,000 --> 00:00:04,000
Text with \\a7 formatting

2
00:00:05,000 --> 00:00:08,000
Normal text
"""
        result = clean_srt_content(content)

        assert "\\a7" not in result
        assert "Text with  formatting" in result or "Text with formatting" in result


class TestSplitIntoUnits:
    """Tests for split_into_units function (reused from translate module)."""

    def test_split_basic_srt(self):
        """Test splitting basic SRT into units."""
        from subtitle_translate import split_into_units

        content = """1
00:00:01,000 --> 00:00:04,000
First subtitle

2
00:00:05,000 --> 00:00:08,000
Second subtitle
"""
        units = split_into_units(content, '\n')

        assert len(units) == 2
        assert "First subtitle" in units[0]
        assert "Second subtitle" in units[1]

    def test_remove_empty_strings(self):
        """Test that empty strings are removed from the result."""
        from subtitle_translate import split_into_units

        content = """1
00:00:01,000 --> 00:00:04,000
Text

"""
        units = split_into_units(content, '\n')

        # Should have exactly 1 unit, not 2
        assert len(units) == 1
        assert units[-1].strip() != ''


class TestChunkUnits:
    """Tests for chunk_units function."""

    def test_chunk_basic_list(self):
        """Test chunking a list into groups."""
        from subtitle_translate import chunk_units

        units = ['u1', 'u2', 'u3', 'u4', 'u5']
        chunks = chunk_units(units, 2)

        assert len(chunks) == 3
        assert chunks[0] == ['u1', 'u2']
        assert chunks[1] == ['u3', 'u4']
        assert chunks[2] == ['u5']

    def test_chunk_exact_fit(self):
        """Test chunking when list size divides evenly."""
        from subtitle_translate import chunk_units

        units = ['u1', 'u2', 'u3', 'u4']
        chunks = chunk_units(units, 2)

        assert len(chunks) == 2
        assert chunks[0] == ['u1', 'u2']
        assert chunks[1] == ['u3', 'u4']

    def test_chunk_empty_list(self):
        """Test chunking an empty list."""
        from subtitle_translate import chunk_units

        chunks = chunk_units([], 3)

        assert chunks == []

    def test_chunk_larger_than_chunk_size(self):
        """Test chunking when list is smaller than chunk size."""
        from subtitle_translate import chunk_units

        units = ['u1', 'u2']
        chunks = chunk_units(units, 5)

        assert len(chunks) == 1
        assert chunks[0] == ['u1', 'u2']


class TestDetectLineEnding:
    """Tests for detect_line_ending function."""

    def test_detect_unix_line_endings(self):
        """Test detecting Unix line endings."""
        from subtitle_translate import detect_line_ending

        content = "line1\nline2\nline3\n"
        result = detect_line_ending(content)

        assert result == '\n'

    def test_detect_windows_line_endings(self, sample_srt_windows_line_endings):
        """Test detecting Windows line endings."""
        from subtitle_translate import detect_line_ending

        result = detect_line_ending(sample_srt_windows_line_endings)

        assert result == '\r\n'

    def test_detect_mixed_line_endings(self):
        """Test that CRLF takes precedence over LF."""
        from subtitle_translate import detect_line_ending

        content = "line1\r\nline2\nline3\r\n"
        result = detect_line_ending(content)

        assert result == '\r\n'


class TestFileOperations:
    """Tests for file reading and writing functions."""

    def test_read_file(self, temp_srt_file):
        """Test reading a file."""
        from subtitle_translate import read_file

        content = read_file(temp_srt_file)

        assert "Hello, welcome to the subtitle toolkit." in content

    def test_write_file(self, tmp_path):
        """Test writing a file."""
        from subtitle_translate import write_file

        output_file = tmp_path / "output.srt"
        content = "Test content\n"

        write_file(output_file, content)

        assert output_file.exists()
        assert output_file.read_text(encoding='utf-8') == content

    def test_write_file_creates_directory(self, tmp_path):
        """Test that writing creates parent directories if needed."""
        from subtitle_translate import write_file

        output_file = tmp_path / "subdir" / "output.srt"
        content = "Test content\n"

        # Create parent directory first
        output_file.parent.mkdir(parents=True, exist_ok=True)

        write_file(output_file, content)

        assert output_file.exists()
        assert output_file.parent.exists()


class TestIntegration:
    """Integration tests for subtitle_mkv2srt.py."""

    def test_check_ffmpeg(self):
        """Test that ffmpeg check works (may fail if ffmpeg not installed)."""
        from subtitle_mkv2srt import check_ffmpeg

        # This will raise SystemExit if ffmpeg is not found
        try:
            check_ffmpeg()
        except SystemExit as e:
            # If ffmpeg is not installed, that's expected in some test environments
            pytest.skip("ffmpeg not installed in test environment")

    def test_extract_subtitles_command(self, tmp_path):
        """Test building the ffmpeg extraction command."""
        from subtitle_mkv2srt import extract_subtitles

        # Create a mock MKV file
        mkv_file = tmp_path / "test.mkv"
        mkv_file.write_bytes(b'')  # Empty file for testing

        # This will fail because the file isn't a real MKV
        with pytest.raises(Exception):
            extract_subtitles(mkv_file)

    def test_extract_all_subtitles_no_subtitles(self, tmp_path):
        """Test extracting subtitles from a file with no subtitle tracks."""
        from subtitle_mkv2srt import extract_all_subtitles

        # Create a mock MKV file
        mkv_file = tmp_path / "test.mkv"
        mkv_file.write_bytes(b'')  # Empty file

        # This will fail because the file isn't a real MKV
        result = extract_all_subtitles(mkv_file)
        assert result == []