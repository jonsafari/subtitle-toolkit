# Subtitle Toolkit  🍿

A small collection of utilities for **fixing** (time‑shifting) and **translating** SRT subtitle files. There's command-line tools as well as a web interface.
The tools are deliberately lightweight, command‑line‑first, and work with any LLM provider via litellm (OpenAI, Anthropic, Gemini, Databricks, and local models).

| Script | What it does | Typical use‑case |
|--------|--------------|------------------|
| `subtitle-tk timeshift` | Shifts every timestamp in an SRT stream by a fixed amount **or** aligns the first subtitle to a user‑provided start time. | Fix subtitles that are out of sync with the video. |
| `subtitle_timeshift_gui.sh` | Small Zenity‑based GUI wrapper around `subtitle-tk timeshift`. | Users who prefer a point‑and‑click workflow on Linux. |
| `subtitle-tk mkv2srt` | Extracts subtitles from MKV files and converts them to SRT format. | Extract subtitles from MKV files for use with video players. |
| `subtitle-tk translate` | Translates a subtitle (SRT/SubRip) file, using a *translation‑instruction* file and an LLM endpoint via litellm. | Translate subtitles (e.g. English → Spanish) while keeping the original formatting. |
| translation_instruction_prompts/`subtitle_translate_*.txt` | Example instruction files that tell the LLM how to translate (show/movie context, keep formatting, don’t add extra text, etc.). | Supply to `subtitle-tk translate` via `--instructions`. |

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
git clone https://github.com/jonsafari/subtitle‑toolkit.git
cd subtitle‑toolkit

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

### <a name="time-shifting-a-subtitle-file"></a>Time‑shifting a subtitle file

```bash
# Shift every timestamp 2.5 seconds earlier (positive = earlier)
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

1. Prompt you to pick a video (optional – just opens it with the default player).
2. Ask for the desired start time of the first subtitle (`HH:MM:SS,mmm`).
3. Let you select the input SRT file and the output filename.
4. Run `subtitle-tk timeshift` behind the scenes and write the corrected file.

> **Note:** The GUI only works on systems with `zenity` and a graphical environment.

### <a name="translating-a-subtitle-file"></a>Translating a subtitle file

```bash
# Basic call – uses the default instruction file `translation_instruction_prompts/subtitle_translate_-_en-es_-_default.txt`
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
| `-s`, `--shift-seconds <float>` | Shift every timestamp by the given number of seconds. Positive values move subtitles **earlier** (i.e. they appear sooner). |
| `-f`, `--first-entry-starts-at <HH:MM:SS[,.mmm]>` | Compute the required shift so that the **first** subtitle starts at the supplied time (sub‑seconds optional). The script reads the first timestamp it encounters, calculates the difference, and then applies that shift to the whole file. |
| *Input* | The script reads **STDIN**. Pipe a file (`cat file.srt \| …`) or redirect (`subtitle-tk timeshift -s 1.2 < file.srt`). |
| *Output* | Printed to **STDOUT** – redirect to a new file. |

**Behaviour notes**

* The script tolerates malformed timestamp lines – they are passed through unchanged.
* If a shift would produce a negative time, the timestamp is clamped to `00:00:00,000`.
* The script keeps the original line endings (`\n` or `\r\n`).

---

### <a name="subtitle_timeshift_guish"></a>`subtitle_timeshift_gui.sh`

A thin wrapper that:

1. Uses `zenity` dialogs to collect:
   * (optional) a video file – opened with the system’s default player (`open` on macOS, `xdg-open` on Linux).
   * Desired start time (`HH:MM:SS,mmm`).
   * Input SRT file.
   * Output filename.
2. Calls `subtitle-tk timeshift` with `--first-entry-starts-at`.
3. Writes the result to the chosen output path.

**Dependencies**

* `zenity` – graphical dialog utility.
* `open` (macOS) **or** `xdg-open` (Linux) – used to launch the video file.

If you do not need the GUI, just use `subtitle-tk timeshift` directly.

---

### <a name="subtitle_mkv2srt"></a>`subtitle-tk mkv2srt`

#### Purpose

Extracts subtitles from MKV files and converts them to SRT (SubRip) format.

#### Command‑line options

| Option | Default | Description |
|--------|---------|-------------|
| `--input` or `-i` | – | Path to the input MKV file (required). |
| `--output` or `-o` | – | Output SRT file path (optional). If not specified, extracts all subtitles to individual files. |
| `--language` or `-l` | – | Language code to filter subtitles (e.g., "en", "es"). |

#### Examples

```bash
# Extract all subtitles from an MKV file
subtitle-tk mkv2srt --input video.mkv

# Extract subtitles in a specific language
subtitle-tk mkv2srt --input video.mkv --language en

# Extract to a specific output file
subtitle-tk mkv2srt --input video.mkv --output subtitles.srt
```

#### Important notes

* The script requires `ffmpeg` to be installed and available in `$PATH`.
* ASS/SSA formatting tags like {\an7} are automatically removed to ensure compatibility with video players.
* If no subtitles are found in the MKV file, the script will report this and exit.

---

### <a name="subtitle_translatepy"></a>`subtitle-tk translate`

#### Purpose

Large subtitle files (e.g. full‑season SRTs) often exceed the token limits of LLM APIs. This script:

1. **Splits** the file into *units* (the classic SRT block: index, timestamps, text, blank line).
2. **Chunks** a configurable number of units together (default 30).
3. **Prepends** a user‑provided instruction file (e.g. "You are an expert translator …").
4. Sends each chunk to an LLM endpoint via litellm.
5. Writes the translated output to a new `.srt` file.

#### Command‑line options

| Option | Default | Description |
|--------|---------|-------------|
| `input_file` | – | Path to the source `.srt`. |
| `--instructions` | `translation_instruction_prompts/subtitle_translate_-_en-es_-_default.txt` | Path to the instruction file that tells the model how to translate. |
| `--chunk-size` | `30` | Number of subtitle units per API request. |
| `--output` | `<input>_translated.srt` | Output translated SRT file name. |
| `--api-base` | `http://localhost:8080` | Base URL of the LLM server (for self-hosted endpoints). |
| `--model-id` | `local-model` | Model identifier (e.g., `llama3:8b`, `anthropic/claude-4-6-sonnet`, `gemini/gemini-3-flash`). |
| `--api-key` | `dummy-key` | API key (some servers require a non‑empty value). |

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

* **Instruction file** – This file is important and provides useful context about the show/movie that you're translating. I recommend copying the Synopsis section of the Wikipedia article for the show/movie that you're translating.  The file must be plain text.
* **API limits** – Adjust `--chunk-size` if you hit token‑limit errors. Smaller chunks = more requests, larger chunks = fewer requests but higher token usage.
* **Model behaviour** – The provided instruction files explicitly ask the model **not** to add extra text, to keep the original formatting, and to translate only the dialogue. If you notice stray commentary, tweak the instruction file accordingly.


---

<a name="configuration"></a>
## Configuration & Environment Variables

| Variable | Effect | Example |
|----------|--------|---------|
| `LLM_API_KEY` | API key for the LLM provider. | `export LLM_API_KEY=sk-xxxx` |
| `ANTHROPIC_API_KEY` | API key for Anthropic models. | `export ANTHROPIC_API_KEY=sk-ant-xxxx` |
| `GEMINI_API_KEY` | API key for Google Gemini models. | `export GEMINI_API_KEY=AIzaSyxxxx` |
| `PYTHONIOENCODING` | Forces UTF‑8 for stdin/stdout (useful on Windows). | `export PYTHONIOENCODING=utf-8` |

The command‑line arguments always take precedence over environment variables.

---

<a name="troubleshooting"></a>
## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `ValueError: time data ... does not match format` from `subtitle-tk timeshift` | Wrong timestamp format in the SRT (e.g., missing commas). | Verify the source file follows the `HH:MM:SS,mmm` pattern. The script will leave un‑parseable lines untouched. |
| No output file created, script exits with "Input file does not exist" | Wrong path or missing file permissions. | Use an absolute path or `ls` to confirm the file exists. |
| `ImportError: No module named litellm` | `litellm` Python package not installed. | `pip install -r requirements.txt` (or `pip install litellm`). |
| API returns 429 / "rate limit exceeded" | Chunk size too large or server limits. | Reduce `--chunk-size` or add a short `sleep` between requests (modify script). |
| GUI script crashes with "zenity: command not found" | `zenity` not installed. | Install via package manager (`sudo apt install zenity` on Debian/Ubuntu, `brew install zenity` on macOS via Homebrew). |
| Translated subtitles lose numbering or timestamps | The instruction file asked the model to "maintain format" but the model ignored it. | Tighten the instruction (e.g., add “**Do not modify the index numbers or timestamps**”). |
| Output file contains Windows line endings on Linux (or vice‑versa) | Mixed line endings in the source file. | The script preserves the original style; if you need a specific style, run `dos2unix` or `unix2dos` after translation. |
| `Error: ffmpeg is required but not found` | FFmpeg not installed. | Install FFmpeg using your system's package manager. |

---

<a name="contributing"></a>
## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a feature branch (`git checkout -b my‑feature`).
3. Make your changes, add tests if applicable.
4. Ensure the code follows the existing style (PEP 8, docstrings).
5. Open a Pull Request with a clear description of the change.

**Areas where help is especially appreciated**

* Adding support for Windows GUI (e.g., PowerShell + `Out-GridView`).
* Improving error handling for malformed SRT files.
* Providing ready‑made instruction templates for other language pairs.
* Any other subtitle tools or ideas.

---

<a name="license"></a>
## License

This project is released under the **GPLv3 License** – see the `LICENSE` file for details.

---

### Happy subtitling! 🎬

If you find the toolkit useful, please star the repo or share it. For questions or feature requests, open an issue on GitHub.
