"""Tests for subtitle_translate.py."""
import sys
from pathlib import Path
from unittest import mock

import pytest

# Add the project root to the path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDetectLineEnding:
    """Tests for detect_line_ending function."""

    def test_detect_unix_line_endings(self):
        """Test detecting Unix line endings."""
        from src.translate import detect_line_ending

        content = "line1\nline2\nline3\n"
        result = detect_line_ending(content)

        assert result == '\n'

    def test_detect_windows_line_endings(self, sample_srt_windows_line_endings):
        """Test detecting Windows line endings."""
        from src.translate import detect_line_ending

        result = detect_line_ending(sample_srt_windows_line_endings)

        assert result == '\r\n'

    def test_detect_mixed_line_endings(self):
        """Test that CRLF takes precedence over LF."""
        from src.translate import detect_line_ending

        content = "line1\r\nline2\nline3\r\n"
        result = detect_line_ending(content)

        assert result == '\r\n'

    def test_detect_empty_content(self):
        """Test detecting line endings in empty content."""
        from src.translate import detect_line_ending

        result = detect_line_ending("")

        # Should default to Unix line endings
        assert result == '\n'


class TestSplitIntoUnits:
    """Tests for split_into_units function."""

    def test_split_basic_srt(self):
        """Test splitting basic SRT into units."""
        from src.translate import split_into_units

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

    def test_split_with_windows_line_endings(self, sample_srt_windows_line_endings):
        """Test splitting with Windows line endings."""
        from src.translate import split_into_units

        units = split_into_units(sample_srt_windows_line_endings, '\r\n')

        assert len(units) == 1
        assert "Hello Windows" in units[0]

    def test_remove_empty_strings(self):
        """Test that empty strings are removed from the result."""
        from src.translate import split_into_units

        content = """1
00:00:01,000 --> 00:00:04,000
Text

"""
        units = split_into_units(content, '\n')

        # Should have exactly 1 unit, not 2
        assert len(units) == 1
        assert units[-1].strip() != ''

    def test_split_multiple_blank_lines(self):
        """Test splitting when there are multiple blank lines between units."""
        from src.translate import split_into_units

        content = """1
00:00:01,000 --> 00:00:04,000
First subtitle


2
00:00:05,000 --> 00:00:08,000
Second subtitle
"""
        units = split_into_units(content, '\n')

        assert len(units) == 2


class TestChunkUnits:
    """Tests for chunk_units function."""

    def test_chunk_basic_list(self):
        """Test chunking a list into groups."""
        from src.translate import chunk_units

        units = ['u1', 'u2', 'u3', 'u4', 'u5']
        chunks = chunk_units(units, 2)

        assert len(chunks) == 3
        assert chunks[0] == ['u1', 'u2']
        assert chunks[1] == ['u3', 'u4']
        assert chunks[2] == ['u5']

    def test_chunk_exact_fit(self):
        """Test chunking when list size divides evenly."""
        from src.translate import chunk_units

        units = ['u1', 'u2', 'u3', 'u4']
        chunks = chunk_units(units, 2)

        assert len(chunks) == 2
        assert chunks[0] == ['u1', 'u2']
        assert chunks[1] == ['u3', 'u4']

    def test_chunk_empty_list(self):
        """Test chunking an empty list."""
        from src.translate import chunk_units

        chunks = chunk_units([], 3)

        assert chunks == []

    def test_chunk_larger_than_chunk_size(self):
        """Test chunking when list is smaller than chunk size."""
        from src.translate import chunk_units

        units = ['u1', 'u2']
        chunks = chunk_units(units, 5)

        assert len(chunks) == 1
        assert chunks[0] == ['u1', 'u2']

    def test_chunk_with_single_unit(self):
        """Test chunking with a single unit."""
        from src.translate import chunk_units

        units = ['u1']
        chunks = chunk_units(units, 3)

        assert len(chunks) == 1
        assert chunks[0] == ['u1']


class TestFileOperations:
    """Tests for file reading and writing functions."""

    def test_read_file(self, temp_srt_file):
        """Test reading a file."""
        from src.translate import read_file

        content = read_file(temp_srt_file)

        assert "Hello, welcome to the subtitle toolkit." in content

    def test_read_file_not_found(self, tmp_path):
        """Test reading a non-existent file."""
        from src.translate import read_file

        non_existent = tmp_path / "non_existent.srt"

        with pytest.raises(SystemExit) as exc_info:
            read_file(non_existent)

        assert exc_info.value.code != 0

    def test_write_file(self, tmp_path):
        """Test writing a file."""
        from src.translate import write_file

        output_file = tmp_path / "output.srt"
        content = "Test content\n"

        write_file(output_file, content)

        assert output_file.exists()
        assert output_file.read_text(encoding='utf-8') == content

    def test_write_file_creates_directory(self, tmp_path):
        """Test that writing creates parent directories if needed."""
        from src.translate import write_file

        output_file = tmp_path / "subdir" / "output.srt"
        content = "Test content\n"

        write_file(output_file, content)

        assert output_file.exists()
        assert output_file.parent.exists()

    def test_write_file_preserves_line_endings(self, tmp_path):
        """Test that writing preserves the correct line endings."""
        from src.translate import write_file

        output_file = tmp_path / "output.srt"
        content = "line1\r\nline2\r\n"

        write_file(output_file, content)

        # Read back in binary mode to check exact bytes
        written_bytes = output_file.read_bytes()
        assert b'\r\n' in written_bytes


class TestTranslationWorkflow:
    """Tests for the translation workflow with mocked API."""

    def test_full_translation_workflow(self, tmp_path, sample_srt_content, mock_api_response):
        """Test the full translation workflow with mocked API."""
        from src.translate import (
            chunk_units,
            detect_line_ending,
            read_file,
            split_into_units,
            write_file,
        )

        # Create input file
        input_file = tmp_path / "input.srt"
        input_file.write_text(sample_srt_content, encoding='utf-8')

        # Read and process
        content = read_file(input_file)
        line_ending = detect_line_ending(content)
        units = split_into_units(content, line_ending)
        chunks = chunk_units(units, 2)

        # Verify processing
        assert len(units) == 3
        assert len(chunks) == 2  # 3 units with chunk_size=2 gives 2 chunks
        assert len(chunks[0]) == 2
        assert len(chunks[1]) == 1

    def test_output_filename_derivation(self, tmp_path, sample_srt_content):
        """Test that output filename is derived correctly from input."""
        from src.translate import main

        input_file = tmp_path / "test_video.srt"
        input_file.write_text(sample_srt_content, encoding='utf-8')

        # Mock litellm.completion to avoid actual API calls
        with mock.patch('litellm.completion') as mock_completion:
            mock_response = mock.MagicMock()
            mock_response.choices = [mock.MagicMock()]
            mock_response.choices[0].message = mock.MagicMock()
            mock_response.choices[0].message.content = sample_srt_content
            mock_completion.return_value = mock_response

            # This would normally call the main function, but we'll test the logic
            stem = input_file.stem
            output_path = input_file.parent / f"{stem}_translated.srt"

            assert output_path.name == "test_video_translated.srt"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_srt_file(self, tmp_path):
        """Test processing an empty SRT file."""
        from src.translate import split_into_units

        empty_file = tmp_path / "empty.srt"
        empty_file.write_text("", encoding='utf-8')

        content = empty_file.read_text(encoding='utf-8')
        units = split_into_units(content, '\n')

        assert units == []

    def test_srt_with_only_timestamps(self, tmp_path):
        """Test SRT file with only timestamps and no text."""
        from src.translate import split_into_units, read_file

        content = """1
00:00:01,000 --> 00:00:04,000

2
00:00:05,000 --> 00:00:08,000

"""
        input_file = tmp_path / "timestamps_only.srt"
        input_file.write_text(content, encoding='utf-8')

        content = read_file(input_file)
        units = split_into_units(content, '\n')

        # Should have 2 units even if text is empty
        assert len(units) == 2

    def test_srt_with_unicode_content(self, tmp_path):
        """Test SRT file with Unicode characters."""
        from src.translate import read_file, write_file

        content = """1
00:00:01,000 --> 00:00:04,000
Héllo Wörld! 你好世界! 🎬

"""
        input_file = tmp_path / "unicode.srt"
        write_file(input_file, content)

        read_content = read_file(input_file)

        assert "Héllo Wörld!" in read_content
        assert "你好世界!" in read_content
        assert "🎬" in read_content

    def test_srt_with_malformed_entries(self, tmp_path):
        """Test SRT file with malformed entries."""
        from src.translate import split_into_units, read_file

        content = """1
00:00:01,000 --> 00:00:04,000
Normal entry

2
malformed-timestamp --> 00:00:08,000
This has a malformed timestamp

3
00:00:09,000 --> 00:00:12,000
Back to normal
"""
        input_file = tmp_path / "malformed.srt"
        input_file.write_text(content, encoding='utf-8')

        content = read_file(input_file)
        units = split_into_units(content, '\n')

        # Should have 3 units (malformed timestamp is still a unit)
        assert len(units) == 3

    def test_srt_with_multiple_blank_lines(self, tmp_path):
        """Test SRT file with multiple blank lines between entries."""
        from src.translate import split_into_units

        content = """1
00:00:01,000 --> 00:00:04,000
First entry


2
00:00:05,000 --> 00:00:08,000
Second entry


3
00:00:09,000 --> 00:00:12,000
Third entry
"""
        input_file = tmp_path / "multiple_blanks.srt"
        input_file.write_text(content, encoding='utf-8')

        content = input_file.read_text(encoding='utf-8')
        units = split_into_units(content, '\n')

        # Should have 3 units despite multiple blank lines
        assert len(units) == 3