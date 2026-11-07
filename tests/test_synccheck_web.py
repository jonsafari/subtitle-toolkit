#!/usr/bin/env python3
"""
Tests for the Sync Check and Sync Preview web endpoints.
"""
import io
import re
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from web.app import (
    app,
    SESSIONS,
    _remove_session,
    _is_browser_playable,
    _safe_video_filename,
)

PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_MP4 = PROJECT_ROOT / "sample_media_files" / "sample.mp4"

client = TestClient(app)

# The sample video is ~1.7 s long; keep cues inside it.
SAMPLE_SRT = (
    "1\n00:00:00,200 --> 00:00:01,200\nHello\n\n"
    "2\n00:00:01,000 --> 00:00:01,600\nWorld\n"
)


@pytest.fixture(autouse=True)
def cleanup_sessions():
    """Remove any preview sessions created during a test."""
    before = set(SESSIONS.keys())
    yield
    for sid in set(SESSIONS.keys()) - before:
        _remove_session(sid)


def wait_for_session(sid, timeout=30.0):
    """Poll a session until it is ready or errors out."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        response = client.get(f"/sync-preview/session/{sid}")
        assert response.status_code == 200
        last = response.json()
        if last["status"] in ("ready", "error"):
            return last
        time.sleep(0.2)
    raise TimeoutError(f"session {sid} did not become ready: {last}")


def create_session_via_upload():
    """Upload the sample video + SRT and return the session id."""
    with open(SAMPLE_MP4, "rb") as fh:
        response = client.post(
            "/sync-preview/session",
            files={
                "video_file": ("sample.mp4", fh, "video/mp4"),
                "srt_file": ("test.srt", io.BytesIO(SAMPLE_SRT.encode("utf-8")),
                             "text/plain"),
            },
            follow_redirects=False,
        )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "/sync-preview?session=" in location
    return location.split("session=")[1]


class TestCheckPages:
    """Tests for the Sync Check pages."""

    def test_check_page(self):
        response = client.get("/check")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "check" in response.text.lower()

    def test_sync_preview_page(self):
        response = client.get("/sync-preview")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "sync-preview" in response.text.lower() or "preview" in response.text.lower()

    def test_sync_preview_page_with_unknown_session(self):
        # Should render the page; the JS poller will get a 404 for the session.
        response = client.get("/sync-preview?session=does-not-exist")
        assert response.status_code == 200

    def test_index_lists_new_tools(self):
        response = client.get("/")
        assert response.status_code == 200
        assert "/check" in response.text
        assert "/sync-preview" in response.text


class TestCheckSubmit:
    """Tests for POST /check."""

    def test_check_submit_missing_files(self):
        response = client.post("/check", data={})
        assert response.status_code == 200
        assert "error" in response.text.lower() or "upload" in response.text.lower()

    @pytest.mark.skipif(not SAMPLE_MP4.exists(), reason="sample.mp4 not available")
    def test_check_submit_with_files(self):
        with open(SAMPLE_MP4, "rb") as fh:
            response = client.post(
                "/check",
                files={
                    "video_file": ("sample.mp4", fh, "video/mp4"),
                    "srt_file": ("test.srt", io.BytesIO(SAMPLE_SRT.encode("utf-8")),
                                 "text/plain"),
                },
            )
        assert response.status_code == 200
        # The report is rendered in a <pre> block.
        assert "<pre" in response.text
        # A session was created for the preview link.
        assert "/sync-preview?session=" in response.text
        # Sample video has no embedded subtitles.
        assert "embedded subtitle tracks: none" in response.text

    @pytest.mark.skipif(not SAMPLE_MP4.exists(), reason="sample.mp4 not available")
    def test_check_submit_bad_srt(self):
        with open(SAMPLE_MP4, "rb") as fh:
            response = client.post(
                "/check",
                files={
                    "video_file": ("sample.mp4", fh, "video/mp4"),
                    "srt_file": ("bad.srt", io.BytesIO(b"not a srt file"),
                                 "text/plain"),
                },
            )
        # Should render a report with a no-cues flag, not crash.
        assert response.status_code == 200
        assert "<pre" in response.text


class TestCheckApplyFix:
    """Tests for POST /check/apply-fix."""

    def test_apply_fix_missing_session(self):
        response = client.post(
            "/check/apply-fix",
            data={"session": "nope", "t1": "0", "o1": "1", "t2": "10", "o2": "1"},
        )
        assert response.status_code == 200
        assert "Session not found" in response.text

    def test_apply_fix_no_session(self):
        response = client.post(
            "/check/apply-fix",
            data={"t1": "0", "o1": "1", "t2": "10", "o2": "1"},
        )
        assert response.status_code == 200
        assert "Session not found" in response.text

    @pytest.mark.skipif(not SAMPLE_MP4.exists(), reason="sample.mp4 not available")
    def test_apply_fix_with_session(self):
        sid = create_session_via_upload()
        status = wait_for_session(sid)
        assert status["status"] == "ready"

        response = client.post(
            "/check/apply-fix",
            data={"session": sid, "t1": "0", "o1": "1", "t2": "10", "o2": "1"},
        )
        assert response.status_code == 200
        # Constant +1 s offset: 00:00:00,200 becomes 00:00:01,200.
        assert "00:00:01,200 --&gt; 00:00:02,200" in response.text


class TestPreviewSession:
    """Tests for the preview session lifecycle."""

    @pytest.mark.skipif(not SAMPLE_MP4.exists(), reason="sample.mp4 not available")
    def test_session_upload_lifecycle(self):
        sid = create_session_via_upload()
        status = wait_for_session(sid)
        assert status["status"] == "ready"
        assert "Hello" in status["srt"]
        assert status["probe"]["video"]["codec"] == "h264"
        assert status["proxy_url"]  # set when ready

    def test_session_status_unknown(self):
        response = client.get("/sync-preview/session/unknown-id")
        assert response.status_code == 404

    @pytest.mark.skipif(not SAMPLE_MP4.exists(), reason="sample.mp4 not available")
    def test_session_local_paths(self):
        # Local-path mode is allowed from the test client (localhost).
        srt_file = Path("/tmp/synccheck_web_test.srt")
        srt_file.write_text(SAMPLE_SRT, encoding="utf-8")
        try:
            response = client.post(
                "/sync-preview/session",
                data={
                    "video_path": str(SAMPLE_MP4),
                    "srt_path": str(srt_file),
                },
                follow_redirects=False,
            )
            assert response.status_code == 303
            sid = response.headers["location"].split("session=")[1]
            status = wait_for_session(sid)
            assert status["status"] == "ready"
            assert "Hello" in status["srt"]
        finally:
            srt_file.unlink(missing_ok=True)

    @pytest.mark.skipif(not SAMPLE_MP4.exists(), reason="sample.mp4 not available")
    def test_session_local_path_missing_file(self):
        response = client.post(
            "/sync-preview/session",
            data={
                "video_path": "/nonexistent/video.mp4",
                "srt_path": "/nonexistent/subs.srt",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "not found" in response.text.lower()

    def test_session_no_input(self):
        response = client.post("/sync-preview/session", data={}, follow_redirects=False)
        assert response.status_code == 200
        assert "upload" in response.text.lower()


class TestPreviewProxy:
    """Tests for the media proxy endpoint."""

    @pytest.mark.skipif(not SAMPLE_MP4.exists(), reason="sample.mp4 not available")
    def test_proxy_serves_video(self):
        sid = create_session_via_upload()
        status = wait_for_session(sid)
        assert status["status"] == "ready"

        response = client.get(f"/sync-preview/session/{sid}/proxy")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("video/")
        assert len(response.content) > 1000

    def test_proxy_unknown_session(self):
        response = client.get("/sync-preview/session/nope/proxy")
        assert response.status_code == 404

    @pytest.mark.skipif(not SAMPLE_MP4.exists(), reason="sample.mp4 not available")
    def test_proxy_before_ready(self):
        # Create a session and immediately hit the proxy; it must not crash.
        sid = create_session_via_upload()
        response = client.get(f"/sync-preview/session/{sid}/proxy")
        # Either ready (200), still preparing (409), or no proxy yet (404).
        assert response.status_code in (200, 404, 409)


class TestPreviewPageJS:
    """Tests for the client-side JS embedded in the Sync Preview page."""

    @pytest.mark.skipif(not SAMPLE_MP4.exists(), reason="sample.mp4 not available")
    def test_parse_time_accepts_missing_milliseconds(self):
        """The page's parseTime must accept HH:MM:SS without a ms fraction.

        Regression: SRT files whose timestamps omit the millisecond part
        (e.g. "00:00:01 --> 00:00:02") used to parse to zero cues, so no
        subtitles ever appeared over the video.
        """
        sid = create_session_via_upload()
        wait_for_session(sid)
        html = client.get(f"/sync-preview?session={sid}").text

        m = re.search(r"function parseTime\(str\)\s*\{.*?\.match\((/\S+?/)\)", html, re.S)
        assert m, "could not locate the parseTime regex in the preview page"
        pattern = m.group(1).strip("/")
        py_re = re.compile(pattern)

        # The bug: timestamps without milliseconds must now match.
        assert py_re.match("00:00:01"), "parseTime must accept HH:MM:SS (no ms)"
        # Existing forms must still match.
        assert py_re.match("00:00:01,500"), "parseTime must accept HH:MM:SS,mmm"
        assert py_re.match("00:00:01.500"), "parseTime must accept HH:MM:SS.mmm"


class TestPreviewApply:
    """Tests for POST /sync-preview/apply."""

    def test_apply_missing_srt(self):
        response = client.post(
            "/sync-preview/apply",
            data={"t1": "0", "o1": "1", "t2": "10", "o2": "1"},
        )
        assert response.status_code == 200
        assert "No subtitle content provided" in response.text

    def test_apply_same_time_points(self):
        # Both sync points at the same time => constant offset (no drift).
        response = client.post(
            "/sync-preview/apply",
            data={"srt": SAMPLE_SRT, "t1": "0", "o1": "1", "t2": "0", "o2": "5"},
        )
        assert response.status_code == 200
        # Constant +1 s offset.
        assert "00:00:01,200 --&gt; 00:00:02,200" in response.text

    def test_apply_constant_offset(self):
        response = client.post(
            "/sync-preview/apply",
            data={"srt": SAMPLE_SRT, "t1": "0", "o1": "1", "t2": "10", "o2": "1"},
        )
        assert response.status_code == 200
        # 00:00:00,200 + 1 s => 00:00:01,200
        assert "00:00:01,200 --&gt; 00:00:02,200" in response.text
        assert "00:00:02,000 --&gt; 00:00:02,600" in response.text

    def test_apply_with_drift(self):
        # +1 s at t=0, +2 s at t=10 s => +0.1 s/s drift.
        # Cue 2 starts at 1.0 s => +1.1 s => 00:00:02,100
        response = client.post(
            "/sync-preview/apply",
            data={"srt": SAMPLE_SRT, "t1": "0", "o1": "1", "t2": "10", "o2": "2"},
        )
        assert response.status_code == 200
        assert "00:00:02,100" in response.text

    def test_apply_swapped_points(self):
        # Points given in reverse order should still work (same transform as
        # +1 s at t=0, +2 s at t=10 s).
        response = client.post(
            "/sync-preview/apply",
            data={"srt": SAMPLE_SRT, "t1": "10", "o1": "2", "t2": "0", "o2": "1"},
        )
        assert response.status_code == 200
        # Cue 1: 0.2 s + 1.02 s => 00:00:01,220 ; 1.2 s + 1.12 s => 00:00:02,320
        assert "00:00:01,220 --&gt; 00:00:02,320" in response.text

    def test_apply_negative_offset(self):
        response = client.post(
            "/sync-preview/apply",
            data={"srt": SAMPLE_SRT, "t1": "0", "o1": "-1", "t2": "10", "o2": "-1"},
        )
        assert response.status_code == 200
        # 00:00:01,000 - 1 s => 00:00:00,000
        assert "00:00:00,000 --&gt; 00:00:00,600" in response.text


class TestPreviewDownload:
    """Tests for POST /sync-preview/download."""

    def test_download(self):
        response = client.post(
            "/sync-preview/download",
            data={"output": SAMPLE_SRT, "filename": "fixed.srt"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"
        assert "fixed.srt" in response.headers.get("content-disposition", "")
        assert response.content.decode("utf-8") == SAMPLE_SRT

    def test_download_empty_output(self):
        # Empty output is handled gracefully (renders the page, no crash).
        response = client.post(
            "/sync-preview/download",
            data={"output": "", "filename": "empty.srt"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")


class TestBrowserPlayable:
    """Tests for _is_browser_playable (serve original vs remux)."""

    def test_mp4_h264_aac(self):
        assert _is_browser_playable("mov,mp4,m4a,3gp,3g2,mj2", "h264", {"aac"},
                                    Path("v.mp4"))

    def test_mkv_is_never_served_directly(self):
        # ffprobe reports MKV and WebM identically; MKV must be remuxed.
        assert not _is_browser_playable("matroska,webm", "h264", {"aac"},
                                        Path("v.mkv"))

    def test_webm_vp9_opus(self):
        assert _is_browser_playable("matroska,webm", "vp9", {"opus"},
                                    Path("v.webm"))

    def test_no_extension_never_served_directly(self):
        # Uploaded files without a recognizable extension are remuxed.
        assert not _is_browser_playable("mov,mp4,m4a,3gp,3g2,mj2", "h264",
                                        {"aac"}, Path("video"))

    def test_bad_video_codec(self):
        assert not _is_browser_playable("mov,mp4,m4a,3gp,3g2,mj2", "mpeg4",
                                        {"aac"}, Path("v.mp4"))

    def test_bad_audio_codec(self):
        assert not _is_browser_playable("mov,mp4,m4a,3gp,3g2,mj2", "h264",
                                        {"ac3"}, Path("v.mp4"))

    def test_no_audio_is_ok(self):
        assert _is_browser_playable("mov,mp4,m4a,3gp,3g2,mj2", "h264", set(),
                                    Path("v.mp4"))


class TestSafeVideoFilename:
    """Tests for _safe_video_filename (keep a safe extension)."""

    def test_keeps_known_extensions(self):
        assert _safe_video_filename("movie.MP4") == "video.mp4"
        assert _safe_video_filename("movie.mkv") == "video.mkv"
        assert _safe_video_filename("movie.webm") == "video.webm"

    def test_drops_unknown_extensions(self):
        assert _safe_video_filename("movie.xyz") == "video"
        assert _safe_video_filename("") == "video"
        assert _safe_video_filename(None) == "video"
