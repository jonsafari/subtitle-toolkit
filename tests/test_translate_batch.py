#!/usr/bin/env python3
"""
Unit tests for the translate_batch module.
"""
import pytest
import tempfile
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from translate_batch import scan_directory, format_time


class TestFormatTime:
    """Tests for the format_time function."""
    
    def test_format_seconds(self):
        """Test formatting seconds."""
        assert format_time(30) == "30s"
        assert format_time(59) == "59s"
    
    def test_format_minutes(self):
        """Test formatting minutes and seconds."""
        assert format_time(60) == "1m 0s"
        assert format_time(90) == "1m 30s"
        assert format_time(3000) == "50m 0s"
    
    def test_format_hours(self):
        """Test formatting hours, minutes, and seconds."""
        assert format_time(3600) == "1h 0m"
        assert format_time(3661) == "1h 1m 1s"
        assert format_time(7261) == "2h 1m 1s"
        assert format_time(3665) == "1h 1m 5s"


class TestScanDirectory:
    """Tests for the scan_directory function."""
    
    def test_scan_empty_directory(self):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_pairs, skipped = scan_directory(
                directory=Path(tmpdir),
                source_lang="en",
                target_lang="es",
                recursive=False
            )
            assert file_pairs == []
            assert skipped == []
    
    def test_scan_no_matching_files(self):
        """Test scanning directory with no matching files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file that doesn't match the pattern
            Path(tmpdir, "readme.txt").write_text("Hello")
            
            file_pairs, skipped = scan_directory(
                directory=Path(tmpdir),
                source_lang="en",
                target_lang="es",
                recursive=False
            )
            assert file_pairs == []
            assert skipped == []
    
    def test_scan_source_only(self):
        """Test scanning directory with only source files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source files
            Path(tmpdir, "show_S03E01.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHello")
            Path(tmpdir, "show_S03E02.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nWorld")
            
            file_pairs, skipped = scan_directory(
                directory=Path(tmpdir),
                source_lang="en",
                target_lang="es",
                recursive=False
            )
            
            assert len(file_pairs) == 2
            assert len(skipped) == 0
            
            # Check that target files don't exist yet
            for source, target in file_pairs:
                assert not target.exists()
    
    def test_scan_already_translated(self):
        """Test scanning directory with already translated files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source and target files
            Path(tmpdir, "show_S03E01.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHello")
            Path(tmpdir, "show_S03E01.es.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHola")
            Path(tmpdir, "show_S03E02.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nWorld")
            
            file_pairs, skipped = scan_directory(
                directory=Path(tmpdir),
                source_lang="en",
                target_lang="es",
                recursive=False
            )
            
            assert len(file_pairs) == 1  # Only show_S03E02 needs translation
            assert len(skipped) == 1     # show_S03E01 is already translated
    
    def test_scan_mixed_extensions(self):
        """Test scanning directory with mixed file extensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with different extensions
            Path(tmpdir, "show_S03E01.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHello")
            Path(tmpdir, "show_S03E02.en.vtt").write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nWorld")
            Path(tmpdir, "show_S03E03.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nTest")
            Path(tmpdir, "show_S03E03.es.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nPrueba")
            
            file_pairs, skipped = scan_directory(
                directory=Path(tmpdir),
                source_lang="en",
                target_lang="es",
                recursive=False,
                extensions=['.srt', '.vtt']
            )
            
            assert len(file_pairs) == 2  # show_S03E01.srt and show_S03E02.vtt
            assert len(skipped) == 1     # show_S03E03.srt is already translated
    
    def test_scan_recursive(self):
        """Test recursive directory scanning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested directory structure
            subdir = Path(tmpdir, "season1", "episodes")
            subdir.mkdir(parents=True)
            
            Path(tmpdir, "show_S03E01.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHello")
            Path(subdir, "show_S03E02.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nWorld")
            
            # Non-recursive scan
            file_pairs, skipped = scan_directory(
                directory=Path(tmpdir),
                source_lang="en",
                target_lang="es",
                recursive=False
            )
            assert len(file_pairs) == 1  # Only root directory
            
            # Recursive scan
            file_pairs, skipped = scan_directory(
                directory=Path(tmpdir),
                source_lang="en",
                target_lang="es",
                recursive=True
            )
            assert len(file_pairs) == 2  # Both files
    
    def test_scan_case_sensitive(self):
        """Test that language codes are case-sensitive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with different cases
            Path(tmpdir, "show_S03E01.EN.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHello")
            Path(tmpdir, "show_S03E02.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nWorld")
            
            # Search for lowercase 'en'
            file_pairs, skipped = scan_directory(
                directory=Path(tmpdir),
                source_lang="en",
                target_lang="es",
                recursive=False
            )
            
            # Only the lowercase file should match
            assert len(file_pairs) == 1
            assert "show_S03E02.en.srt" in str(file_pairs[0][0])
    
    def test_scan_complex_language_codes(self):
        """Test scanning with complex language codes like pt-BR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with complex language codes
            Path(tmpdir, "show_S03E01.pt-BR.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nOlá")
            Path(tmpdir, "show_S03E02.pt-BR.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nMundo")
            Path(tmpdir, "show_S03E01.es.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHola")
            
            file_pairs, skipped = scan_directory(
                directory=Path(tmpdir),
                source_lang="pt-BR",
                target_lang="es",
                recursive=False
            )
            
            assert len(file_pairs) == 1  # Only show_S03E02 needs translation
            assert len(skipped) == 1     # show_S03E01 is already translated
    
    def test_scan_nonexistent_directory(self):
        """Test scanning a nonexistent directory."""
        with pytest.raises(SystemExit):
            scan_directory(
                directory=Path("/nonexistent/directory"),
                source_lang="en",
                target_lang="es",
                recursive=False
            )


class TestFilePairing:
    """Tests for file pairing logic."""
    
    def test_target_file_path_construction(self):
        """Test that target file paths are constructed correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file
            source = Path(tmpdir, "show_S03E01.en.srt")
            source.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello")
            
            file_pairs, skipped = scan_directory(
                directory=Path(tmpdir),
                source_lang="en",
                target_lang="es",
                recursive=False
            )
            
            assert len(file_pairs) == 1
            source_path, target_path = file_pairs[0]
            
            assert source_path.name == "show_S03E01.en.srt"
            assert target_path.name == "show_S03E01.es.srt"
            assert target_path.parent == source_path.parent


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
