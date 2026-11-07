#!/usr/bin/env python3
"""
Tests for the synccheck module (Sync Check diagnostics).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from synccheck import (
    Cue,
    Report,
    fps_fraction_to_float,
    probe_video,
    parse_srt_cues,
    analyze_srt,
    normalize_text,
    drift_scenarios,
    compare_with_embedded,
    build_report,
    ms_to_ts,
    point_time,
    format_report,
    run_check,
)

PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_MP4 = PROJECT_ROOT / "sample_media_files" / "sample.mp4"


def make_cues(starts_ms, dur_ms=2000, text=None):
    """Build a list of cues with the given start times."""
    cues = []
    for i, s in enumerate(starts_ms):
        t = (text or [f"line {i}"] * len(starts_ms))[i]
        cues.append(Cue(start_ms=s, end_ms=s + dur_ms, text=t))
    return cues


class TestFpsFractionToFloat:
    """Tests for fps_fraction_to_float."""

    def test_ntsc_fraction(self):
        assert abs(fps_fraction_to_float("24000/1001") - 23.976024) < 0.001

    def test_plain_number(self):
        assert fps_fraction_to_float("30") == 30.0

    def test_none(self):
        assert fps_fraction_to_float(None) is None

    def test_empty(self):
        assert fps_fraction_to_float("") is None

    def test_invalid(self):
        assert fps_fraction_to_float("abc") is None

    def test_zero_denominator(self):
        assert fps_fraction_to_float("30/0") is None

    def test_ffprobe_unknown(self):
        # ffprobe reports "0/0" for unknown rates
        assert fps_fraction_to_float("0/0") is None


class TestParseSrtCues:
    """Tests for parse_srt_cues."""

    def test_basic(self):
        content = (
            "1\n00:00:01,000 --> 00:00:04,000\nHello\n\n"
            "2\n00:00:05,500 --> 00:00:08,000\nWorld\n"
        )
        cues = parse_srt_cues(content)
        assert len(cues) == 2
        assert cues[0].start_ms == 1000
        assert cues[0].end_ms == 4000
        assert cues[0].text == "Hello"
        assert cues[1].start_ms == 5500
        assert cues[1].text == "World"

    def test_index_lines_optional(self):
        content = "00:00:01,000 --> 00:00:04,000\nHello\n\n"
        cues = parse_srt_cues(content)
        assert len(cues) == 1
        assert cues[0].text == "Hello"

    def test_period_milliseconds(self):
        content = "1\n00:00:01.250 --> 00:00:04.000\nHello\n"
        cues = parse_srt_cues(content)
        assert cues[0].start_ms == 1250

    def test_crlf_line_endings(self):
        content = "1\r\n00:00:01,000 --> 00:00:04,000\r\nHello\r\n\r\n"
        cues = parse_srt_cues(content)
        assert len(cues) == 1
        assert cues[0].text == "Hello"

    def test_multiline_text(self):
        content = "1\n00:00:01,000 --> 00:00:04,000\nLine one\nLine two\n\n"
        cues = parse_srt_cues(content)
        assert cues[0].text == "Line one\nLine two"

    def test_empty(self):
        assert parse_srt_cues("") == []
        assert parse_srt_cues("no cues here\n") == []


class TestAnalyzeSrt:
    """Tests for analyze_srt."""

    def test_basic(self):
        content = (
            "1\n00:00:01,000 --> 00:00:04,000\nHello\n\n"
            "2\n00:01:00,000 --> 00:01:02,000\nWorld\n"
        )
        info = analyze_srt(content)
        assert info["cue_count"] == 2
        assert info["first_start"] == 1000
        assert info["last_end"] == 62000
        assert info["span"] == 61000
        assert info["texts"] == ["hello", "world"]

    def test_empty(self):
        info = analyze_srt("")
        assert info["cue_count"] == 0
        assert info["first_start"] is None
        assert info["last_end"] is None
        assert info["span"] is None


class TestNormalizeText:
    """Tests for normalize_text."""

    def test_lowercase_and_punctuation(self):
        assert normalize_text("Hello, World!") == "hello world"

    def test_html_tags_stripped(self):
        assert normalize_text("<i>Hello</i> World") == "hello world"

    def test_ass_tags_stripped(self):
        assert normalize_text(r"{\an7}Centered{\r} text") == "centered text"


class TestDriftScenarios:
    """Tests for drift_scenarios."""

    def test_24fps_video(self):
        scenarios = drift_scenarios(24.0)
        fps_list = [s["subs_fps"] for s in scenarios]
        # 24 itself is excluded
        assert 24.0 not in fps_list
        # 23.976 is the closest (smallest drift)
        assert fps_list[0] == 23.976
        # Sorted by absolute drift
        drifts = [abs(s["drift_per_hour"]) for s in scenarios]
        assert drifts == sorted(drifts)

    def test_drift_sign(self):
        # Subs authored faster than the video play rate => subtitles get LATER.
        scenarios = drift_scenarios(24.0, top=5)
        s30 = next(s for s in scenarios if s["subs_fps"] == 30.0)
        assert s30["drift_per_hour"] > 0
        # Subs authored slower than the video play rate => subtitles get EARLIER.
        s23976 = next(s for s in scenarios if s["subs_fps"] == 23.976)
        assert s23976["drift_per_hour"] < 0

    def test_24fps_drift_magnitude(self):
        # 23.976 subs on a 24fps video: ~3.6 s/hour of drift.
        scenarios = drift_scenarios(24.0)
        s = next(x for x in scenarios if x["subs_fps"] == 23.976)
        assert abs(abs(s["drift_per_hour"]) - 3.6) < 0.1

    def test_no_fps(self):
        assert drift_scenarios(None) == []
        assert drift_scenarios(0) == []


class TestCompareWithEmbedded:
    """Tests for compare_with_embedded."""

    def test_empty_inputs(self):
        assert compare_with_embedded([], []) is None
        assert compare_with_embedded(make_cues([0]), []) is None

    def test_exact_match(self):
        emb = make_cues([i * 10000 for i in range(10)])
        ext = make_cues([i * 10000 for i in range(10)])
        result = compare_with_embedded(ext, emb)
        assert result["match"] is True
        assert abs(result["offset_ms"]) < 1
        assert abs(result["rate"]) < 1e-6
        assert abs(result["drift_per_hour"]) < 0.01

    def test_constant_offset(self):
        emb = make_cues([i * 10000 for i in range(10)])
        ext = make_cues([i * 10000 + 2000 for i in range(10)])
        result = compare_with_embedded(ext, emb)
        assert result["match"] is True
        assert abs(result["offset_ms"] - 2000) < 1
        assert abs(result["rate"]) < 1e-6

    def test_drift(self):
        # External cues drift 1ms per 1ms of time (3.6 s/hour late).
        emb = make_cues([i * 10000 for i in range(20)])
        ext = make_cues([i * 10000 + int(i * 10000 * 0.001) for i in range(20)])
        result = compare_with_embedded(ext, emb)
        assert result["match"] is True
        assert abs(result["offset_ms"]) < 50
        assert abs(result["rate"] - 0.001) < 0.0002
        assert abs(result["drift_per_hour"] - 3.6) < 0.5

    def test_text_mismatch(self):
        emb = make_cues([i * 10000 for i in range(10)],
                        text=[f"embedded line {i}" for i in range(10)])
        ext = make_cues([i * 10000 for i in range(10)],
                        text=[f"totally different text {i}" for i in range(10)])
        result = compare_with_embedded(ext, emb)
        assert result["match"] is False
        assert result["reason"] == "text"

    def test_cue_count_mismatch(self):
        emb = make_cues([i * 10000 for i in range(20)])
        ext = make_cues([i * 10000 for i in range(5)])
        result = compare_with_embedded(ext, emb)
        assert result["match"] is False
        assert result["reason"] == "cue_count"
        assert result["n_embedded"] == 20
        assert result["n_external"] == 5


class TestBuildReport:
    """Tests for build_report."""

    VIDEO = {
        "duration": 3600.0,
        "container": "matroska,webm",
        "video": {"codec": "h264", "fps": 24.0, "width": 1920, "height": 1080},
        "audio": [{"codec": "aac"}],
        "subtitles": [],
    }
    SRT = {
        "cue_count": 10,
        "first_start": 1000,
        "last_end": 3599000,
        "span": 3598000,
        "texts": [],
    }

    def test_no_embedded_gives_possible_misalignment(self):
        report = build_report(Path("v.mp4"), Path("s.srt"), self.VIDEO, self.SRT)
        assert report.verdict == "possible_misalignment"

    def test_embedded_match_large_offset(self):
        embedded = {
            "match": True, "reason": None, "n_external": 10, "n_embedded": 10,
            "median_similarity": 0.95, "n_cues": 10,
            "offset_ms": 2000.0, "rate": 0.0, "drift_per_hour": 0.0,
        }
        report = build_report(Path("v.mp4"), Path("s.srt"), self.VIDEO, self.SRT,
                              embedded=embedded)
        assert report.verdict == "fix_available"
        assert report.suggested_fix is not None
        # External is 2 s late => correction is -2 s everywhere.
        assert abs(report.suggested_fix["o1"] - (-2.0)) < 0.01
        assert abs(report.suggested_fix["o2"] - (-2.0)) < 0.01

    def test_embedded_match_small_offset_is_ok(self):
        embedded = {
            "match": True, "reason": None, "n_external": 10, "n_embedded": 10,
            "median_similarity": 0.95, "n_cues": 10,
            "offset_ms": 100.0, "rate": 0.0, "drift_per_hour": 0.0,
        }
        report = build_report(Path("v.mp4"), Path("s.srt"), self.VIDEO, self.SRT,
                              embedded=embedded)
        assert report.verdict == "ok"

    def test_embedded_match_drift(self):
        # Classic 23.976-on-24 drift: 3.6 s/hour.
        embedded = {
            "match": True, "reason": None, "n_external": 10, "n_embedded": 10,
            "median_similarity": 0.95, "n_cues": 10,
            "offset_ms": 0.0, "rate": 0.001, "drift_per_hour": 3.6,
        }
        report = build_report(Path("v.mp4"), Path("s.srt"), self.VIDEO, self.SRT,
                              embedded=embedded)
        assert report.verdict == "fix_available"
        fx = report.suggested_fix
        assert abs(fx["o1"]) < 0.01
        # At the end of the video the correction is ~-3.6 s.
        assert abs(fx["o2"] - (-3.6)) < 0.1

    def test_srt_longer_than_video(self):
        srt = dict(self.SRT, last_end=7200000)  # 2 h SRT, 1 h video
        report = build_report(Path("v.mp4"), Path("s.srt"), self.VIDEO, srt)
        assert report.verdict == "likely_different_version"
        assert any(f["key"] == "srt_longer_than_video" for f in report.flags)

    def test_no_cues(self):
        srt = {"cue_count": 0, "first_start": None, "last_end": None,
               "span": None, "texts": []}
        report = build_report(Path("v.mp4"), Path("s.srt"), self.VIDEO, srt)
        assert any(f["key"] == "no_cues" for f in report.flags)

    def test_embedded_cue_count_mismatch(self):
        embedded = {
            "match": False, "reason": "cue_count", "n_external": 10,
            "n_embedded": 500, "median_similarity": None, "n_cues": 0,
            "offset_ms": None, "rate": None, "drift_per_hour": None,
        }
        report = build_report(Path("v.mp4"), Path("s.srt"), self.VIDEO, self.SRT,
                              embedded=embedded)
        assert report.verdict == "likely_different_version"

    def test_scenarios_present_for_fps(self):
        report = build_report(Path("v.mp4"), Path("s.srt"), self.VIDEO, self.SRT)
        assert len(report.scenarios) > 0
        assert all("drift_per_hour" in s for s in report.scenarios)

    def test_report_to_dict_roundtrip(self):
        report = build_report(Path("v.mp4"), Path("s.srt"), self.VIDEO, self.SRT)
        d = report.to_dict()
        # Must be JSON-serializable
        json.dumps(d)
        assert d["verdict"] == "possible_misalignment"


class TestMsToTs:
    """Tests for ms_to_ts."""

    def test_basic(self):
        assert ms_to_ts(0) == "00:00:00"
        assert ms_to_ts(61000) == "00:01:01"
        assert ms_to_ts(3661000) == "01:01:01"


class TestPointTime:
    """Tests for point_time (times for autosync --points arguments)."""

    def test_whole_seconds(self):
        assert point_time(0.0) == "00:00:00"
        assert point_time(11.0) == "00:00:11"
        assert point_time(3600.0) == "01:00:00"

    def test_fractional_seconds(self):
        assert point_time(10.5) == "00:00:10.500"
        assert point_time(3670.25) == "01:01:10.250"
        assert point_time(59.999) == "00:00:59.999"

    def test_round_trips_through_parse_time(self):
        from autosync import parse_time
        for value in (0.0, 11.006, 10.5, 3670.25, 59.999):
            assert abs(parse_time(point_time(value)) - value * 1000) < 1.0


class TestFormatReport:
    """Tests for format_report."""

    def test_contains_key_sections(self):
        report = build_report(
            Path("movie.mkv"), Path("movie.en.srt"),
            TestBuildReport.VIDEO, TestBuildReport.SRT,
        )
        text = format_report(report)
        assert "movie.mkv" in text
        assert "movie.en.srt" in text
        assert "Verdict:" in text
        assert "embedded subtitle tracks: none" in text

    def test_apply_hint_with_suggested_fix(self):
        embedded = {
            "match": True, "reason": None, "n_external": 10, "n_embedded": 10,
            "median_similarity": 0.95, "n_cues": 10,
            "offset_ms": 2000.0, "rate": 0.0, "drift_per_hour": 0.0,
        }
        report = build_report(
            Path("v.mp4"), Path("s.srt"),
            TestBuildReport.VIDEO, TestBuildReport.SRT, embedded=embedded,
        )
        text = format_report(report)
        assert "Suggested fix" in text
        assert "Apply: subtitle-tk autosync --points" in text
        # The suggested points must be parseable by autosync.
        from autosync import parse_time
        import re
        m = re.search(r"--points (\S+):(-?\S+) (\S+):(-?\S+)", text)
        assert m is not None
        t1, o1, t2, o2 = m.groups()
        assert parse_time(t1) == 0.0
        assert abs(float(o1) - (-2.0)) < 0.01
        assert parse_time(t2) > 0
        assert abs(float(o2) - (-2.0)) < 0.01


@pytest.mark.skipif(not SAMPLE_MP4.exists(), reason="sample.mp4 not available")
class TestProbeVideo:
    """Tests for probe_video against the real sample file."""

    def test_probe_sample(self):
        probe = probe_video(SAMPLE_MP4)
        assert probe["duration"] is not None
        assert probe["duration"] > 1.0
        assert probe["video"] is not None
        assert probe["video"]["codec"] == "h264"
        assert probe["video"]["fps"] is not None
        assert probe["subtitles"] == []

    def test_probe_missing_file(self):
        with pytest.raises(FileNotFoundError):
            probe_video(Path("/nonexistent/file.mp4"))


@pytest.mark.skipif(not SAMPLE_MP4.exists(), reason="sample.mp4 not available")
class TestRunCheck:
    """End-to-end tests for run_check (uses ffprobe)."""

    def test_run_check_sample(self, tmp_path):
        srt = tmp_path / "test.srt"
        srt.write_text(
            "1\n00:00:00,500 --> 00:00:01,500\nHello\n", encoding="utf-8"
        )
        report = run_check(SAMPLE_MP4, srt)
        assert report.verdict in ("possible_misalignment", "ok",
                                  "fix_available", "likely_different_version")
        assert report.srt["cue_count"] == 1
        # No embedded subtitles in the sample => no embedded comparison.
        assert report.embedded is None

    def test_run_check_json_serializable(self, tmp_path):
        srt = tmp_path / "test.srt"
        srt.write_text(
            "1\n00:00:00,500 --> 00:00:01,500\nHello\n", encoding="utf-8"
        )
        report = run_check(SAMPLE_MP4, srt)
        json.dumps(report.to_dict())


@pytest.mark.skipif(
    subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0,
    reason="ffmpeg not available",
)
class TestEmbeddedComparisonEndToEnd:
    """Generate a video with an embedded subtitle track and verify detection."""

    def _make_video_with_subs(self, tmp_path):
        """Create a 12 s test video with an embedded SRT track."""
        video = tmp_path / "test.mkv"
        srt = tmp_path / "embedded.srt"
        srt.write_text(
            "1\n00:00:01,000 --> 00:00:03,000\nFirst line\n\n"
            "2\n00:00:05,000 --> 00:00:07,000\nSecond line\n\n"
            "3\n00:00:09,000 --> 00:00:11,000\nThird line\n",
            encoding="utf-8",
        )
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=320x240:d=12:r=25",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
            "-i", str(srt),
            "-c:v", "libx264", "-preset", "veryfast",
            "-c:a", "aac",
            "-c:s", "srt",
            "-shortest",
            str(video),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return video, srt

    def test_detects_offset_against_embedded(self, tmp_path):
        video, _ = self._make_video_with_subs(tmp_path)

        # External SRT is the same text but 2 s late.
        ext = tmp_path / "external.srt"
        ext.write_text(
            "1\n00:00:03,000 --> 00:00:05,000\nFirst line\n\n"
            "2\n00:00:07,000 --> 00:00:09,000\nSecond line\n\n"
            "3\n00:00:11,000 --> 00:00:12,000\nThird line\n",
            encoding="utf-8",
        )
        report = run_check(video, ext)
        assert report.embedded is not None
        assert report.embedded["match"] is True
        assert abs(report.embedded["offset_ms"] - 2000) < 150
        assert report.verdict == "fix_available"
        assert report.suggested_fix is not None
        assert abs(report.suggested_fix["o1"] - (-2.0)) < 0.2

    def test_in_sync_embedded(self, tmp_path):
        video, embedded_srt = self._make_video_with_subs(tmp_path)
        # External SRT identical to the embedded track.
        ext = tmp_path / "external.srt"
        ext.write_text(embedded_srt.read_text(encoding="utf-8"), encoding="utf-8")
        report = run_check(video, ext)
        assert report.embedded is not None
        assert report.embedded["match"] is True
        assert abs(report.embedded["offset_ms"]) < 150
        assert report.verdict == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
