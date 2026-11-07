#!/usr/bin/env python3
"""
Sync Check - diagnose out-of-sync subtitles before you sit down to watch.

Given a video file and one or more downloaded .srt files, this tool quickly
reports:

  * video info (duration, frame rate, embedded subtitle tracks)
  * SRT info (cue count, first/last cue, total span)
  * likely problems (constant offset, frame-rate drift, wrong version/cut)
  * a suggested fix (offset + drift) when the video contains an embedded
    subtitle track that can be compared against the downloaded SRT

The comparison against an embedded track is deterministic (no AI): if the
video already carries a subtitle track that is in sync, we align the two cue
lists by text and fit a linear time correction.

Sign convention (used everywhere in this toolkit):
  A positive correction moves subtitles LATER (to bigger timestamps).
  If subtitles appear too early, use a positive correction.
  If subtitles appear too late, use a negative correction.

Usage (standalone):
    python3 synccheck.py VIDEO [SRT ...] [--json] [--no-embedded]
"""

import argparse
import difflib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Common frame rates subtitles are authored at.
COMMON_SUB_FPS = [23.976, 24.0, 25.0, 29.97, 30.0]

# Tolerances for matching the video fps against a common rate.
FPS_MATCH_TOLERANCE = 0.05  # +/- 0.05 fps


@dataclass
class Cue:
    """A single parsed subtitle cue."""
    start_ms: int
    end_ms: int
    text: str


@dataclass
class Report:
    """Result of a sync check for one (video, srt) pair."""
    video_path: str
    srt_path: str
    video: Dict = field(default_factory=dict)
    srt: Dict = field(default_factory=dict)
    flags: List[Dict] = field(default_factory=list)   # [{level, key, message}]
    embedded: Optional[Dict] = None                    # comparison result
    scenarios: List[Dict] = field(default_factory=list)  # fps drift scenarios
    verdict: str = "ok"                                # see build_report
    suggested_fix: Optional[Dict] = None               # {t1, o1, t2, o2} seconds

    def to_dict(self) -> Dict:
        return {
            "video_path": self.video_path,
            "srt_path": self.srt_path,
            "video": self.video,
            "srt": self.srt,
            "flags": self.flags,
            "embedded": self.embedded,
            "scenarios": self.scenarios,
            "verdict": self.verdict,
            "suggested_fix": self.suggested_fix,
        }


def fps_fraction_to_float(fraction: Optional[str]) -> Optional[float]:
    """Convert an ffprobe frame-rate fraction like '24000/1001' to a float.

    Args:
        fraction: Frame rate as 'num/den' or a plain number.

    Returns:
        Frame rate as float, or None if unparseable/zero.
    """
    if not fraction:
        return None
    fraction = fraction.strip()
    try:
        if "/" in fraction:
            num, den = fraction.split("/", 1)
            den_f = float(den)
            if den_f == 0:
                return None
            return float(num) / den_f
        return float(fraction)
    except (ValueError, ZeroDivisionError):
        return None


def probe_video(video_path: Path) -> Dict:
    """Probe a video file with ffprobe.

    Args:
        video_path: Path to the video file.

    Returns:
        Dict with keys:
            path, duration (seconds or None), container,
            video: {codec, fps, r_frame_rate, avg_frame_rate, width, height} or None,
            audio: [{codec, ...}],
            subtitles: [{index, language, codec, title, forced}]

    Raises:
        FileNotFoundError: If the file does not exist.
        RuntimeError: If ffprobe is missing or fails.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise RuntimeError(
            "ffprobe not found. Install ffmpeg (https://ffmpeg.org) to use sync check."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffprobe timed out on {video_path}")

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {video_path}: {result.stderr.strip()[:300]}")

    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Could not parse ffprobe output: {e}")

    fmt = info.get("format", {})
    duration = None
    if fmt.get("duration"):
        try:
            duration = float(fmt["duration"])
        except ValueError:
            duration = None

    video_stream = None
    audio_streams = []
    subtitle_streams = []
    for stream in info.get("streams", []):
        ctype = stream.get("codec_type")
        if ctype == "video" and video_stream is None:
            r = fps_fraction_to_float(stream.get("r_frame_rate"))
            avg = fps_fraction_to_float(stream.get("avg_frame_rate"))
            # Prefer r_frame_rate (actual), fall back to avg, skip 0/unknown.
            fps = r if (r and r > 0) else (avg if (avg and avg > 0) else None)
            video_stream = {
                "codec": stream.get("codec_name"),
                "fps": round(fps, 5) if fps else None,
                "r_frame_rate": stream.get("r_frame_rate"),
                "avg_frame_rate": stream.get("avg_frame_rate"),
                "width": stream.get("width"),
                "height": stream.get("height"),
            }
        elif ctype == "audio":
            audio_streams.append({"codec": stream.get("codec_name")})
        elif ctype == "subtitle":
            tags = stream.get("tags", {})
            subtitle_streams.append({
                "index": stream.get("index"),
                "language": tags.get("language", "und"),
                "codec": stream.get("codec_name"),
                "title": tags.get("title"),
                "forced": bool(stream.get("disposition", {}).get("forced", False)),
            })

    return {
        "path": str(video_path),
        "duration": duration,
        "container": fmt.get("format_name"),
        "video": video_stream,
        "audio": audio_streams,
        "subtitles": subtitle_streams,
    }


def parse_srt_cues(content: str) -> List[Cue]:
    """Parse SRT content into cues (lenient: index lines optional).

    Args:
        content: SRT file content.

    Returns:
        List of Cue objects (may be empty).
    """
    cues: List[Cue] = []
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    ts_re = re.compile(
        r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*"
        r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
    )

    i = 0
    n = len(lines)
    while i < n:
        m = ts_re.search(lines[i])
        if not m:
            i += 1
            continue

        def to_ms(h, mi, s, ms):
            return ((int(h) * 60 + int(mi)) * 60 + int(s)) * 1000 + int(ms.ljust(3, "0")[:3])

        start_ms = to_ms(m.group(1), m.group(2), m.group(3), m.group(4))
        end_ms = to_ms(m.group(5), m.group(6), m.group(7), m.group(8))

        # Collect text lines until a blank line.
        text_lines = []
        j = i + 1
        while j < n and lines[j].strip() != "":
            text_lines.append(lines[j])
            j += 1
        cues.append(Cue(start_ms=start_ms, end_ms=end_ms, text="\n".join(text_lines)))
        i = j
    return cues


def analyze_srt(content: str) -> Dict:
    """Analyze SRT content for sync-check purposes.

    Args:
        content: SRT file content.

    Returns:
        Dict with: cue_count, first_start (ms), last_end (ms), span (ms),
        texts (normalized cue texts for comparison).
    """
    cues = parse_srt_cues(content)
    if not cues:
        return {"cue_count": 0, "first_start": None, "last_end": None,
                "span": None, "texts": []}
    return {
        "cue_count": len(cues),
        "first_start": cues[0].start_ms,
        "last_end": max(c.end_ms for c in cues),
        "span": max(c.end_ms for c in cues) - cues[0].start_ms,
        "texts": [normalize_text(c.text) for c in cues],
    }


def normalize_text(text: str) -> str:
    """Normalize subtitle text for comparison (lowercase alphanumerics only)."""
    text = re.sub(r"<[^>]+>", " ", text)    # strip HTML tags
    text = re.sub(r"\{[^}]*\}", " ", text)  # strip ASS/SSA override tags
    text = text.lower()
    return re.sub(r"[^a-z0-9\u00c0-\uffff]+", " ", text).strip()


def drift_scenarios(video_fps: Optional[float], top: int = 3) -> List[Dict]:
    """Suggest likely frame-rate drift scenarios for a video fps.

    If subtitles were authored at frame rate `s` but the video plays at
    frame rate `v`, a cue at authored time t should display at video time
    (s/v) * t, i.e. subtitles drift by (s/v - 1) per second of content.

    Args:
        video_fps: The video's frame rate.
        top: Maximum number of scenarios to return.

    Returns:
        List of {subs_fps, scale, drift_per_hour} sorted by |drift| ascending.
        drift_per_hour is in seconds; positive = subtitles get LATER.
    """
    if not video_fps or video_fps <= 0:
        return []
    scenarios = []
    for s in COMMON_SUB_FPS:
        if abs(s - video_fps) < 0.01:
            continue  # same rate, no drift
        scale = s / video_fps
        drift_per_hour = 3600.0 * (scale - 1.0)
        scenarios.append({
            "subs_fps": round(s, 3),
            "scale": round(scale, 6),
            "drift_per_hour": round(drift_per_hour, 2),
        })
    scenarios.sort(key=lambda x: abs(x["drift_per_hour"]))
    return scenarios[:top]


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    mid = len(vals) // 2
    if len(vals) % 2:
        return float(vals[mid])
    return (vals[mid - 1] + vals[mid]) / 2.0


def compare_with_embedded(
    external_cues: List[Cue],
    embedded_cues: List[Cue],
) -> Optional[Dict]:
    """Compare an external SRT against an embedded (in-sync) subtitle track.

    Pairs cues by index, verifies the pairing by text similarity, then fits a
    linear model  delta(t) = offset + rate * t  where delta = external_start -
    embedded_start. The correction to apply to the external SRT is
    corrected(t) = t - delta(t) = (1 - rate) * t - offset.

    Args:
        external_cues: Cues from the downloaded SRT.
        embedded_cues: Cues from the video's embedded subtitle track.

    Returns:
        None if no comparison is possible, otherwise a dict:
          match: bool
          median_similarity: float (0..1)
          n_cues: int (number of pairs used)
          offset_ms: float  (constant part of delta, at t=0)
          rate: float       (ms of drift per ms of time)
          drift_per_hour: float (seconds; positive = external is late and gets later)
          reason: str (only when match is False)
    """
    if not external_cues or not embedded_cues:
        return None

    n_ext, n_emb = len(external_cues), len(embedded_cues)
    if abs(n_ext - n_emb) > max(3, 0.1 * max(n_ext, n_emb)):
        return {
            "match": False,
            "reason": "cue_count",
            "n_external": n_ext,
            "n_embedded": n_emb,
            "median_similarity": None,
            "n_cues": 0,
            "offset_ms": None,
            "rate": None,
            "drift_per_hour": None,
        }

    n = min(n_ext, n_emb)
    pairs = list(zip(external_cues[:n], embedded_cues[:n]))

    # Verify pairing by text similarity.
    similarities = []
    for ext, emb in pairs:
        te, tb = normalize_text(ext.text), normalize_text(emb.text)
        if not te or not tb:
            similarities.append(0.0)
        else:
            similarities.append(difflib.SequenceMatcher(None, te, tb).ratio())
    median_sim = _median(similarities)

    if median_sim < 0.5:
        return {
            "match": False,
            "reason": "text",
            "n_external": n_ext,
            "n_embedded": n_emb,
            "median_similarity": round(median_sim, 3),
            "n_cues": 0,
            "offset_ms": None,
            "rate": None,
            "drift_per_hour": None,
        }

    # Fit delta(t) = offset + rate * t using robust endpoint medians.
    deltas = []
    for ext, emb in pairs:
        deltas.append((emb.start_ms, ext.start_ms - emb.start_ms))
    deltas.sort(key=lambda p: p[0])

    k = max(3, len(deltas) // 10)
    first = [d for _, d in deltas[:k]]
    last = [d for _, d in deltas[-k:]]
    t1, d1 = deltas[0][0], _median(first)
    t2, d2 = deltas[-1][0], _median(last)

    if t2 > t1:
        rate = (d2 - d1) / (t2 - t1)
        offset_ms = d1 - rate * t1
    else:
        rate = 0.0
        offset_ms = _median([d for _, d in deltas])

    drift_per_hour = rate * 3600000.0  # ms/ms * ms/hour = ms/hour -> /1000 below
    drift_per_hour_s = drift_per_hour / 1000.0

    return {
        "match": True,
        "reason": None,
        "n_external": n_ext,
        "n_embedded": n_emb,
        "median_similarity": round(median_sim, 3),
        "n_cues": len(deltas),
        "offset_ms": round(offset_ms, 1),
        "rate": rate,
        "drift_per_hour": round(drift_per_hour_s, 2),
    }


def extract_embedded_cues(video_path: Path, track_index: Optional[int] = None) -> List[Cue]:
    """Extract a subtitle track from the video and parse it into cues.

    Args:
        video_path: Path to the video file.
        track_index: 0-based index among subtitle streams (default: first).

    Returns:
        List of Cue objects (empty on failure).

    Raises:
        RuntimeError: If ffmpeg is missing or extraction fails.
    """
    import tempfile
    from pathlib import Path as _Path

    cmd_base = ["ffmpeg", "-y", "-loglevel", "error"]
    # Determine the subtitle stream selector.
    probe = probe_video(video_path)
    subs = probe.get("subtitles") or []
    if not subs:
        return []
    idx = track_index if track_index is not None else 0
    if idx >= len(subs):
        return []
    sel = subs[idx]

    # ffmpeg -map 0:s:N uses the index among subtitle streams.
    selector = 0
    for s in subs:
        if s["index"] == sel["index"]:
            break
        selector += 1

    with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as f:
        tmp_path = _Path(f.name)
    try:
        cmd = cmd_base + ["-i", str(video_path), "-map", f"0:s:{selector}", "-f", "srt", str(tmp_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed to extract subtitle track: {result.stderr.strip()[:300]}")
        content = tmp_path.read_text(encoding="utf-8", errors="replace")
        return parse_srt_cues(content)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def build_report(
    video_path: Path,
    srt_path: Path,
    video: Dict,
    srt: Dict,
    embedded: Optional[Dict] = None,
) -> Report:
    """Combine probe/analysis results into a Report with flags and a verdict.

    Args:
        video_path: Path to the video (for reporting only).
        srt_path: Path to the SRT (for reporting only).
        video: Result of probe_video().
        srt: Result of analyze_srt().
        embedded: Result of compare_with_embedded() (optional).

    Returns:
        A Report with flags, verdict and (when confident) a suggested fix.
    """
    report = Report(video_path=str(video_path), srt_path=str(srt_path),
                    video=video, srt=srt, embedded=embedded)

    duration = video.get("duration")
    fps = (video.get("video") or {}).get("fps")

    # --- Frame-rate drift scenarios -------------------------------------
    report.scenarios = drift_scenarios(fps)

    # --- Structural flags ------------------------------------------------
    if srt["cue_count"] == 0:
        report.flags.append({"level": "error", "key": "no_cues",
                             "message": "No subtitle cues found in the SRT file."})
    else:
        if duration is not None and srt["last_end"] is not None:
            if srt["last_end"] > duration * 1000 + 5000:
                report.flags.append({
                    "level": "warn", "key": "srt_longer_than_video",
                    "message": (f"SRT ends at {ms_to_ts(srt['last_end'])} but the video is "
                                f"{ms_to_ts(int(duration * 1000))} long. The SRT may be for a "
                                f"different cut or version.")})
            elif srt["last_end"] < duration * 1000 - 120000:
                report.flags.append({
                    "level": "info", "key": "srt_ends_early",
                    "message": (f"SRT ends at {ms_to_ts(srt['last_end'])}, about "
                                f"{int((duration * 1000 - srt['last_end']) / 60000)} minutes before "
                                f"the video ends (credits or a different version?).")})
        if srt["first_start"] is not None and srt["first_start"] > 30000:
            report.flags.append({
                "level": "info", "key": "first_cue_late",
                "message": (f"First cue starts at {ms_to_ts(srt['first_start'])}. If the video "
                            f"starts with dialogue, the SRT may need a negative offset.")})

    # --- Embedded comparison ---------------------------------------------
    if embedded:
        if embedded.get("match"):
            # Suggested fix: corrected(t) = (1-rate)*t - offset
            rate = embedded["rate"] or 0.0
            offset_ms = embedded["offset_ms"] or 0.0
            t2_ms = min(srt["last_end"] or 0, int(duration * 1000)) if duration else (srt["last_end"] or 0)
            if t2_ms <= 0:
                t2_ms = 3600000
            o1_s = -offset_ms / 1000.0
            o2_s = -offset_ms / 1000.0 - rate * (t2_ms / 1000.0)
            report.suggested_fix = {
                "t1": 0.0,
                "o1": round(o1_s, 3),
                "t2": round(t2_ms / 1000.0, 3),
                "o2": round(o2_s, 3),
            }
            report.flags.append({
                "level": "fix", "key": "embedded_match",
                "message": (f"Downloaded SRT matches the embedded subtitle track "
                            f"({embedded['n_cues']} cues, similarity "
                            f"{embedded['median_similarity']:.0%}). Measured offset: "
                            f"{offset_ms / 1000.0:+.2f}s, drift: "
                            f"{embedded['drift_per_hour'] / 60.0:+.2f} min/hour.")})
            # 2 s/hour is just under the classic 23.976<->24 fps drift
            # (3.6 s/hour): anything above that is worth fixing.
            if abs(embedded["drift_per_hour"]) > 2 or abs(offset_ms) > 500:
                report.verdict = "fix_available"
            else:
                report.verdict = "ok"
        elif embedded.get("reason") == "cue_count":
            report.flags.append({
                "level": "warn", "key": "embedded_cue_count",
                "message": (f"Embedded track has {embedded['n_embedded']} cues but the "
                            f"downloaded SRT has {embedded['n_external']} — likely a "
                            f"different version or language.")})
            report.verdict = "likely_different_version"
        else:
            report.flags.append({
                "level": "info", "key": "embedded_text_mismatch",
                "message": (f"Downloaded SRT does not match the embedded track text "
                            f"(similarity {embedded['median_similarity']:.0%}) — possibly a "
                            f"different language or version.")})

    # --- Verdict fallbacks -------------------------------------------------
    # Default: we cannot confirm sync without visual verification.
    if report.verdict == "ok" and embedded is None:
        report.verdict = "possible_misalignment"
    if any(f["key"] == "srt_longer_than_video" for f in report.flags):
        report.verdict = "likely_different_version"

    if not report.flags:
        report.flags.append({"level": "info", "key": "no_issues",
                             "message": "No obvious problems detected. If subtitles are still "
                                        "out of sync, verify visually with Sync Preview."})

    return report


def ms_to_ts(ms: int) -> str:
    """Format milliseconds as HH:MM:SS."""
    ms = int(ms)
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s = rem // 1000
    return f"{h:02d}:{m:02d}:{s:02d}"


def point_time(seconds: float) -> str:
    """Format seconds as a time usable in an autosync --points argument.

    Whole seconds use HH:MM:SS; fractional seconds use HH:MM:SS.mmm so no
    precision is lost (autosync's parse_time accepts both).
    """
    seconds = float(seconds)
    if seconds == int(seconds):
        return ms_to_ts(int(seconds * 1000))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def format_report(report: Report) -> str:
    """Format a Report as human-readable text (for CLI output)."""
    lines = []
    v = report.video
    s = report.srt

    lines.append(f"Video: {report.video_path}")
    if v.get("duration"):
        lines.append(f"  duration: {ms_to_ts(int(v['duration'] * 1000))} ({v['duration']:.1f}s)")
    video = v.get("video") or {}
    if video.get("fps"):
        lines.append(f"  video: {video.get('codec')} {video.get('width')}x{video.get('height')} @ {video['fps']} fps")
    subs = v.get("subtitles") or []
    if subs:
        lines.append(f"  embedded subtitle tracks: {len(subs)}")
        for t in subs:
            label = f"track {t['index']}: {t['language']}"
            if t.get("title"):
                label += f" ({t['title']})"
            if t.get("forced"):
                label += " [forced]"
            lines.append(f"    {label}")
    else:
        lines.append("  embedded subtitle tracks: none")

    lines.append(f"SRT:   {report.srt_path}")
    if s["cue_count"]:
        lines.append(f"  cues: {s['cue_count']}, first at {ms_to_ts(s['first_start'])}, "
                     f"last ends at {ms_to_ts(s['last_end'])} "
                     f"(span {ms_to_ts(s['span'])})")
    else:
        lines.append("  cues: 0 (no cues found!)")

    if report.scenarios:
        lines.append("Possible frame-rate drift (if subtitles were authored at a different fps):")
        for sc in report.scenarios:
            direction = "later" if sc["drift_per_hour"] > 0 else "earlier"
            lines.append(f"  - subs at {sc['subs_fps']} fps: subtitles would drift "
                         f"{abs(sc['drift_per_hour']):.1f}s {direction} per hour")

    if report.flags:
        lines.append("Findings:")
        for f in report.flags:
            icon = {"error": "✗", "warn": "!", "fix": "✓", "info": "·"}[f["level"]]
            lines.append(f"  [{icon}] {f['message']}")

    if report.suggested_fix:
        fx = report.suggested_fix
        lines.append("Suggested fix (correction to add to the SRT timestamps):")
        lines.append(f"  {fx['o1']:+.2f}s at {ms_to_ts(int(fx['t1'] * 1000))}, "
                     f"{fx['o2']:+.2f}s at {ms_to_ts(int(fx['t2'] * 1000))}")
        lines.append("  Verify visually first:  subtitle-tk preview VIDEO SRT")
        p1 = point_time(fx["t1"])
        p2 = point_time(fx["t2"])
        lines.append(
            f"  Apply: subtitle-tk autosync --points {p1}:{fx['o1']:.2f} {p2}:{fx['o2']:.2f}"
            f" < {report.srt_path} > fixed.srt"
        )

    verdict_text = {
        "ok": "Verdict: looks fine.",
        "fix_available": "Verdict: a fix is available — apply the suggested fix or verify in preview.",
        "possible_misalignment": "Verdict: possible offset/drift — verify visually with preview.",
        "likely_different_version": "Verdict: this SRT may be for a different version of the video.",
    }
    lines.append(verdict_text.get(report.verdict, f"Verdict: {report.verdict}."))
    return "\n".join(lines)


def run_check(video_path: Path, srt_path: Path, use_embedded: bool = True) -> Report:
    """Run a full sync check for one video + one SRT.

    Args:
        video_path: Path to the video file.
        srt_path: Path to the SRT file.
        use_embedded: If True and the video has an embedded subtitle track,
            compare against it.

    Returns:
        A Report.
    """
    video = probe_video(video_path)
    srt_content = srt_path.read_text(encoding="utf-8", errors="replace")
    srt = analyze_srt(srt_content)

    embedded = None
    if use_embedded and video.get("subtitles") and srt["cue_count"]:
        try:
            embedded_cues = extract_embedded_cues(video_path)
            if embedded_cues:
                embedded = compare_with_embedded(parse_srt_cues(srt_content), embedded_cues)
        except RuntimeError:
            embedded = None  # extraction failed; skip comparison

    return build_report(video_path, srt_path, video, srt, embedded)


def main() -> None:
    """Command-line entry point for the sync check."""
    parser = argparse.ArgumentParser(
        description="Check whether a subtitle file is in sync with a video "
                    "(offset, drift, wrong version).",
        epilog="Example: subtitle-tk check movie.mkv movie.en.srt",
    )
    parser.add_argument("video", type=Path, help="Video file")
    parser.add_argument("srt", type=Path, nargs="+", help="One or more SRT files to check")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    parser.add_argument("--no-embedded", action="store_true",
                        help="Skip comparison against embedded subtitle tracks")
    args = parser.parse_args()

    reports = []
    for srt_path in args.srt:
        try:
            reports.append(run_check(args.video, srt_path, use_embedded=not args.no_embedded))
        except (FileNotFoundError, RuntimeError) as e:
            print(f"Error checking {srt_path}: {e}", file=sys.stderr)
            sys.exit(1)

    if args.json:
        print(json.dumps([r.to_dict() for r in reports], indent=2, ensure_ascii=False))
    else:
        for i, r in enumerate(reports):
            if i > 0:
                print()
            print(format_report(r))


if __name__ == "__main__":
    main()
