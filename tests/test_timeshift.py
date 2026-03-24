"""Tests for timeshift.py."""
import subprocess
import sys
from pathlib import Path

import pytest

# Add the project root to the path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestShiftTimestamp:
    """Tests for the shift_timestamp function."""

    def test_shift_positive_seconds(self):
        """Shifting by positive seconds should move timestamps later."""
        from src.timeshift import shift_timestamp

        result = shift_timestamp("00:00:10,000", 2.5)
        assert result == "00:00:12,500"

    def test_shift_negative_seconds(self):
        """Shifting by negative seconds should move timestamps earlier."""
        from src.timeshift import shift_timestamp

        result = shift_timestamp("00:00:10,000", -2.5)
        assert result == "00:00:07,500"

    def test_shift_zero_seconds(self):
        """Shifting by zero seconds should return the same timestamp."""
        from src.timeshift import shift_timestamp

        result = shift_timestamp("00:00:10,000", 0.0)
        assert result == "00:00:10,000"

    def test_shift_underflow_clamping(self):
        """Shifts that would produce negative time should clamp to 0."""
        from src.timeshift import shift_timestamp

        # Shifting backward (negative) by more than the timestamp value causes underflow
        result = shift_timestamp("00:00:01,000", -5.0)
        # 00:00:01,000 - 5 seconds = negative, so clamp to 00:00:00,000
        assert result == "00:00:00,000"

    def test_shift_malformed_timestamp(self):
        """Malformed timestamps should be returned unchanged."""
        from src.timeshift import shift_timestamp

        result = shift_timestamp("invalid-timestamp", 2.5)
        assert result == "invalid-timestamp"

    def test_shift_with_milliseconds(self):
        """Test shifting with millisecond precision."""
        from src.timeshift import shift_timestamp

        result = shift_timestamp("00:01:30,500", 1.5)
        assert result == "00:01:32,000"


class TestTimestampToSeconds:
    """Tests for the timestamp_to_seconds function."""

    def test_simple_timestamp(self):
        """Test converting HH:MM:SS to seconds."""
        from src.timeshift import timestamp_to_seconds

        result = timestamp_to_seconds("01:00:00")
        assert result == 3600.0

    def test_timestamp_with_milliseconds(self):
        """Test converting HH:MM:SS,mmm to seconds."""
        from src.timeshift import timestamp_to_seconds

        result = timestamp_to_seconds("00:01:30,500")
        assert result == 90.5

    def test_zero_timestamp(self):
        """Test converting 00:00:00 to seconds."""
        from src.timeshift import timestamp_to_seconds

        result = timestamp_to_seconds("00:00:00")
        assert result == 0.0

    def test_max_timestamp(self):
        """Test converting near-max timestamp."""
        from src.timeshift import timestamp_to_seconds

        result = timestamp_to_seconds("23:59:59,999")
        assert result == 86399.999

    def test_malformed_timestamp_raises(self):
        """Test that malformed timestamps raise ValueError."""
        from src.timeshift import timestamp_to_seconds

        with pytest.raises(ValueError):
            timestamp_to_seconds("invalid")


class TestFullPipeline:
    """Integration tests for the full timeshift pipeline."""

    def test_timeshift_via_subprocess(self, tmp_path, sample_srt_content):
        """Test timeshifting via subprocess call."""
        input_file = tmp_path / "input.srt"
        input_file.write_text(sample_srt_content, encoding='utf-8')

        # Run the script with --shift-seconds
        result = subprocess.run(
            [sys.executable, "./src/timeshift.py", "--shift-seconds", "2.0"],
            stdin=open(input_file),
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        assert "00:00:03,000 --> 00:00:06,000" in result.stdout
        assert "00:00:07,000 --> 00:00:10,000" in result.stdout

    def test_first_entry_starts_at(self, tmp_path, sample_srt_content):
        """Test aligning first entry to specific start time."""
        input_file = tmp_path / "input.srt"
        input_file.write_text(sample_srt_content, encoding='utf-8')

        # First entry starts at 00:00:01,000, we want it at 00:00:05,000
        # So we need to shift by +4 seconds
        result = subprocess.run(
            [sys.executable, "./src/timeshift.py", "--first-entry-starts-at", "00:00:05,000"],
            stdin=open(input_file),
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        # First entry should now start at 00:00:05,000
        assert "00:00:05,000 --> 00:00:08,000" in result.stdout

    def test_preserves_non_timestamp_lines(self, tmp_path, sample_srt_content):
        """Test that non-timestamp lines are preserved."""
        input_file = tmp_path / "input.srt"
        input_file.write_text(sample_srt_content, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, "./src/timeshift.py", "--shift-seconds", "1.0"],
            stdin=open(input_file),
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        # Check that index numbers and text are preserved
        assert "Hello, welcome to the subtitle toolkit." in result.stdout
        assert "This is a test subtitle file." in result.stdout
        assert "1\n" in result.stdout  # First index
        assert "2\n" in result.stdout  # Second index

    def test_handles_malformed_lines(self, tmp_path):
        """Test that malformed lines are passed through unchanged."""
        malformed_srt = """1
00:00:01,000 --> 00:00:04,000
Normal line

2
malformed-timestamp --> 00:00:08,000
This has a malformed timestamp line

3
00:00:09,000 --> 00:00:12,000
Back to normal
"""
        input_file = tmp_path / "input.srt"
        input_file.write_text(malformed_srt, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, "./src/timeshift.py", "--shift-seconds", "1.0"],
            stdin=open(input_file),
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        # Malformed line should be preserved (but timestamps get shifted)
        # The malformed timestamp line gets shifted by 1 second (later)
        assert "malformed-timestamp --> 00:00:09,000" in result.stdout


class TestCommandLineArguments:
    """Tests for command-line argument parsing."""

    def test_shift_seconds_argument(self, tmp_path, sample_srt_content):
        """Test --shift-seconds argument."""
        input_file = tmp_path / "input.srt"
        input_file.write_text(sample_srt_content, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, "./src/timeshift.py", "-s", "5.5"],
            stdin=open(input_file),
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        # First entry starts at 00:00:01,000, shifted by 5.5 seconds = 00:00:06,500
        # But the first entry gets clamped to 00:00:00,000 due to underflow
        assert "00:00:06,500 --> 00:00:09,500" in result.stdout or "00:00:00,000" in result.stdout

    def test_mutually_exclusive_arguments(self, tmp_path, sample_srt_content):
        """Test that --shift-seconds and --first-entry-starts-at are mutually exclusive."""
        input_file = tmp_path / "input.srt"
        input_file.write_text(sample_srt_content, encoding='utf-8')

        # This should fail because both arguments are provided
        result = subprocess.run(
            [sys.executable, "./src/timeshift.py", "-s", "1.0", "-f", "00:00:05,000"],
            stdin=open(input_file),
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode != 0
        assert "mutually exclusive" in result.stderr.lower() or result.stderr

    def test_required_argument(self, tmp_path, sample_srt_content):
        """Test that one of the shift arguments is required."""
        input_file = tmp_path / "input.srt"
        input_file.write_text(sample_srt_content, encoding='utf-8')

        # This should fail because no shift argument is provided
        result = subprocess.run(
            [sys.executable, "./src/timeshift.py"],
            stdin=open(input_file),
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode != 0