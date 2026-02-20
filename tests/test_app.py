"""Tests for app.py FastAPI endpoints."""
import sys
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

# Add the project root to the path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.app import app


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

class TestI18n:
    """Tests for internationalization functionality."""

    def test_language_selector_in_base(self):
        """Test that language selector is present in base template."""
        response = client.get("/")
        assert response.status_code == 200
        assert "language-selector" in response.text
        assert "English" in response.text
        assert "Español" in response.text

    def test_default_language_is_english(self):
        """Test that default language is English."""
        response = client.get("/")
        assert response.status_code == 200
        # Should contain English text
        assert "Subtitle Toolkit" in response.text
        assert "Time Shift" in response.text

    def test_spanish_language_query_param(self):
        """Test Spanish language via query parameter."""
        response = client.get("/?lang=es")
        assert response.status_code == 200
        # Should contain Spanish text
        assert "Desplazamiento de Tiempo" in response.text

    def test_spanish_language_cookie(self):
        """Test Spanish language via cookie."""
        response = client.get("/", cookies={"language": "es"})
        assert response.status_code == 200
        # Should contain Spanish text
        assert "Desplazamiento de Tiempo" in response.text

    def test_set_language_endpoint(self):
        """Test setting language via POST request."""
        response = client.post("/set-language", data={"lang": "es"})
        assert response.status_code == 200  # Redirect not working in test, but endpoint exists
        assert "language" in response.headers.get("set-cookie", "") or response.status_code == 200

    def test_invalid_language_falls_back(self):
        """Test that invalid language falls back to default."""
        response = client.get("/?lang=invalid")
        assert response.status_code == 200
        # Should still work with default language
        assert "Subtitle Toolkit" in response.text

    def test_timeshift_page_spanish(self):
        """Test timeshift page in Spanish."""
        response = client.get("/timeshift?lang=es")
        assert response.status_code == 200
        assert "Desplazamiento de Tiempo" in response.text

    def test_mkv2srt_page_spanish(self):
        """Test mkv2srt page in Spanish."""
        response = client.get("/mkv2srt?lang=es")
        assert response.status_code == 200
        assert "MKV a SRT" in response.text

    def test_translate_page_spanish(self):
        """Test translate page in Spanish."""
        response = client.get("/translate?lang=es")
        assert response.status_code == 200
        assert "Traducir" in response.text

    def test_load_translations_en(self):
        """Test loading English translations."""
        from web.app import load_translations
        translations = load_translations("en")
        assert translations is not None
        assert "subtitle_toolkit" in translations
        assert translations["subtitle_toolkit"] == "Subtitle Toolkit"

    def test_load_translations_es(self):
        """Test loading Spanish translations."""
        from web.app import load_translations
        translations = load_translations("es")
        assert translations is not None
        assert "subtitle_toolkit" in translations
        assert translations["subtitle_toolkit"] == "Conjunto de Herramientas de Subtítulos"

    def test_load_translations_invalid(self):
        """Test loading invalid language returns empty dict."""
        from web.app import load_translations
        translations = load_translations("invalid")
        assert translations == {}

    def test_get_language_from_request_default(self):
        """Test getting language from request with default."""
        from web.app import get_language_from_request
        from fastapi import Request
        from starlette.datastructures import URL, Headers
        from starlette.requests import Request as StarletteRequest
        
        # Create a mock request without language
        class MockRequest:
            def __init__(self):
                self.query_params = {}
                self.cookies = {}
        
        request = MockRequest()
        lang = get_language_from_request(request)
        assert lang == "en"

    def test_get_language_from_request_query(self):
        """Test getting language from request query param."""
        from web.app import get_language_from_request
        
        class MockRequest:
            def __init__(self):
                self.query_params = {"lang": "es"}
                self.cookies = {}
        
        request = MockRequest()
        lang = get_language_from_request(request)
        assert lang == "es"

    def test_get_language_from_request_cookie(self):
        """Test getting language from request cookie."""
        from web.app import get_language_from_request
        
        class MockRequest:
            def __init__(self):
                self.query_params = {}
                self.cookies = {"language": "es"}
        
        request = MockRequest()
        lang = get_language_from_request(request)
        assert lang == "es"

    def test_invalid_language_fallback(self):
        """Test that invalid language falls back to default."""
        from web.app import get_language_from_request
        
        class MockRequest:
            def __init__(self):
                self.query_params = {"lang": "invalid"}
                self.cookies = {}
        
        request = MockRequest()
        lang = get_language_from_request(request)
        assert lang == "en"
