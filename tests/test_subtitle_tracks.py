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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
