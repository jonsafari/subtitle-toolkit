"""Tests for cli.py - the unified command-line interface."""
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

# Add the project root to the path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestGetScriptDir:
    """Tests for the get_script_dir function."""

    def test_get_script_dir_returns_path(self):
        """Test that get_script_dir returns a Path object."""
        from src.cli import get_script_dir

        result = get_script_dir()

        assert isinstance(result, Path)
        assert result.is_absolute()
        assert result.exists()


class TestCommandLineInterface:
    """Tests for the CLI main function via subprocess."""

    def test_cli_help_flag(self):
        """Test that --help flag shows help message."""
        result = subprocess.run(
            [sys.executable, "./src/cli.py", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        assert "Subtitle Toolkit" in result.stdout
        assert "translate" in result.stdout
        assert "timeshift" in result.stdout

    def test_cli_short_help_flag(self):
        """Test that -h flag shows help message."""
        result = subprocess.run(
            [sys.executable, "./src/cli.py", "-h"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        assert "Subtitle Toolkit" in result.stdout

    def test_cli_no_args_shows_help(self):
        """Test that running without arguments shows help."""
        result = subprocess.run(
            [sys.executable, "./src/cli.py"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        assert "Subtitle Toolkit" in result.stdout
        assert "Commands:" in result.stdout

    def test_cli_invalid_command(self):
        """Test that invalid command shows error."""
        result = subprocess.run(
            [sys.executable, "./src/cli.py", "invalid-command"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 1
        # Should show help with available commands
        assert "translate" in result.stdout or "timeshift" in result.stdout

    def test_cli_translate_command_exists(self):
        """Test that translate command is recognized."""
        # This will fail because we don't have an input file, but it should recognize the command
        result = subprocess.run(
            [sys.executable, "./src/cli.py", "translate", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should succeed (show translate help) or at least not fail with "invalid command"
        assert result.returncode == 0 or "translate" in result.stdout.lower()

    def test_cli_timeshift_command_exists(self):
        """Test that timeshift command is recognized."""
        result = subprocess.run(
            [sys.executable, "./src/cli.py", "timeshift", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should succeed (show timeshift help)
        assert result.returncode == 0


class TestCliSubcommands:
    """Tests for CLI subcommand execution."""

    def test_cli_timeshift_with_shift(self, tmp_path, sample_srt_content):
        """Test timeshift subcommand with shift parameter."""
        input_file = tmp_path / "input.srt"
        input_file.write_text(sample_srt_content, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, "./src/cli.py", "timeshift", "--shift-seconds", "2.0"],
            stdin=open(input_file),
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        assert "00:00:03,000 --> 00:00:06,000" in result.stdout

    def test_cli_timeshift_with_first_entry(self, tmp_path, sample_srt_content):
        """Test timeshift subcommand with first-entry-starts-at parameter."""
        input_file = tmp_path / "input.srt"
        input_file.write_text(sample_srt_content, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, "./src/cli.py", "timeshift", "--first-entry-starts-at", "00:00:05,000"],
            stdin=open(input_file),
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        assert "00:00:05,000 --> 00:00:08,000" in result.stdout

    def test_cli_translate_with_invalid_file(self, tmp_path):
        """Test translate subcommand with non-existent file."""
        result = subprocess.run(
            [sys.executable, "./src/cli.py", "translate", str(tmp_path / "nonexistent.srt")],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should fail because file doesn't exist
        assert result.returncode != 0


class TestRunFunctions:
    """Tests for the run_* functions (internal CLI functions)."""

    def test_run_translate_calls_subprocess(self):
        """Test that run_translate builds correct command."""
        from src.cli import run_translate, get_script_dir

        script_path = get_script_dir() / "translate.py"

        with mock.patch('subprocess.run') as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0)

            result = run_translate(["--help"])

            # Verify subprocess was called with correct arguments
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]  # First positional argument
            assert sys.executable in call_args[0] or call_args[0].endswith('python')
            assert str(script_path) in str(call_args)
            assert "--help" in call_args

    def test_run_timeshift_calls_subprocess(self):
        """Test that run_timeshift builds correct command."""
        from src.cli import run_timeshift, get_script_dir

        script_path = get_script_dir() / "timeshift.py"

        with mock.patch('subprocess.run') as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0)

            result = run_timeshift(["--help"])

            # Verify subprocess was called with correct arguments
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert str(script_path) in str(call_args)
            assert "--help" in call_args

    def test_run_functions_return_exit_code(self):
        """Test that run functions return the subprocess exit code."""
        from src.cli import run_translate

        with mock.patch('subprocess.run') as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=42)

            result = run_translate(["--help"])

            assert result == 42


class TestCliEdgeCases:
    """Tests for CLI edge cases."""

    def test_cli_with_extra_args(self, tmp_path, sample_srt_content):
        """Test that extra arguments are passed through correctly."""
        input_file = tmp_path / "input.srt"
        input_file.write_text(sample_srt_content, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, "./src/cli.py", "timeshift", "-s", "1.5"],
            stdin=open(input_file),
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        # First entry starts at 00:00:01,000, shifted by 1.5 seconds later = 00:00:02,500
        # Second entry starts at 00:00:05,000, shifted by 1.5 seconds later = 00:00:06,500
        assert "00:00:02,500 --> 00:00:05,500" in result.stdout
        assert "00:00:06,500 --> 00:00:09,500" in result.stdout

    def test_cli_case_sensitive_commands(self):
        """Test that commands are case-sensitive."""
        result = subprocess.run(
            [sys.executable, "./src/cli.py", "Translate"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should fail because "Translate" is not a valid command (should be "translate")
        assert result.returncode == 1

    def test_cli_empty_string_command(self):
        """Test that empty string command shows help."""
        result = subprocess.run(
            [sys.executable, "./src/cli.py", ""],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Empty string is treated as invalid command
        assert result.returncode == 1 or "Subtitle Toolkit" in result.stdout


class TestCliIntegration:
    """Integration tests for the CLI."""

    def test_cli_full_workflow_timeshift(self, tmp_path, sample_srt_content):
        """Test complete timeshift workflow via CLI."""
        input_file = tmp_path / "input.srt"
        output_file = tmp_path / "output.srt"
        input_file.write_text(sample_srt_content, encoding='utf-8')

        # Run timeshift via CLI
        result = subprocess.run(
            [sys.executable, "./src/cli.py", "timeshift", "--shift-seconds", "5.0"],
            stdin=open(input_file),
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0

        # Write output
        output_file.write_text(result.stdout, encoding='utf-8')

        # Verify output file
        assert output_file.exists()
        content = output_file.read_text(encoding='utf-8')
        # First entry starts at 00:00:01,000, shifted by 5 seconds later = 00:00:06,000
        # Second entry starts at 00:00:05,000, shifted by 5 seconds later = 00:00:10,000
        # Third entry starts at 00:00:09,000, shifted by 5 seconds later = 00:00:14,000
        assert "00:00:06,000 --> 00:00:09,000" in content  # First entry shifted by 5 seconds
        assert "00:00:14,000 --> 00:00:17,000" in content  # Third entry shifted by 5 seconds

    def test_cli_preserves_subtitle_text(self, tmp_path, sample_srt_content):
        """Test that CLI preserves subtitle text content."""
        input_file = tmp_path / "input.srt"
        input_file.write_text(sample_srt_content, encoding='utf-8')

        result = subprocess.run(
            [sys.executable, "./src/cli.py", "timeshift", "--shift-seconds", "1.0"],
            stdin=open(input_file),
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0

        # Check that original text is preserved
        assert "Hello, welcome to the subtitle toolkit." in result.stdout
        assert "This is a test subtitle file." in result.stdout
        assert "We can shift timestamps or translate them." in result.stdout
