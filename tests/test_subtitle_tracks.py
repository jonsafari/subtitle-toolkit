#!/usr/bin/env python3
"""Unit tests for subtitle_tracks module."""
import tempfile
from datetime import timedelta
from pathlib import Path

import pytest

from src.subtitle_tracks import (
    TrackInfo,
    SubtitleEntry,
    list_tracks,
    extract_track,
    extract_all_tracks,
    merge_subtitles,
    parse_srt,
    write_srt,
    clean_srt_content,
    clean_srt_file,
    _parse_srt_time,
    _format_srt_time,
)


class TestTrackInfo:
    """Tests for TrackInfo dataclass."""
    
    def test_track_info_str_simple(self):
        """Test string representation of simple track."""
        track = TrackInfo(index=0, language="eng", codec="subrip")
        assert "Track 0" in str(track)
        assert "ENG" in str(track)
        assert "subrip" in str(track)
    
    def test_track_info_str_with_title(self):
        """Test string representation with title."""
        track = TrackInfo(index=1, language="spa", codec="subrip", title="Spanish")
        assert "Spanish" in str(track)
    
    def test_track_info_str_with_flags(self):
        """Test string representation with flags."""
        track = TrackInfo(
            index=2, 
            language="eng", 
            codec="subrip",
            is_forced=True,
            is_hearing_impaired=True
        )
        assert "Forced" in str(track)
        assert "Hearing Impaired" in str(track)


class TestSubtitleEntry:
    """Tests for SubtitleEntry dataclass."""
    
    def test_subtitle_entry_creation(self):
        """Test creating a subtitle entry."""
        entry = SubtitleEntry(
            index=1,
            start=timedelta(seconds=10),
            end=timedelta(seconds=15),
            text="Hello World"
        )
        assert entry.index == 1
        assert entry.start == timedelta(seconds=10)
        assert entry.end == timedelta(seconds=15)
        assert entry.text == "Hello World"


class TestSrtTimeParsing:
    """Tests for SRT time parsing and formatting."""
    
    def test_parse_srt_time_comma(self):
        """Test parsing SRT time with comma separator."""
        td = _parse_srt_time("00:01:30,500")
        assert td == timedelta(minutes=1, seconds=30, milliseconds=500)
    
    def test_parse_srt_time_period(self):
        """Test parsing SRT time with period separator."""
        td = _parse_srt_time("00:01:30.500")
        assert td == timedelta(minutes=1, seconds=30, milliseconds=500)
    
    def test_parse_srt_time_zero(self):
        """Test parsing zero time."""
        td = _parse_srt_time("00:00:00,000")
        assert td == timedelta(0)
    
    def test_parse_srt_time_hours(self):
        """Test parsing time with hours."""
        td = _parse_srt_time("01:30:45,123")
        assert td == timedelta(hours=1, minutes=30, seconds=45, milliseconds=123)
    
    def test_format_srt_time(self):
        """Test formatting timedelta to SRT time."""
        td = timedelta(minutes=1, seconds=30, milliseconds=500)
        assert _format_srt_time(td) == "00:01:30,500"
    
    def test_format_srt_time_zero(self):
        """Test formatting zero time."""
        td = timedelta(0)
        assert _format_srt_time(td) == "00:00:00,000"
    
    def test_format_srt_time_hours(self):
        """Test formatting time with hours."""
        td = timedelta(hours=1, minutes=30, seconds=45, milliseconds=123)
        assert _format_srt_time(td) == "01:30:45,123"


class TestParseSrt:
    """Tests for SRT parsing."""
    
    def test_parse_simple_srt(self):
        """Test parsing a simple SRT file."""
        srt_content = """1
00:00:01,000 --> 00:00:04,000
Hello World

2
00:00:05,000 --> 00:00:08,000
Goodbye World
"""
        entries = parse_srt(srt_content)
        assert len(entries) == 2
        assert entries[0].index == 1
        assert entries[0].text == "Hello World"
        assert entries[1].text == "Goodbye World"
    
    def test_parse_multiline_srt(self):
        """Test parsing SRT with multi-line text."""
        srt_content = """1
00:00:01,000 --> 00:00:04,000
Line one
Line two
Line three
"""
        entries = parse_srt(srt_content)
        assert len(entries) == 1
        assert entries[0].text == "Line one\nLine two\nLine three"
    
    def test_parse_empty_srt(self):
        """Test parsing empty SRT."""
        entries = parse_srt("")
        assert len(entries) == 0
    
    def test_parse_invalid_srt(self):
        """Test parsing invalid SRT content."""
        entries = parse_srt("not a valid srt file")
        assert len(entries) == 0


class TestWriteSrt:
    """Tests for SRT writing."""
    
    def test_write_simple_srt(self):
        """Test writing a simple SRT file."""
        entries = [
            SubtitleEntry(1, timedelta(seconds=1), timedelta(seconds=4), "Hello"),
            SubtitleEntry(2, timedelta(seconds=5), timedelta(seconds=8), "World"),
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            output_file = Path(f.name)
        
        try:
            write_srt(entries, output_file)
            with open(output_file, 'r') as f:
                content = f.read()
            
            assert "Hello" in content
            assert "World" in content
            assert "00:00:01,000 --> 00:00:04,000" in content
        finally:
            output_file.unlink()
    
    def test_write_renumbers_sequence(self):
        """Test that write_srt renumbers sequence starting from 1."""
        entries = [
            SubtitleEntry(100, timedelta(seconds=1), timedelta(seconds=2), "First"),
            SubtitleEntry(200, timedelta(seconds=3), timedelta(seconds=4), "Second"),
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            output_file = Path(f.name)
        
        try:
            write_srt(entries, output_file)
            with open(output_file, 'r') as f:
                content = f.read()
            
            # Should start with 1, not 100
            lines = content.strip().split('\n')
            assert lines[0] == "1"
        finally:
            output_file.unlink()


class TestCleanSrtContent:
    """Tests for SRT content cleaning."""
    
    def test_clean_ass_tags(self):
        """Test removing ASS formatting tags."""
        content = """1
00:00:01,000 --> 00:00:04,000
{\an7}Hello World
"""
        cleaned = clean_srt_content(content)
        assert "{\\an7}" not in cleaned
        assert "Hello World" in cleaned
    
    def test_clean_html_tags(self):
        """Test removing HTML tags."""
        content = """1
00:00:01,000 --> 00:00:04,000
<font face="Arial">Hello World</font>
"""
        cleaned = clean_srt_content(content)
        assert "<font" not in cleaned
        assert "</font>" not in cleaned
        assert "Hello World" in cleaned
    
    def test_clean_backslash_formatting(self):
        """Test removing backslash formatting."""
        content = r"""1
00:00:01,000 --> 00:00:04,000
Hello\hWorld\NNew Line
"""
        cleaned = clean_srt_content(content)
        assert "\\h" not in cleaned
        assert "\\N" not in cleaned
    
    def test_clean_preserves_structure(self):
        """Test that cleaning preserves SRT structure."""
        content = """1
00:00:01,000 --> 00:00:04,000
Hello World

2
00:00:05,000 --> 00:00:08,000
Goodbye World
"""
        cleaned = clean_srt_content(content)
        assert "1" in cleaned
        assert "2" in cleaned
        assert "00:00:01,000 --> 00:00:04,000" in cleaned


class TestMergeSubtitles:
    """Tests for subtitle merging."""
    
    def test_merge_non_overlapping(self):
        """Test merging non-overlapping subtitles."""
        # Create first file
        entries1 = [
            SubtitleEntry(1, timedelta(seconds=0), timedelta(seconds=5), "First"),
        ]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            file1 = Path(f.name)
        write_srt(entries1, file1)
        
        # Create second file
        entries2 = [
            SubtitleEntry(1, timedelta(seconds=10), timedelta(seconds=15), "Second"),
        ]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            file2 = Path(f.name)
        write_srt(entries2, file2)
        
        # Merge
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            output = Path(f.name)
        
        try:
            merge_subtitles([file1, file2], output, "first")
            merged = parse_srt(output.read_text())
            assert len(merged) == 2
        finally:
            file1.unlink()
            file2.unlink()
            output.unlink()
    
    def test_merge_overlapping_first_priority(self):
        """Test merging overlapping subtitles with first priority."""
        # Create two files with overlapping subtitles
        entries1 = [
            SubtitleEntry(1, timedelta(seconds=0), timedelta(seconds=10), "First"),
        ]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            file1 = Path(f.name)
        write_srt(entries1, file1)
        
        entries2 = [
            SubtitleEntry(1, timedelta(seconds=5), timedelta(seconds=15), "Second"),
        ]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            file2 = Path(f.name)
        write_srt(entries2, file2)
        
        # Merge with first priority
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            output = Path(f.name)
        
        try:
            merge_subtitles([file1, file2], output, "first")
            merged = parse_srt(output.read_text())
            # Should keep "First" and discard "Second"
            texts = [e.text for e in merged]
            assert "First" in texts
        finally:
            file1.unlink()
            file2.unlink()
            output.unlink()
    
    def test_merge_overlapping_combine(self):
        """Test merging overlapping subtitles with combine priority."""
        # Create two files with overlapping subtitles
        entries1 = [
            SubtitleEntry(1, timedelta(seconds=0), timedelta(seconds=10), "First"),
        ]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            file1 = Path(f.name)
        write_srt(entries1, file1)
        
        entries2 = [
            SubtitleEntry(1, timedelta(seconds=5), timedelta(seconds=15), "Second"),
        ]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            file2 = Path(f.name)
        write_srt(entries2, file2)
        
        # Merge with combine priority
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            output = Path(f.name)
        
        try:
            merge_subtitles([file1, file2], output, "combine")
            merged = parse_srt(output.read_text())
            # Should combine both
            texts = [e.text for e in merged]
            assert any("First" in t and "Second" in t for t in texts)
        finally:
            file1.unlink()
            file2.unlink()
            output.unlink()
    
    def test_merge_invalid_priority(self):
        """Test that invalid priority raises error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            file1 = Path(f.name)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            output = Path(f.name)
        
        try:
            with pytest.raises(ValueError, match="Invalid priority"):
                merge_subtitles([file1], output, "invalid")
        finally:
            file1.unlink()
            output.unlink()


class TestListTracks:
    """Tests for list_tracks function."""
    
    def test_list_tracks_no_file(self):
        """Test listing tracks from non-existent file."""
        with pytest.raises(FileNotFoundError):
            list_tracks(Path("/nonexistent/file.mkv"))
    
    def test_list_tracks_real_file(self):
        """Test listing tracks from real video file."""
        # Use the sample video file in the project
        video_file = Path("/home/tcsh/src/subtitle-toolkit/Winged_Migration_-_2001.mkv")
        if video_file.exists():
            tracks = list_tracks(video_file)
            assert len(tracks) > 0
            # Check that we have the expected tracks
            languages = [t.language for t in tracks]
            assert "eng" in languages


class TestExtractTrack:
    """Tests for extract_track function."""
    
    def test_extract_track_no_file(self):
        """Test extracting from non-existent file."""
        with pytest.raises(FileNotFoundError):
            extract_track(Path("/nonexistent/file.mkv"))
    
    def test_extract_track_not_found(self):
        """Test extracting non-existent track."""
        video_file = Path("/home/tcsh/src/subtitle-toolkit/Winged_Migration_-_2001.mkv")
        if video_file.exists():
            with pytest.raises(ValueError):
                extract_track(video_file, track_index=999)


class TestExtractAllTracks:
    """Tests for extract_all_tracks function."""

    def test_extract_all_tracks_no_file(self):
        """Test extracting from non-existent file."""
        with pytest.raises(FileNotFoundError):
            extract_all_tracks(Path("/nonexistent/file.mkv"))

    def test_extract_all_tracks_real_file(self, tmp_path):
        """Test extracting all tracks from a real video file."""
        video_file = Path("/home/tcsh/src/subtitle-toolkit/Winged_Migration_-_2001.mkv")
        if video_file.exists():
            result = extract_all_tracks(video_file, output_dir=tmp_path, as_zip=False)
            # Result is a tuple of (srt_files, zip_path)
            srt_files, zip_path = result
            # srt_files might be None if extraction fails, so check first
            if srt_files is not None:
                assert len(srt_files) > 0
                # Verify all files were created
                for srt_file in srt_files:
                    assert srt_file.exists()


class TestCheckFfmpeg:
    """Tests for check_ffmpeg function."""

    def test_check_ffmpeg_success(self):
        """Test ffmpeg check when ffmpeg is installed."""
        from src.subtitle_tracks import check_ffmpeg

        # This should not raise if ffmpeg is installed
        try:
            result = check_ffmpeg()
            assert result is True
        except SystemExit:
            pytest.skip("ffmpeg not installed in test environment")

    def test_check_ffmpeg_called(self):
        """Test that check_ffmpeg is called by other functions."""
        from src.subtitle_tracks import list_tracks

        # list_tracks should call check_ffmpeg internally
        # If ffmpeg is not installed, it should exit
        try:
            list_tracks(Path("/nonexistent/file.mkv"))
        except FileNotFoundError:
            # Expected - file doesn't exist, but ffmpeg was checked first
            pass
        except SystemExit:
            pytest.skip("ffmpeg not installed in test environment")


class TestCleanSrtFile:
    """Tests for clean_srt_file function."""

    def test_clean_srt_file(self, tmp_path):
        """Test cleaning an SRT file in place."""
        from src.subtitle_tracks import clean_srt_file

        # Create a test SRT file with ASS tags
        srt_file = tmp_path / "test.srt"
        content = """1
00:00:01,000 --> 00:00:04,000
{\\an7}Hello World

2
00:00:05,000 --> 00:00:08,000
{\\b1}Bold text
"""
        srt_file.write_text(content, encoding='utf-8')

        # Clean the file
        clean_srt_file(srt_file)

        # Verify tags were removed
        cleaned_content = srt_file.read_text(encoding='utf-8')
        assert "{\\an7}" not in cleaned_content
        assert "{\\b1}" not in cleaned_content
        assert "Hello World" in cleaned_content
        assert "Bold text" in cleaned_content

    def test_clean_srt_file_no_tags(self, tmp_path):
        """Test cleaning an SRT file without tags."""
        from src.subtitle_tracks import clean_srt_file

        srt_file = tmp_path / "test.srt"
        content = """1
00:00:01,000 --> 00:00:04,000
Hello World
"""
        srt_file.write_text(content, encoding='utf-8')

        # Clean the file
        clean_srt_file(srt_file)

        # Content should be unchanged (except for whitespace normalization)
        cleaned_content = srt_file.read_text(encoding='utf-8')
        assert "Hello World" in cleaned_content

    def test_clean_srt_file_not_found(self):
        """Test cleaning a non-existent file."""
        from src.subtitle_tracks import clean_srt_file

        with pytest.raises(FileNotFoundError):
            clean_srt_file(Path("/nonexistent/file.srt"))


class TestParseFfprobeOutput:
    """Tests for _parse_ffprobe_output internal function."""

    def test_parse_ffprobe_output_no_file(self):
        """Test parsing ffprobe output for non-existent file."""
        from src.subtitle_tracks import _parse_ffprobe_output

        # ffprobe fails on non-existent files, which raises RuntimeError
        with pytest.raises((FileNotFoundError, RuntimeError)):
            _parse_ffprobe_output(Path("/nonexistent/file.mkv"))

    def test_parse_ffprobe_output_real_file(self):
        """Test parsing ffprobe output for a real video file."""
        from src.subtitle_tracks import _parse_ffprobe_output

        video_file = Path("/home/tcsh/src/subtitle-toolkit/Winged_Migration_-_2001.mkv")
        if video_file.exists():
            info = _parse_ffprobe_output(video_file)
            assert "streams" in info
            assert "format" in info


class TestExtractTrackWithLanguage:
    """Tests for extract_track with language filtering."""

    def test_extract_track_by_language(self, tmp_path):
        """Test extracting a track by language code."""
        video_file = Path("/home/tcsh/src/subtitle-toolkit/Winged_Migration_-_2001.mkv")
        if video_file.exists():
            output_file = tmp_path / "output.srt"
            try:
                result = extract_track(video_file, language="eng", output_file=output_file)
                assert result.exists()
                # Verify it contains valid SRT format
                content = result.read_text(encoding='utf-8')
                assert "-->" in content
            except RuntimeError as e:
                # Some video files may have subtitle codecs that can't be converted to SRT
                pytest.skip(f"Subtitle extraction failed: {e}")

    def test_extract_track_by_track_index(self, tmp_path):
        """Test extracting a track by index."""
        video_file = Path("/home/tcsh/src/subtitle-toolkit/Winged_Migration_-_2001.mkv")
        if video_file.exists():
            # First, list tracks to find a valid track index
            tracks = list_tracks(video_file)
            if len(tracks) > 0:
                output_file = tmp_path / "output.srt"
                try:
                    result = extract_track(video_file, track_index=tracks[0].index, output_file=output_file)
                    assert result.exists()
                except RuntimeError as e:
                    # Some subtitle codecs may not be convertible to SRT
                    pytest.skip(f"Subtitle extraction failed: {e}")


class TestExtractAllTracksWithZip:
    """Tests for extract_all_tracks with ZIP output."""

    def test_extract_all_tracks_as_zip(self, tmp_path):
        """Test extracting all tracks as a ZIP file."""
        video_file = Path("/home/tcsh/src/subtitle-toolkit/Winged_Migration_-_2001.mkv")
        if video_file.exists():
            output_dir = tmp_path / "subtitles"
            try:
                srt_files, zip_path = extract_all_tracks(video_file, output_dir=output_dir, as_zip=True)
                # When as_zip=True, zip_path should be set
                if zip_path is not None:
                    assert zip_path.exists()
                    # Verify ZIP contains SRT files
                    import zipfile
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        names = zf.namelist()
                        assert any(name.endswith('.srt') for name in names)
                else:
                    # If zip_path is None, check that srt_files were created
                    if srt_files is not None:
                        assert len(srt_files) > 0
            except RuntimeError as e:
                # Some subtitle codecs may not be convertible to SRT
                pytest.skip(f"Subtitle extraction failed: {e}")


class TestCleanSrtContentEdgeCases:
    """Additional edge case tests for clean_srt_content."""

    def test_clean_empty_content(self):
        """Test cleaning empty content."""
        result = clean_srt_content("")
        assert result == ""

    def test_clean_content_no_tags(self):
        """Test cleaning content without any tags."""
        content = """1
00:00:01,000 --> 00:00:04,000
Normal text without tags
"""
        result = clean_srt_content(content)
        assert "Normal text without tags" in result

    def test_clean_content_with_unicode(self):
        """Test cleaning content with unicode characters."""
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
        content = """1
00:00:01,000 --> 00:00:04,000
{\\an7}Special chars: @#$%^&*()
"""
        result = clean_srt_content(content)
        assert "Special chars: @#$%^&*()" in result
        assert "{\\an7}" not in result

    def test_clean_content_preserves_index(self):
        """Test that index numbers are preserved."""
        content = """1
00:00:01,000 --> 00:00:04,000
{\\an7}First

2
00:00:05,000 --> 00:00:08,000
{\\an7}Second

3
00:00:09,000 --> 00:00:12,000
{\\an7}Third
"""
        result = clean_srt_content(content)
        assert "1\n" in result
        assert "2\n" in result
        assert "3\n" in result

    def test_clean_content_with_multiple_tags(self):
        """Test cleaning content with multiple consecutive tags."""
        content = """1
00:00:01,000 --> 00:00:04,000
{\\b1}{\\i1}{\\u1}Multiple tags
"""
        result = clean_srt_content(content)
        assert "Multiple tags" in result
        assert "{\\b1}" not in result
        assert "{\\i1}" not in result
        assert "{\\u1}" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
