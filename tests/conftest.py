"""Test configuration and fixtures for Subtitle Toolkit."""
import pytest
from pathlib import Path


# Sample SRT content for testing
SAMPLE_SRT = """1
00:00:01,000 --> 00:00:04,000
Hello, welcome to the subtitle toolkit.

2
00:00:05,000 --> 00:00:08,000
This is a test subtitle file.

3
00:00:09,000 --> 00:00:12,000
We can shift timestamps or translate them.
"""

SAMPLE_SRT_WITH_ASS_TAGS = r"""1
00:00:01,000 --> 00:00:04,000
{\an7}Centered text{\r}

2
00:00:05,000 --> 00:00:08,000
{\b1}Bold text{\r}{\i1}Italic text{\r}
"""

SAMPLE_SRT_WINDOWS_LINE_ENDINGS = "1\r\n00:00:01,000 --> 00:00:04,000\r\nHello Windows\r\n\r\n"


@pytest.fixture
def sample_srt_content():
    """Return sample SRT content."""
    return SAMPLE_SRT


@pytest.fixture
def sample_srt_with_ass_tags():
    """Return SRT content with ASS/SSA formatting tags."""
    return SAMPLE_SRT_WITH_ASS_TAGS


@pytest.fixture
def sample_srt_windows_line_endings():
    """Return SRT content with Windows line endings."""
    return SAMPLE_SRT_WINDOWS_LINE_ENDINGS


@pytest.fixture
def temp_srt_file(tmp_path, sample_srt_content):
    """Create a temporary SRT file."""
    srt_file = tmp_path / "test.srt"
    srt_file.write_text(sample_srt_content, encoding='utf-8')
    return srt_file


@pytest.fixture
def mock_api_response():
    """Return a mock OpenAI API response."""
    return {
        "choices": [
            {
                "message": {
                    "content": "1\n00:00:01,000 --> 00:00:04,000\nHola, bienvenido al toolkit de subtítulos.\n\n2\n00:00:05,000 --> 00:00:08,000\nEste es un archivo de subtítulos de prueba.\n\n3\n00:00:09,000 --> 00:00:12,000\nPodemos cambiar los tiempos o traducirlos.\n"
                }
            }
        ]
    }


# Register pytest-asyncio marker
def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")