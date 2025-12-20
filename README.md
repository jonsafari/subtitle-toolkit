# Subtitle Toolkit  🍿

A small collection of utilities for **fixing** (time‑shifting) and **translating** SRT subtitle files.  
The tools are deliberately lightweight, command‑line‑first, and can be combined with any LLM that speaks the OpenAI API (including local models).

| Script | What it does | Typical use‑case |
|--------|--------------|------------------|
| `subtitle_timeshift.py` | Shifts every timestamp in an SRT stream by a fixed amount **or** aligns the first subtitle to a user‑provided start time. | Fix subtitles that are out of sync with the video. |
| `subtitle_timeshift_gui.sh` | Small Zenity‑based GUI wrapper around `subtitle_timeshift.py`. | Users who prefer a point‑and‑click workflow on Linux. |
| `subtitle_translate.py` | Splits a large SRT file into manageable chunks, prepends a *translation‑instruction* file, sends each chunk to an OpenAI‑compatible endpoint and writes the translated chunks to disk. | Batch‑translate subtitles (e.g. English → Spanish) while keeping the original formatting. |
| instructions/`subtitle_translate_*.txt` | Example instruction files that tell the LLM how to translate (show/movie context, keep formatting, don’t add extra text, etc.). | Supply to `subtitle_translate.py` via `--instructions`. |

---

## Table of Contents  

1. [Prerequisites](#prerequisites)  
2. [Installation](#installation)  
3. [Quick‑Start](#quick-start)  
   - [Time‑shifting a subtitle file](#time‑shifting-a-subtitle-file)  
   - [Using the GUI wrapper](#using-the-gui-wrapper)  
   - [Translating a subtitle file](#translating-a-subtitle-file)  
4. [Detailed Usage](#detailed-usage)  
   - [`subtitle_timeshift.py`](#subtitle_timeshiftpy)  
   - [`subtitle_timeshift_gui.sh`](#subtitle_timeshift_guish)  
   - [`subtitle_translate.py`](#subtitle_translatepy)  
5. [Configuration & Environment Variables](#configuration)  
6. [Troubleshooting](#troubleshooting)  
7. [Contributing](#contributing)  
8. [License](#license)  

---

<a name="prerequisites"></a>
## 1. Prerequisites  

| Requirement | Minimum version / notes |
|-------------|--------------------------|
| **Python** | 3.8+ (tested on 3.10, 3.11) |
| **pip** | To install the Python dependencies |
| **OpenAI Python SDK** *(only needed for translation)*| `openai>=1.0` – used by `subtitle_translate.py`. You can use a local LLM. |
| **Zenity** *(optional, for the GUI script)* | `zenity` must be in `$PATH`. Available in most Linux distros (`sudo apt install zenity` on Debian/Ubuntu). |
| **A working OpenAI‑compatible endpoint** | Can be the official `api.openai.com`, a self‑hosted model (e.g. Llama.cpp, Ollama, vLLM) or any server that implements the OpenAI chat completion API. |

---

<a name="installation"></a>
## 2. Installation  

```bash
# Clone the repository
git clone https://github.com/jonsafari/subtitle‑toolkit.git
cd subtitle‑toolkit

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt   # (see below)
```

**`requirements.txt`** (included in the repo)

```
openai>=1.0
```

If you only need the time‑shifting utilities you can skip the `openai` dependency.

Make the scripts executable:

```bash
chmod +x subtitle_timeshift.py subtitle_timeshift_gui.sh subtitle_translate.py
```

---

<a name="quick-start"></a>
## 3. Quick‑Start  

### <a name="time-shifting-a-subtitle-file"></a>Time‑shifting a subtitle file  

```bash
# Shift every timestamp 2.5 seconds earlier (positive = earlier)
cat original.srt | ./subtitle_timeshift.py -s 2.5 > shifted.srt

# Or align the first subtitle to a concrete start time
cat original.srt | ./subtitle_timeshift.py -f 00:01:32,945 > aligned.srt
```

### <a name="using-the-gui-wrapper"></a>Using the GUI wrapper  

```bash
./subtitle_timeshift_gui.sh
```

The script will:

1. Prompt you to pick a video (optional – just opens it with the default player).  
2. Ask for the desired start time of the first subtitle (`HH:MM:SS,mmm`).  
3. Let you select the input SRT file and the output filename.  
4. Run `subtitle_timeshift.py` behind the scenes and write the corrected file.

> **Note:** The GUI only works on systems with `zenity` and a graphical environment.

### <a name="translating-a-subtitle-file"></a>Translating a subtitle file  

```bash
# Basic call – uses the default instruction file `subtitle_translate.txt`
./subtitle_translate.py path/to/english.srt

# Custom instruction file, chunk size, output directory and API endpoint
./subtitle_translate.py path/to/english.srt \
    --instructions instructions/subtitle_translate_-_en-es_-_Gavin_and_Stacey.txt \
    --output-dir ./translated_chunks \
    --api-base http://localhost:8080/v1 \
    --model-id llama3:8b \
    --api-key dummy-key
```

Each chunk will be written as `chunk_01.srt`, `chunk_02.srt`, … inside the chosen output directory.  
The content of each file is **only the translated subtitle block** (the instruction header is **not** written to the output – it is only sent to the LLM).

---

<a name="detailed-usage"></a>
## 4. Detailed Usage  

### <a name="subtitle_timeshiftpy"></a>`subtitle_timeshift.py`

| Option | Description |
|--------|-------------|
| `-s`, `--shift-seconds <float>` | Shift every timestamp by the given number of seconds. Positive values move subtitles **earlier** (i.e. they appear sooner). |
| `-f`, `--first-entry-starts-at <HH:MM:SS,mmm>` | Compute the required shift so that the **first** subtitle starts at the supplied time. The script reads the first timestamp it encounters, calculates the difference, and then applies that shift to the whole file. |
| *Input* | The script reads **STDIN**. Pipe a file (`cat file.srt \| …`) or redirect (`./subtitle_timeshift.py -s 1.2 < file.srt`). |
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
2. Calls `subtitle_timeshift.py` with `--first-entry-starts-at`.  
3. Writes the result to the chosen output path.

**Dependencies**

* `zenity` – graphical dialog utility.  
* `open` (macOS) **or** `xdg-open` (Linux) – used to launch the video file.  

If you do not need the GUI, just use `subtitle_timeshift.py` directly.

---

### <a name="subtitle_translatepy"></a>`subtitle_translate.py`

#### Purpose  

Large subtitle files (e.g. full‑season SRTs) often exceed the token limits of LLM APIs. This script:

1. **Splits** the file into *units* (the classic SRT block: index, timestamps, text, blank line).  
2. **Chunks** a configurable number of units together (default 30).  
3. **Prepends** a user‑provided instruction file (e.g. “You are an expert translator …”).  
4. Sends each chunk to an OpenAI‑compatible chat endpoint.  
5. Writes the translated chunk to a separate `.srt` file.

#### Command‑line options  

| Option | Default | Description |
|--------|---------|-------------|
| `input_file` | – | Path to the source `.srt`. |
| `--instructions` | `subtitle_translate.txt` | Path to the instruction file that tells the model how to translate. |
| `--chunk-size` | `30` | Number of subtitle units per API request. |
| `--output-dir` | `/tmp/` | Directory where the translated chunks are saved. |
| `--api-base` | `http://localhost:8080` | Base URL of the OpenAI‑compatible server. |
| `--model-id` | `local-model` | Model identifier used in the request. |
| `--api-key` | `dummy-key` | API key (some servers require a non‑empty value). |

#### Example workflow  

```bash
./subtitle_translate.py season01.srt \
    --instructions instructions/subtitle_translate_-_en-es_-_Schitts_Creek.txt \
    --output-dir ./es_translation \
    --api-base http://localhost:8080/v1 \
    --model-id llama3:8b \
    --api-key dummy-key
```

After the run you will have a series of `chunk_01.srt`, `chunk_02.srt`, … in `./es_translation`.  
You can concatenate them (preserving order) to obtain a single translated file:

```bash
cat ./es_translation/chunk_*.srt > season01_es.srt
```

#### Important notes  

* **Instruction file** – This file is important and provides useful context about the show/movie that you're translating. I recommend copying the Synopsis section of the Wikipedia article for the show/movie that you're translating.  The file must be plain text.
* **API limits** – Adjust `--chunk-size` if you hit token‑limit errors. Smaller chunks = more requests, larger chunks = fewer requests but higher token usage.  
* **Model behaviour** – The provided instruction files explicitly ask the model **not** to add extra text, to keep the original formatting, and to translate only the dialogue. If you notice stray commentary, tweak the instruction file accordingly.

---

<a name="configuration"></a>
## 5. Configuration & Environment Variables  

| Variable | Effect | Example |
|----------|--------|---------|
| `OPENAI_API_BASE` | Overrides `--api-base` if set. | `export OPENAI_API_BASE=http://localhost:11434/v1` |
| `OPENAI_API_KEY` | Overrides `--api-key` if set. | `export OPENAI_API_KEY=sk-xxxx` |
| `PYTHONIOENCODING` | Forces UTF‑8 for stdin/stdout (useful on Windows). | `export PYTHONIOENCODING=utf-8` |

The command‑line arguments always take precedence over environment variables.

---

<a name="troubleshooting"></a>
## 6. Troubleshooting  

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `ValueError: time data ... does not match format` from `subtitle_timeshift.py` | Wrong timestamp format in the SRT (e.g., missing commas). | Verify the source file follows the `HH:MM:SS,mmm` pattern. The script will leave un‑parseable lines untouched. |
| No output file created, script exits with “Input file does not exist” | Wrong path or missing file permissions. | Use an absolute path or `ls` to confirm the file exists. |
| `ImportError: No module named openai` | `openai` Python package not installed. | `pip install -r requirements.txt` (or `pip install openai`). |
| API returns 429 / “rate limit exceeded” | Chunk size too large or server limits. | Reduce `--chunk-size` or add a short `sleep` between requests (modify script). |
| GUI script crashes with “zenity: command not found” | `zenity` not installed. | Install via package manager (`sudo apt install zenity` on Debian/Ubuntu, `brew install zenity` on macOS via Homebrew). |
| Translated subtitles lose numbering or timestamps | The instruction file asked the model to “maintain format” but the model ignored it. | Tighten the instruction (e.g., add “**Do not modify the index numbers or timestamps**”). |
| Output file contains Windows line endings on Linux (or vice‑versa) | Mixed line endings in the source file. | The script preserves the original style; if you need a specific style, run `dos2unix` or `unix2dos` after translation. |

---

<a name="contributing"></a>
## 7. Contributing  

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
## 8. License  

This project is released under the **GPLv3 License** – see the `LICENSE` file for details.

---

### Happy subtitling! 🎬  

If you find the toolkit useful, please star the repo or share it. For questions or feature requests, open an issue on GitHub.
