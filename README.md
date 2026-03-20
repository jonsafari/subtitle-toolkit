# Subtitle Toolkit  🍿

A small collection of utilities for **fixing** (time-shifting, drift correction) and **translating** SRT subtitle files. There's command-line tools as well as a web interface.
The tools are deliberately lightweight, command-line-first, and work with any LLM provider via litellm (OpenAI, Anthropic, Gemini, Databricks, and local models).

| Script | What it does | Typical use-case |
|--------|--------------|------------------|
| `subtitle-tk timeshift` | Shifts every timestamp in an SRT stream by a fixed amount **or** aligns the first subtitle to a user-provided start time. | Fix subtitles that are uniformly out of sync with the video. |
| `subtitle-tk autosync` | Applies **drift correction** to SRT files using two-point, multi-point, or known drift rate methods. | Fix subtitles that gradually drift out of sync (e.g., due to frame rate differences like 23.976fps vs 24fps). |
| `subtitle_timeshift_gui.sh` | Small Zenity-based GUI wrapper around `subtitle-tk timeshift`. | Users who prefer a point-and-click workflow on Linux. |
| `subtitle-tk subtitle-tracks list` | Lists all subtitle tracks in a video file (MKV, MP4, AVI, MOV, WEBM, etc.). | Discover what subtitle tracks are available in your video files. |
| `subtitle-tk subtitle-tracks extract` | Extracts specific subtitle tracks by index, language, or filter (forced, hearing impaired). | Extract the subtitle track you want to use from a multi-track video. |
| `subtitle-tk subtitle-tracks merge` | Merges multiple subtitle files with configurable priority handling. | Combine regular subtitles with hearing-impaired tracks or merge translations. |
| `subtitle-tk mkv2srt` | **(DEPRECATED)** Extracts subtitles from MKV files. Use `subtitle-tracks` instead. | Legacy support only - use `subtitle-tk subtitle-tracks` for enhanced functionality. |
| `subtitle-tk translate` | Translates a subtitle (SRT/SubRip) file, using a *translation‑instruction* file and an LLM endpoint via litellm. | Translate subtitles (e.g. English → Spanish) while keeping the original formatting. |
| `subtitle-tk convert` | Converts subtitle files between different formats (SRT, VTT, ASS, TTML, etc.). | Convert subtitles to a format compatible with your video player or editing software. |
| translation_instruction_prompts/`subtitle_translate_*.txt` | Example instruction files that tell the LLM how to translate (show/movie context, keep formatting, don't add extra text, etc.). | Supply to `subtitle-tk translate` via `--instructions`. |

---


<a name="installation"></a>
## Installation

```bash
pip install subtitle-toolkit
```

---

<a name="system_deps"></a>
### System Dependencies

```bash
# Optional install of ffmpeg if you want subtitle extraction
brew install ffmpeg   # macOS
# sudo apt install ffmpeg  # Ubuntu/Debian/Mint

# Optional install of Zenity for the GUI script
brew install zenity   # macOS
# sudo apt install zenity  # Ubuntu/Debian/Mint
```

<a name="from_source"></a>
### From Source

```bash
# Clone the repository
git clone https://github.com/jonsafari/subtitle-toolkit.git
cd subtitle-toolkit

# Create a virtual environment (optional)
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Local Pip install
pip install -e .
```

---

### <a name="web-interface"></a>Web interface

```bash
subtitle-tk web
```

Open http://localhost:8000 in a browser.

---

<a name="quick-start"></a>
## Command-line Intro

### <a name="time-shifting-a-subtitle-file"></a>Time-shifting a subtitle file

```bash
# Shift every timestamp 2.5 seconds later (positive = later)
cat original.srt | subtitle-tk timeshift --shift-seconds 2.5 > shifted.srt

# Or align the first subtitle to a concrete start time
cat original.srt | subtitle-tk timeshift --first-entry-starts-at 00:01:32,945 > aligned.srt
```

### <a name="using-the-gui-wrapper"></a>Using the GUI wrapper

```bash
./subtitle_timeshift_gui.sh
```

For an all-GUI experience, you can edit the file `Subtitle_Timeshift.desktop` to ensure your correct local path in the `Exec` line, and then copy it to `~/Desktop`.
Afterwards you should see an icon on your desktop, which will launch the script above.

```bash
sensible-editor Subtitle_Timeshift.desktop
cp Subtitle_Timeshift.desktop ~/Desktop/
```

The GUI dialogue will:

1. Prompt you to pick a video (optional - just opens it with the default player).
2. Ask for the desired start time of the first subtitle (`HH:MM:SS,mmm`).
3. Let you select the input SRT file and the output filename.
4. Run `subtitle-tk timeshift` behind the scenes and write the corrected file.

> **Note:** The GUI only works on systems with `zenity` and a graphical environment.

### <a name="translating-a-subtitle-file"></a>Translating a subtitle file

```bash
# Basic call - uses the default instruction file `translation_instruction_prompts/subtitle_translate_-_en-es_-_default.txt`
subtitle-tk translate path/to/english.srt

# Custom instruction file, chunk size, output SRT file and API endpoint
subtitle-tk translatey path/to/english.srt \
    --instructions translation_instruction_prompts/subtitle_translate_-_en-es_-_Gavin_and_Stacey.txt \
    --output path/to/spanish.srt \
    --api-base http://localhost:8080/v1 \
    --model-id llama3:8b \
    --api-key dummy-key

# Using Anthropic Claude
subtitle-tk translate path/to/english.srt \
    --model-id anthropic/claude-4-6-sonnet \
    --api-key $ANTHROPIC_API_KEY

# Using Google Gemini
subtitle-tk translate path/to/english.srt \
    --model-id gemini/gemini-3-flash \
    --api-key $GEMINI_API_KEY
```

---

<a name="detailed-usage"></a>
## Detailed Usage

### <a name="subtitle_timeshiftpy"></a>`subtitle-tk timeshift`

| Option | Description |
|--------|-------------|
| `-s`, `--shift-seconds <float>` | Shift every timestamp by the given number of seconds. Positive values move subtitles **later** (i.e. they appear later). |
| `-f`, `--first-entry-starts-at <HH:MM:SS[,.mmm]>` | Compute the required shift so that the **first** subtitle starts at the supplied time (sub-seconds optional). The script reads the first timestamp it encounters, calculates the difference, and then applies that shift to the whole file. |
| *Input* | The script reads **STDIN**. Pipe a file (`cat file.srt \| ...`) or redirect (`subtitle-tk timeshift -s 1.2 < file.srt`). |
| *Output* | Printed to **STDOUT** - redirect to a new file. |

**Behaviour notes**

* The script tolerates malformed timestamp lines - they are passed through unchanged.
* If a shift would produce a negative time, the timestamp is clamped to `00:00:00,000`.
* The script keeps the original line endings (`\n` or `\r\n`).

---

### <a name="subtitle_autosyncpy"></a>`subtitle-tk autosync`

#### Purpose

Applies **drift correction** to SRT subtitle files. Unlike `timeshift` which applies a uniform shift to all timestamps, `autosync` applies a **time-varying offset** that increases or decreases across the video duration. This is essential for fixing subtitles that gradually drift out of sync due to frame rate differences (e.g., 23.976fps video with 24fps subtitles).

#### When to Use Autosync vs Timeshift

| Scenario | Tool |
|----------|------|
| Subtitles are uniformly off by X seconds | `timeshift` |
| Subtitles start correct but drift over time | `autosync` |
| Video has wrong frame rate (23.976 vs 24 fps) | `autosync` |

#### Command-line options

| Option | Description |
|--------|-------------|
| `--correct-at`, `-c <time>` | Time where subtitles are correct (offset = 0). Format: `HH:MM:SS[,.mmm]` |
| `--offset-at`, `-o <time>` | Time where you know the offset value |
| `--offset <seconds>` | Offset in seconds at `--offset-at` time (positive = subtitles are late) |
| `--points`, `-p <time:offset>...` | Multiple sync points for complex drift (e.g., `00:00:30:0 00:10:00:5`) |
| `--drift-rate`, `-d <rate>` | Apply known drift rate: `23.976_to_24`, `24_to_23.976`, `29.97_to_30`, etc. |
| `--reference`, `-r <time>` | Reference time for drift rate mode (default: `00:00:00`) |
| `--output`, `-O <file>` | Output file (default: stdout) |
| `--no-clamp` | Don't clamp negative timestamps to zero |
| `--verbose`, `-v` | Print verbose information about the correction |

#### Examples

**Two-point correction (most common):**
```bash
# Subtitles correct at 0:30, 5 seconds late at 10:00
cat input.srt | subtitle-tk autosync --correct-at 00:00:30 --offset-at 00:10:00 --offset 5.0 > output.srt
```

**Multi-point correction (for complex drift):**
```bash
# Multiple sync points: 0:30 correct, 5:00 is 2.5s late, 10:00 is 5s late
cat input.srt | subtitle-tk autosync --points 00:00:30:0 00:05:00:2.5 00:10:00:5.0 > output.srt
```

**Known drift rate (frame rate conversion):**
```bash
# Video was 23.976fps but subtitles are for 24fps
cat input.srt | subtitle-tk autosync --drift-rate 23.976_to_24 > output.srt

# Common drift rates:
# - 23.976_to_24: 23.976fps → 24fps (+0.1%, ~4.5 sec/hour)
# - 29.97_to_30: 29.97fps → 30fps (+0.1%, ~6 sec/hour)
# - 25_to_23.976: 25fps → 23.976fps (-4.2%, ~2.5 min/hour)
```

**With verbose output:**
```bash
cat input.srt | subtitle-tk autosync --correct-at 00:00:30 --offset-at 00:10:00 --offset 5.0 --verbose
```

#### How It Works

The autosync tool calculates a **drift rate** based on your sync points:

```
drift_rate = offset_at_offset_time / (offset_time - reference_time)
```

For any subtitle at time `t`:
```
offset = drift_rate × (t - reference_time)
new_time = t + offset
```

This creates a linear correction that gradually increases (or decreases) across the video.

#### Tips

1. **Watch your video** and note timestamps where subtitles are correct vs. wrong
2. **Positive offset** means subtitles appear LATE (after the audio)
3. **Negative offset** means subtitles appear EARLY (before the audio)
4. **Two-point mode** works for most cases - just find where subs are correct and where they're wrong
5. **Multi-point mode** is for complex drift patterns (rare)

---

### <a name="subtitle_timeshift_guish"></a>`subtitle_timeshift_gui.sh`

A thin wrapper that:

1. Uses `zenity` dialogs to collect:
   * (optional) a video file - opened with the system's default player (`open` on macOS, `xdg-open` on Linux).
   * Desired start time (`HH:MM:SS,mmm`).
   * Input SRT file.
   * Output filename.
2. Calls `subtitle-tk timeshift` with `--first-entry-starts-at`.
3. Writes the result to the chosen output path.

**Dependencies**

* `zenity` - graphical dialog utility.
* `open` (macOS) **or** `xdg-open` (Linux) - used to launch the video file.

If you do not need the GUI, just use `subtitle-tk timeshift` directly.

---

### <a name="subtitle_mkv2srt"></a>`subtitle-tk mkv2srt` **(DEPRECATED)**

> **⚠️ DEPRECATED:** This tool is deprecated and will be removed in a future version. Please use [`subtitle-tk subtitle-tracks`](#subtitle_tracks) instead, which provides enhanced functionality including:
> - Support for all video formats (not just MKV)
> - Track listing with metadata
> - Forced and hearing impaired subtitle filtering
> - Subtitle merging capabilities
> - ZIP download for multiple tracks

#### Purpose

Extracts subtitles from MKV files and converts them to SRT (SubRip) format. This tool is maintained for backward compatibility only.

#### Command-line options

| Option | Default | Description |
|--------|---------|-------------|
| `--input` or `-i` | - | Path to the input MKV file (required). |
| `--output` or `-o` | - | Output SRT file path (optional). If not specified, extracts all subtitles to individual files. |
| `--language` or `-l` | - | Language code to filter subtitles (e.g., "en", "es"). |

#### Examples

```bash
# Extract all subtitles from an MKV file (deprecated - use subtitle-tracks instead)
subtitle-tk mkv2srt --input video.mkv

# Recommended alternative:
subtitle-tk subtitle-tracks extract video.mkv --all
```

#### Important notes

* The script requires `ffmpeg` to be installed and available in `$PATH`.
* ASS/SSA formatting tags like {\an7} are automatically removed to ensure compatibility with video players.
* If no subtitles are found in the MKV file, the script will report this and exit.
* **This tool is deprecated.** Please migrate to `subtitle-tk subtitle-tracks` for new projects.

---

### <a name="subtitle_tracks"></a>`subtitle-tk subtitle-tracks`

#### Purpose

A comprehensive tool for managing subtitle tracks in video files. It can:
- **List** all subtitle tracks in a video file (MKV, MP4, AVI, MOV, WEBM, etc.)
- **Extract** specific tracks by index, language, or filter (forced, hearing impaired)
- **Merge** multiple subtitle files with configurable priority handling

**This is the recommended tool for extracting subtitles from video files.** It replaces the older `mkv2srt` command with enhanced functionality including support for all video formats, track metadata, and subtitle merging.

#### Subcommands

##### `list` - List subtitle tracks

Lists all subtitle tracks in a video file with their metadata.

```bash
# List all subtitle tracks
subtitle-tk subtitle-tracks list video.mkv

# Output as JSON
subtitle-tk subtitle-tracks list video.mkv --format json
```

**Example output:**
```
Found 5 subtitle track(s) in movie.mkv:
  Track 3: ENG - dvd_subtitle
  Track 4: SPA - dvd_subtitle
  Track 5: POR - dvd_subtitle
  Track 6: HIN - dvd_subtitle
  Track 7: ENG - ass [Hearing Impaired]
```

##### `extract` - Extract subtitle tracks

Extract one or all subtitle tracks from a video file.

| Option | Default | Description |
|--------|---------|-------------|
| `--track` or `-t` | - | Track index to extract (0-based). |
| `--language` or `-l` | - | Language code to filter by (e.g., "eng", "spa"). |
| `--all` or `-a` | - | Extract all subtitle tracks. |
| `--output` or `-o` | - | Output file path or directory. |
| `--as-zip` | - | Package all extracted files into a ZIP archive. |
| `--forced-only` | - | Only extract forced subtitle tracks (foreign dialogue). |
| `--no-forced` | - | Exclude forced subtitle tracks. |

**Examples:**

```bash
# Extract English subtitles
subtitle-tk subtitle-tracks extract movie.mkv --language eng

# Extract a specific track by index
subtitle-tk subtitle-tracks extract movie.mkv --track 0

# Extract all tracks to individual files
subtitle-tk subtitle-tracks extract movie.mkv --all

# Extract all tracks as a ZIP archive
subtitle-tk subtitle-tracks extract movie.mkv --all --as-zip

# Extract only forced subtitles (foreign dialogue)
subtitle-tk subtitle-tracks extract movie.mkv --forced-only

# Exclude forced subtitles
subtitle-tk subtitle-tracks extract movie.mkv --no-forced
```

##### `merge` - Merge subtitle files

Merges multiple subtitle files into one, with configurable handling of overlapping timestamps.

| Option | Default | Description |
|--------|---------|-------------|
| `--output` or `-o` | - | Output file path (required). |
| `--priority` or `-p` | `first` | How to handle overlapping timestamps: `first`, `second`, or `combine`. |

**Priority modes:**
- **`first`**: When timestamps overlap, keep the subtitle from the first file.
- **`second`**: When timestamps overlap, keep the subtitle from the last file.
- **`combine`**: When timestamps overlap, stack both subtitles with a line break between them.

**Examples:**

```bash
# Merge two subtitle files (first file takes priority on overlaps)
subtitle-tk subtitle-tracks merge regular.srt hearing-impaired.srt -o combined.srt

# Merge with combine priority (stack overlapping subtitles)
subtitle-tk subtitle-tracks merge subs1.srt subs2.srt -o merged.srt --priority combine

# Merge multiple files
subtitle-tk subtitle-tracks merge en.srt es.srt fr.srt -o all_languages.srt --priority first
```

#### Important notes

* The tool requires `ffmpeg` and `ffprobe` to be installed and available in `$PATH`.
* Supports all video formats that ffmpeg can handle (MKV, MP4, AVI, MOV, WEBM, FLV, etc.).
* ASS/SSA formatting tags are automatically removed during extraction.
* When extracting all tracks, filenames are auto-generated based on language and track properties.
* For merging, the order of input files matters when using `first` or `second` priority modes.

---

### <a name="subtitle_translatepy"></a>`subtitle-tk translate`

#### Purpose

Large subtitle files (e.g. full-season SRTs) often exceed the token limits of LLM APIs. This script:

1. **Splits** the file into *units* (the classic SRT block: index, timestamps, text, blank line).
2. **Chunks** a configurable number of units together (default 30).
3. **Prepends** a user-provided instruction file (e.g. "You are an expert translator ...").
4. Sends each chunk to an LLM endpoint via litellm.
5. Writes the translated output to a new `.srt` file.

#### Command-line options

| Option | Default | Description |
|--------|---------|-------------|
| `input_file` | - | Path to the source `.srt`. |
| `--instructions` | `translation_instruction_prompts/subtitle_translate_-_en-es_-_default.txt` | Path to the instruction file that tells the model how to translate. |
| `--chunk-size` | `30` | Number of subtitle units per API request. |
| `--output` | `<input>_translated.srt` | Output translated SRT file name. |
| `--api-base` | `http://localhost:8080` | Base URL of the LLM server (for self-hosted endpoints). |
| `--model-id` | `local-model` | Model identifier (e.g., `llama3:8b`, `anthropic/claude-4-6-sonnet`, `gemini/gemini-3-flash`). |
| `--api-key` | `dummy-key` | API key (some servers require a non-empty value). |

#### Example workflow

```bash
# Self-hosted OpenAI-compatible endpoint
subtitle-tk translate season01.srt \
    --instructions translation_instruction_prompts/subtitle_translate_-_en-es_-_Schitts_Creek.txt \
    --output path/to/spanish.srt \
    --api-base http://localhost:8080/v1 \
    --model-id llama3:8b \
    --api-key dummy-key

# Anthropic Claude
subtitle-tk translate season01.srt \
    --model-id anthropic/claude-4-6-sonnet \
    --api-key $ANTHROPIC_API_KEY

# Google Gemini
subtitle-tk translate season01.srt \
    --model-id gemini/gemini-3-flash \
    --api-key $GEMINI_API_KEY
```

#### Important notes

* **Instruction file** - This file is important and provides useful context about the show/movie that you're translating. I recommend copying the Synopsis section of the Wikipedia article for the show/movie that you're translating.  The file must be plain text.
* **API limits** - Adjust `--chunk-size` if you hit token-limit errors. Smaller chunks = more requests, larger chunks = fewer requests but higher token usage.
* **Model behaviour** - The provided instruction files explicitly ask the model **not** to add extra text, to keep the original formatting, and to translate only the dialogue. If you notice stray commentary, tweak the instruction file accordingly.

### <a name="subtitle_convertpy"></a>`subtitle-tk convert`

Convert subtitle files between different formats (SRT, VTT, ASS, TTML, etc.). Powered by [lattifai-captions](https://github.com/lattifai/captions).

```bash
# Convert SRT to VTT
subtitle-tk convert input.srt --output-format vtt -o output.vtt

# Convert ASS to SRT
subtitle-tk convert input.ass --output-format srt -o output.srt

# Read from stdin, write to stdout
cat input.srt | subtitle-tk convert --input-format srt --output-format vtt

# Normalize text (remove HTML tags, collapse whitespace)
subtitle-tk convert input.srt --output-format sbv -o output.sbv --normalize-text
```

| Option | Default | Description |
|--------|---------|-------------|
| `--input-format` | `auto` | Input format (srt, vtt, ass, etc.) |
| `--output-format` | *(required)* | Output format (srt, vtt, ass, ttml, etc.) |
| `-o, --output` | *(stdout)* | Output file path |
| `--preserve-formatting` | *(default)* | Keep original text formatting |
| `--normalize-text` | | Normalize text (remove HTML tags, collapse whitespace) |

---

<a name="configuration"></a>
## Configuration & Environment Variables

| Variable | Effect | Example |
|----------|--------|---------|
| `LLM_API_KEY` | API key for the LLM provider. | `export LLM_API_KEY=sk-xxxx` |
| `ANTHROPIC_API_KEY` | API key for Anthropic models. | `export ANTHROPIC_API_KEY=sk-ant-xxxx` |
| `GEMINI_API_KEY` | API key for Google Gemini models. | `export GEMINI_API_KEY=AIzaSyxxxx` |
| `PYTHONIOENCODING` | Forces UTF-8 for stdin/stdout (useful on Windows). | `export PYTHONIOENCODING=utf-8` |

The command-line arguments always take precedence over environment variables.

---

<a name="troubleshooting"></a>
## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `ValueError: time data ... does not match format` from `subtitle-tk timeshift` | Wrong timestamp format in the SRT (e.g., missing commas). | Verify the source file follows the `HH:MM:SS,mmm` pattern. The script will leave un-parseable lines untouched. |
| No output file created, script exits with "Input file does not exist" | Wrong path or missing file permissions. | Use an absolute path or `ls` to confirm the file exists. |
| `ImportError: No module named litellm` | `litellm` Python package not installed. | `pip install -r requirements.txt` (or `pip install litellm`). |
| API returns 429 / "rate limit exceeded" | Chunk size too large or server limits. | Reduce `--chunk-size` or add a short `sleep` between requests (modify script). |
| GUI script crashes with "zenity: command not found" | `zenity` not installed. | Install via package manager (`sudo apt install zenity` on Debian/Ubuntu, `brew install zenity` on macOS via Homebrew). |
| Translated subtitles lose numbering or timestamps | The instruction file asked the model to "maintain format" but the model ignored it. | Tighten the instruction (e.g., add "**Do not modify the index numbers or timestamps**"). |
| Output file contains Windows line endings on Linux (or vice-versa) | Mixed line endings in the source file. | The script preserves the original style; if you need a specific style, run `dos2unix` or `unix2dos` after translation. |
| `Error: ffmpeg is required but not found` | FFmpeg not installed. | Install FFmpeg using your system's package manager. |

---

<a name="contributing"></a>
## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a feature branch (`git checkout -b my-feature`).
3. Make your changes, add tests if applicable.
4. Ensure the code follows the existing style (PEP 8, docstrings).
5. Open a Pull Request with a clear description of the change.

**Areas where help is especially appreciated**

* Adding support for Windows GUI (e.g., PowerShell + `Out-GridView`).
* Improving error handling for malformed SRT files.
* Providing ready-made instruction templates for other language pairs.
* Any other subtitle tools or ideas.

---

<a name="license"></a>
## License

This project is released under the **GPLv3 License** - see the `LICENSE` file for details.

---

### Happy subtitling! 🎬

If you find the toolkit useful, please star the repo or share it. For questions or feature requests, open an issue on GitHub.
