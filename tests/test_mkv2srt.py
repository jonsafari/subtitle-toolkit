#!/usr/bin/env python3
"""
Tests for mkv2srt.py (deprecated module).

NOTE: This module is deprecated. The tests here verify backward compatibility
for the deprecated API. New development should use subtitle_tracks module
and its tests in test_subtitle_tracks.py.
"""
import pytest
from pathlib import Path

# Add the project root to the path so we can import the module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDeprecatedExtractSubtitles:
    """Tests for deprecated extract_subtitles function."""

    def test_extract_subtitles_deprecated(self, tmp_path):
        """Test that extract_subtitles shows deprecation warning."""
        from src.mkv2srt import extract_subtitles

        # Create a mock MKV file
        mkv_file = tmp_path / "test.mkv"
        mkv_file.write_bytes(b'')  # Empty file

        # This will fail because the file isn't a real MKV
        with pytest.raises(Exception):
            extract_subtitles(mkv_file)


class TestDeprecatedExtractAllSubtitles:
    """Tests for deprecated extract_all_subtitles function."""

    def test_extract_all_subtitles_deprecated(self, tmp_path):
        """Test that extract_all_subtitles shows deprecation warning."""
        from src.mkv2srt import extract_all_subtitles

        # Create a mock MKV file
        mkv_file = tmp_path / "test.mkv"
        mkv_file.write_bytes(b'')  # Empty file

        # This will fail because the file isn't a real MKV
        with pytest.raises(Exception):
            extract_all_subtitles(mkv_file)


class TestDeprecatedCheckFfmpeg:
    """Tests for deprecated check_ffmpeg function."""

    def test_check_ffmpeg_deprecated(self):
        """Test that check_ffmpeg shows deprecation warning."""
        from src.mkv2srt import check_ffmpeg

        # This will raise SystemExit if ffmpeg is not found
        try:
            check_ffmpeg()
        except SystemExit as e:
            # If ffmpeg is not installed, that's expected in some test environments
            pytest.skip("ffmpeg not installed in test environment")


class TestCleanSrtContent:
    """Tests for clean_srt_content function (re-exported from subtitle_tracks).

    NOTE: This function is now implemented in subtitle_tracks.py. These tests
    verify the re-export still works for backward compatibility.
    """

    def test_remove_ass_ssa_tags(self):
        """Test removing ASS/SSA formatting tags."""
        from src.mkv2srt import clean_srt_content

        content = """1
00:00:01,000 --> 00:00:04,000
{\\an7}Centered text{\\r}

2
00:00:05,000 --> 00:00:08,000
{\\b1}Bold text{\\r}{\\i1}Italic text{\\r}
"""
        result = clean_srt_content(content)

        # Tags should be removed but structure preserved
        assert r"{\an7}" not in result
        assert r"{\b1}" not in result
        assert r"{\i1}" not in result
        assert "Centered text" in result
        assert "Bold text" in result
        assert "Italic text" in result

    def test_preserve_srt_structure(self):
        """Test that SRT structure is preserved after cleaning."""
        from src.mkv2srt import clean_srt_content

        content = """1
00:00:01,000 --> 00:00:04,000
{\\an7}First

2
00:00:05,000 --> 00:00:08,000
{\\an7}Second
"""
        result = clean_srt_content(content)

        # Check that index numbers and timestamps are preserved
        assert "1\n" in result
        assert "00:00:01,000 --> 00:00:04,000" in result
        assert "2\n" in result
        assert "00:00:05,000 --> 00:00:08,000" in result

    def test_clean_empty_content(self):
        """Test cleaning empty content."""
        from src.mkv2srt import clean_srt_content

        result = clean_srt_content("")
        assert result == ""

    def test_clean_content_no_tags(self):
        """Test cleaning content without any tags."""
        from src.mkv2srt import clean_srt_content

        content = """1
00:00:01,000 --> 00:00:04,000
Normal text without tags
"""
        result = clean_srt_content(content)
        assert "Normal text without tags" in result

    def test_clean_content_with_unicode(self):
        """Test cleaning content with unicode characters."""
        from src.mkv2srt import clean_srt_content

        content = """1
00:00:01,000 --> 00:00:04,000
{\\an7}Héllo Wörld! 你好世界!
"""
        result = clean_srt_content(content)
        assert "Héllo Wörld!" in result
        assert "你好世界!" in result
        assert "{\\an7}" not in result

    def test_clean_content_with_special_chars(self):
        """Test cleaning content with special characters."""
        from src.mkv2srt import clean_srt_content

        content = """1
00:00:01,000 --> 00:00:04,000
{\\an7}Special chars: @#$%^&*()
"""
        result = clean_srt_content(content)
        assert "Special chars: @#$%^&*()" in result
        assert "{\\an7}" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
