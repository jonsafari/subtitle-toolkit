"""Tests for app.py FastAPI endpoints."""
import sys
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

# Add the project root to the path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app


# Create a test client
client = TestClient(app)


class TestRootEndpoint:
    """Tests for the root endpoint."""

    def test_read_root(self):
        """Test the root endpoint returns the index page."""
        response = client.get("/")

        assert response.status_code == 200
        assert "Subtitle Toolkit" in response.text
        assert "index.html" in response.text or response.headers["content-type"].startswith("text/html")


class TestTimeshiftEndpoints:
    """Tests for the timeshift endpoints."""

    def test_timeshift_page(self):
        """Test the timeshift page returns the form."""
        response = client.get("/timeshift")

        assert response.status_code == 200
        assert "timeshift.html" in response.text or response.headers["content-type"].startswith("text/html")
        assert "shift" in response.text.lower() or "subtitle" in response.text.lower()

    def test_timeshift_submit_with_shift_seconds(self):
        """Test timeshift submission with shift_seconds."""
        response = client.post(
            "/timeshift",
            data={
                "shift_seconds": "2.5",
                "srt_file": "1\n00:00:01,000 --> 00:00:04,000\nTest\n"
            }
        )

        # This should work if the script is available
        assert response.status_code == 200
        assert "timeshift_result.html" in response.text or response.headers["content-type"].startswith("text/html")

    def test_timeshift_submit_with_first_entry_starts_at(self):
        """Test timeshift submission with first_entry_starts_at."""
        response = client.post(
            "/timeshift",
            data={
                "first_entry_starts_at": "00:00:05,000",
                "srt_file": "1\n00:00:01,000 --> 00:00:04,000\nTest\n"
            }
        )

        assert response.status_code == 200

    def test_timeshift_submit_missing_file(self):
        """Test timeshift submission without SRT file."""
        response = client.post(
            "/timeshift",
            data={
                "shift_seconds": "2.5",
                "srt_file": ""
            }
        )

        # The form validation should show an error
        assert response.status_code == 200
        # Check for error message in the response
        assert "error" in response.text.lower() or "upload" in response.text.lower()

    def test_timeshift_submit_missing_parameters(self):
        """Test timeshift submission without required parameters."""
        response = client.post(
            "/timeshift",
            data={
                "srt_file": "1\n00:00:01,000 --> 00:00:04,000\nTest\n"
            }
        )

        # The form validation should show an error
        assert response.status_code == 200
        assert "error" in response.text.lower() or "provide" in response.text.lower()

    def test_timeshift_download(self):
        """Test timeshift download endpoint."""
        response = client.post(
            "/timeshift/download",
            data={
                "output": "1\n00:00:03,500 --> 00:00:06,500\nTest\n"
            }
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/octet-stream")
        assert "processed_subtitles.srt" in response.headers.get("content-disposition", "")


class TestMkv2srtEndpoints:
    """Tests for the mkv2srt endpoints."""

    def test_mkv2srt_page(self):
        """Test the mkv2srt page returns the form."""
        response = client.get("/mkv2srt")

        assert response.status_code == 200
        assert "mkv2srt.html" in response.text or response.headers["content-type"].startswith("text/html")

    def test_mkv2srt_submit_missing_file(self):
        """Test mkv2srt submission without MKV file."""
        response = client.post(
            "/mkv2srt",
            data={
                "language": "en",
                "output_file": "output.srt"
            }
        )

        # The form validation should show an error
        assert response.status_code == 200
        assert "error" in response.text.lower() or "upload" in response.text.lower()

    def test_mkv2srt_submit_with_file(self):
        """Test mkv2srt submission with MKV file."""
        # Create a mock MKV file
        mock_mkv_content = b'Mock MKV content'

        response = client.post(
            "/mkv2srt",
            data={
                "language": "en",
                "output_file": "output.srt"
            },
            files={
                "mkv_file": ("test.mkv", mock_mkv_content, "video/x-matroska")
            }
        )

        # This will likely fail if ffmpeg is not available, but should return a response
        assert response.status_code == 200


class TestTranslateEndpoints:
    """Tests for the translate endpoints."""

    def test_translate_page(self):
        """Test the translate page returns the form."""
        response = client.get("/translate")

        assert response.status_code == 200
        assert "translate.html" in response.text or response.headers["content-type"].startswith("text/html")

    def test_translate_submit_missing_file(self):
        """Test translate submission without SRT file."""
        response = client.post(
            "/translate",
            data={
                "chunk_size": "30",
                "api_base": "http://localhost:8080",
                "model_id": "local-model",
                "api_key": "dummy-key"
            }
        )

        # The form validation should show an error
        assert response.status_code == 200
        assert "error" in response.text.lower() or "upload" in response.text.lower()

    def test_translate_submit_with_file(self):
        """Test translate submission with SRT file."""
        response = client.post(
            "/translate",
            data={
                "srt_file": "1\n00:00:01,000 --> 00:00:04,000\nTest\n",
                "chunk_size": "30",
                "api_base": "http://localhost:8080",
                "model_id": "local-model",
                "api_key": "dummy-key"
            }
        )

        # This will likely fail if the API endpoint is not available, but should return a response
        assert response.status_code == 200

    def test_translate_submit_with_instructions(self):
        """Test translate submission with custom instructions."""
        # Read a sample instruction file
        instruction_file = Path("translation_instruction_prompts/subtitle_translate_-_en-es_-_default.txt")

        if instruction_file.exists():
            instructions = instruction_file.read_text(encoding='utf-8')
        else:
            instructions = "Default translation instructions"

        response = client.post(
            "/translate",
            data={
                "srt_file": "1\n00:00:01,000 --> 00:00:04,000\nTest\n",
                "instructions_file": str(instruction_file),
                "chunk_size": "30",
                "api_base": "http://localhost:8080",
                "model_id": "local-model",
                "api_key": "dummy-key"
            }
        )

        assert response.status_code == 200


class TestStaticFiles:
    """Tests for static file serving."""

    def test_favicon(self):
        """Test the favicon endpoint."""
        response = client.get("/favicon.ico")

        assert response.status_code == 200
        # Favicon might be a different content type depending on the file
        assert response.headers["content-type"].startswith("image/")

    def test_static_files(self):
        """Test static file serving."""
        response = client.get("/static/empty.txt")

        assert response.status_code == 200
        # The file is empty, so content should be empty
        assert response.text == "" or response.content == b""


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_endpoint(self):
        """Test that invalid endpoints return 404."""
        response = client.get("/nonexistent")

        assert response.status_code == 404

    def test_malformed_timestamp_in_timeshift(self):
        """Test handling of malformed timestamps in timeshift."""
        response = client.post(
            "/timeshift",
            data={
                "shift_seconds": "2.5",
                "srt_file": "1\nmalformed-timestamp --> 00:00:04,000\nTest\n"
            }
        )

        # Should handle gracefully
        assert response.status_code == 200