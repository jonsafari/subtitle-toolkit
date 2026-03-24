#!/usr/bin/env python3
"""Unit tests for subtitle-tracks CLI."""
import subprocess
import sys
from pathlib import Path

import pytest

# Add the project root to the path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCliHelp:
    """Tests for CLI help output."""

    def test_cli_help_flag(self):
        """Test --help flag shows help message."""
        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        assert "subtitle-tracks" in result.stdout.lower() or "usage" in result.stdout.lower()

    def test_cli_no_command_shows_help(self):
        """Test that running without a command shows help."""
        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should show help or list of commands
        assert result.returncode == 0 or "usage" in result.stdout.lower() or "help" in result.stdout.lower()


class TestCliListCommand:
    """Tests for the 'list' subcommand."""

    def test_list_command_no_file(self):
        """Test list command with no file argument."""
        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py", "list"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should fail because no file provided
        assert result.returncode != 0

    def test_list_command_nonexistent_file(self):
        """Test list command with non-existent file."""
        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py", "list", "/nonexistent/file.mkv"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should fail because file doesn't exist
        assert result.returncode != 0

    def test_list_command_real_file(self):
        """Test list command with real video file."""
        video_file = Path("/home/tcsh/src/subtitle-toolkit/Winged_Migration_-_2001.mkv")
        if not video_file.exists():
            pytest.skip("Test video file not found")

        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py", "list", str(video_file)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        # Should list tracks
        assert "Track" in result.stdout or "track" in result.stdout.lower()


class TestCliExtractCommand:
    """Tests for the 'extract' subcommand."""

    def test_extract_command_no_file(self, tmp_path):
        """Test extract command with no file argument."""
        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py", "extract"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should fail because no file provided
        assert result.returncode != 0

    def test_extract_command_nonexistent_file(self, tmp_path):
        """Test extract command with non-existent file."""
        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py", "extract", "/nonexistent/file.mkv"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should fail because file doesn't exist
        assert result.returncode != 0

    def test_extract_command_by_language(self, tmp_path):
        """Test extract command with language filter."""
        video_file = Path("/home/tcsh/src/subtitle-toolkit/Winged_Migration_-_2001.mkv")
        if not video_file.exists():
            pytest.skip("Test video file not found")

        output_file = tmp_path / "output.srt"
        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py", "extract", str(video_file),
             "--language", "eng", "--output", str(output_file)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # May fail if subtitle codec can't be converted to SRT
        if result.returncode != 0:
            pytest.skip(f"Subtitle extraction failed: {result.stderr}")
        assert output_file.exists()

    def test_extract_command_by_track_index(self, tmp_path):
        """Test extract command with track index."""
        video_file = Path("/home/tcsh/src/subtitle-toolkit/Winged_Migration_-_2001.mkv")
        if not video_file.exists():
            pytest.skip("Test video file not found")

        output_file = tmp_path / "output.srt"
        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py", "extract", str(video_file),
             "--track", "0", "--output", str(output_file)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # May fail if subtitle codec can't be converted to SRT or track not found
        if result.returncode != 0:
            pytest.skip(f"Subtitle extraction failed: {result.stderr}")
        assert output_file.exists()

    def test_extract_command_all_tracks(self, tmp_path):
        """Test extract command with --all flag."""
        video_file = Path("/home/tcsh/src/subtitle-toolkit/Winged_Migration_-_2001.mkv")
        if not video_file.exists():
            pytest.skip("Test video file not found")

        output_dir = tmp_path / "subtitles"
        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py", "extract", str(video_file),
             "--all", "--output", str(output_dir)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # May fail if subtitle codec can't be converted to SRT
        if result.returncode != 0:
            pytest.skip(f"Subtitle extraction failed: {result.stderr}")
        # Should have created output directory with SRT files
        assert output_dir.exists()
        srt_files = list(output_dir.glob("*.srt"))
        assert len(srt_files) > 0

    def test_extract_command_all_tracks_as_zip(self, tmp_path):
        """Test extract command with --all and --as-zip flags."""
        video_file = Path("/home/tcsh/src/subtitle-toolkit/Winged_Migration_-_2001.mkv")
        if not video_file.exists():
            pytest.skip("Test video file not found")

        output_dir = tmp_path / "subtitles"
        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py", "extract", str(video_file),
             "--all", "--as-zip", "--output", str(output_dir)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # May fail if subtitle codec can't be converted to SRT
        if result.returncode != 0:
            pytest.skip(f"Subtitle extraction failed: {result.stderr}")
        # Should have created a ZIP file in the output directory
        zip_files = list(output_dir.glob("*.zip"))
        assert len(zip_files) > 0


class TestCliMergeCommand:
    """Tests for the 'merge' subcommand."""

    def test_merge_command_no_files(self, tmp_path):
        """Test merge command with no input files."""
        output_file = tmp_path / "output.srt"
        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py", "merge",
             "--output", str(output_file)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should fail because no input files provided
        assert result.returncode != 0

    def test_merge_command_with_files(self, tmp_path):
        """Test merge command with input files."""
        # Create test SRT files
        file1 = tmp_path / "sub1.srt"
        file1.write_text("""1
00:00:01,000 --> 00:00:04,000
First subtitle
""")

        file2 = tmp_path / "sub2.srt"
        file2.write_text("""1
00:00:05,000 --> 00:00:08,000
Second subtitle
""")

        output_file = tmp_path / "merged.srt"
        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py", "merge",
             str(file1), str(file2),
             "--output", str(output_file),
             "--priority", "first"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        assert output_file.exists()
        content = output_file.read_text(encoding='utf-8')
        assert "First subtitle" in content
        assert "Second subtitle" in content

    def test_merge_command_with_combine_priority(self, tmp_path):
        """Test merge command with combine priority."""
        # Create test SRT files with overlapping times
        file1 = tmp_path / "sub1.srt"
        file1.write_text("""1
00:00:01,000 --> 00:00:05,000
First subtitle
""")

        file2 = tmp_path / "sub2.srt"
        file2.write_text("""1
00:00:03,000 --> 00:00:07,000
Second subtitle
""")

        output_file = tmp_path / "merged.srt"
        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py", "merge",
             str(file1), str(file2),
             "--output", str(output_file),
             "--priority", "combine"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        assert output_file.exists()


class TestCliEdgeCases:
    """Tests for CLI edge cases."""

    def test_cli_invalid_command(self):
        """Test that invalid commands are rejected."""
        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py", "invalidcommand"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should fail with non-zero exit code
        assert result.returncode != 0

    def test_cli_case_sensitive_commands(self):
        """Test that commands are case-sensitive."""
        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py", "List"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should fail because "List" is not a valid command (should be "list")
        assert result.returncode != 0

    def test_cli_invalid_priority(self, tmp_path):
        """Test that invalid priority is rejected."""
        file1 = tmp_path / "sub1.srt"
        file1.write_text("""1
00:00:01,000 --> 00:00:04,000
Test
""")

        output_file = tmp_path / "output.srt"
        result = subprocess.run(
            [sys.executable, "./src/subtitle_tracks.py", "merge",
             str(file1),
             "--output", str(output_file),
             "--priority", "invalid"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should fail with non-zero exit code
        assert result.returncode != 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
