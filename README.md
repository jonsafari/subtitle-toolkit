# Subtitle Toolkit  🍿

> Swiss Army knife for everything subtitle-related.

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)

Subtitle Toolkit is a collection of tools for working with subtitle files. Whether you're a translator, video editor, accessibility advocate, or just someone who needs to fix out-of-sync subtitles, this toolkit has you covered.

## What Can It Do?

- **Translate** subtitles using AI (supports any LLM via LiteLLM)
- **Diagnose** out-of-sync subtitles (Sync Check): detects constant offset, frame-rate drift, or the wrong subtitle version — including comparison against embedded subtitle tracks
- **Preview & fix** sync live (Sync Preview): watch the video with your subtitles overlaid, nudge offset/drift instantly, and export a corrected `.srt`
- **Fix timing** with uniform shifts or drift correction for frame-rate issues
- **Convert** between formats: SRT, VTT, ASS, TTML, and many more
- **Extract** subtitle tracks from MKV/MP4 video files
- **Merge** multiple subtitle tracks into one

## Installation

**For end users**:
```bash
pip install subtitle-toolkit
```

**For the web interface**:
```bash
pip install subtitle-toolkit[web]
```

**For developers** (all dependencies including testing tools):
```bash
pip install subtitle-toolkit[all]
```

Or install in editable mode for development:
```bash
pip install -e subtitle-toolkit[all]
```

## Quick Start

**Web interface** (recommended for most users):
```bash
subtitle-tk web
# Then open http://localhost:8000 in your browser
```

**Command line**:
```bash
# Shift every timestamp 2.5 seconds later (positive = later)
subtitle-tk timeshift --shift-seconds 2.5 < input.srt > output.srt
```

---

## Web Interface

The web interface is the easiest way to use Subtitle Toolkit. No command line needed—just upload your file, adjust settings, and download the result.

### Getting Started

1. Start the server:
   ```bash
   subtitle-tk web
   ```

2. Open your browser to `http://localhost:8000`

3. Choose a tool from the menu and follow the on-screen instructions

### Available Tools

| Tool | What It Does |
|------|--------------|
| **Sync Check** | Fast pre-flight diagnosis: reports video/SRT details, compares against embedded subtitle tracks, and tells you whether the problem is a constant offset, frame-rate drift, or the wrong subtitle version — with a suggested fix you can apply in one click. |
| **Sync Preview** | Watch the video with your subtitles overlaid. Adjust "at time T, subtitles are X seconds off" at two points, see the result instantly, and export the corrected `.srt`. |
| **Translate** | Translate subtitles using AI. Supports any LLM provider (OpenAI, Anthropic, local models, etc.). |
| **Timeshift** | Shift all timestamps by a fixed amount (e.g., "subtitles are 2 seconds late"). |
| **Autosync** | Fix drift issues where subtitles slowly get more out of sync over time (common with frame-rate conversion). |
| **Subtitle Tracks** | List, extract, or merge subtitle tracks from video files. |
| **Convert** | Convert between subtitle formats (SRT, VTT, ASS, TTML, and more). |

### Fixing Out-of-Sync Subtitles (Recommended Workflow)

If your downloaded subtitles don't line up with the video:

1. **Sync Check** — upload the video and the `.srt`. The tool probes the video, analyzes the subtitles, and (if the video has an embedded subtitle track) compares the two to measure the exact offset and drift. It tells you the likely cause and offers a one-click suggested fix.
2. **Sync Preview** — watch the video with your subtitles overlaid. Fine-tune two sync points (e.g. "at 00:00:00 subtitles are 2 s late" and "at 01:00:00 subtitles are 5 s late") and see the change instantly — even while paused. Drift presets fill in the second point for common frame-rate mismatches. Hotkeys: `,` / `.` = one frame earlier/later, `<` / `>` = one second, `[` / `]` = ten seconds.
3. **Export** — the corrected `.srt` is generated with exactly the same math as the preview, so what you saw is what you get. The video file is never modified.

### Multi-Language Support

The web interface is available in 17 languages: English, Arabic, German, Spanish, Persian, French, Indonesian, Italian, Japanese, Korean, Dutch, Polish, Portuguese, Turkish, Ukrainian, Vietnamese, and Chinese.

---

## Command-Line Interface

For scripting, automation, or if you prefer the terminal, the CLI provides the same functionality.

### Commands

| Command | Description |
|---------|-------------|
| `translate` | Translate subtitles using AI |
| `timeshift` | Uniform timestamp adjustment |
| `autosync` | Drift correction (time-varying offset) |
| `check` | Diagnose out-of-sync subtitles (offset, drift, wrong version) |
| `preview` | Open the live Sync Preview web UI with files pre-loaded |
| `subtitle-tracks` | List, extract, merge subtitle tracks |
| `convert` | Convert between subtitle formats |
| `web` | Start the web interface |

### Examples

**Translate subtitles** (requires API key or local LLM):
```bash
subtitle-tk translate input.srt --instructions "Translate to Spanish"
```

**Shift timestamps** (move subtitles to 3 seconds later):
```bash
subtitle-tk timeshift --shift-seconds 3 < input.srt > output.srt
```

**Fix drift** (at 10:00, subtitles are 5 seconds late):
```bash
subtitle-tk autosync --correct-at 00:00:00 --offset-at 00:10:00 --offset 5 < input.srt > output.srt
```

**Diagnose out-of-sync subtitles** (offset, drift, or wrong version):
```bash
subtitle-tk check movie.mkv subtitles.srt
# machine-readable output:
subtitle-tk check movie.mkv subtitles.srt --json
```

**Live sync preview** (opens the web UI with your files pre-loaded):
```bash
subtitle-tk preview movie.mkv subtitles.srt
```

**Or specify multiple sync points**:
```bash
subtitle-tk autosync --point 00:00:00:0 00:05:00:2.5 00:10:00:5 < input.srt > output.srt
```

**List subtitle tracks in a video**:
```bash
subtitle-tk subtitle-tracks list video.mkv
```

**Extract all subtitle tracks as a zip file**:
```bash
subtitle-tk subtitle-tracks extract video.mkv --all --as-zip
```

**Convert to VTT format**:
```bash
subtitle-tk convert input.srt --output-format vtt -o output.vtt
```

**Get help for any command**:
```bash
subtitle-tk <command> --help
```

---

## Common Use Cases

### "My subtitles are out of sync but I don't know why"
Use **Sync Check** (`subtitle-tk check` or the web UI). It measures the offset and drift — using the video's embedded subtitle track as a reference when available — and tells you whether it's a constant offset, frame-rate drift, or the wrong subtitle version.

### "I want to see the fix before I commit to it"
Use **Sync Preview** (`subtitle-tk preview` or the web UI). Watch the video with your subtitles overlaid, adjust two sync points live, and export the corrected `.srt` when it looks right.

### "My subtitles are 2 seconds late"
Use **Timeshift** with a positive shift value.

### "My subtitles start fine but drift out of sync over time"
Use **Autosync** with one or more sync points.

### "I need subtitles in another language"
Use **Translate** with your preferred AI provider.

### "I have a video file and need the subtitle tracks"
Use **Subtitle Tracks** to extract them.

### "My video editor needs a different subtitle format"
Use **Convert** to change the format.

---

## Docker (Optional)

Skip this section if Docker isn't your thing. The pip installation works great for most users.

```bash
docker build -t subtitle-toolkit .
docker run -p 8000:8000 subtitle-toolkit
```

---

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests. The codebase is Python 3.8+ and uses FastAPI for the web interface.

---

## License

GPL-3.0 — See [LICENSE](LICENSE) for details.

---

Happy subtitling! 🎬
