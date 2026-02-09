# Subtitle Toolkit Web Interface

A modern, simple, fast, and secure web interface for the Subtitle Toolkit command-line utilities.

## Features

- **Time Shift Tool**: Shift timestamps in subtitle files to fix synchronization issues
- **MKV to SRT Converter**: Extract subtitles from MKV files and convert them to SRT format
- **Subtitle Translator**: Translate subtitle files using AI models with customizable instructions

## Installation

1. Clone the repository:
```bash
git clone https://github.com/jonsafari/subtitle-toolkit.git
cd subtitle-toolkit
```

2. Install the web interface dependencies:
```bash
pip install -r requirements-web.txt
```

3. Install the subtitle toolkit dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

```bash
python app.py
```

The web interface will be available at `http://localhost:8000`

## Usage

1. Navigate to the main page
2. Select the tool you want to use (Time Shift, MKV to SRT, or Translate)
3. Upload your file and configure the tool settings
4. Process your subtitle file
5. Download the results

## Security

This web interface is designed with security in mind:
- Input validation for all file uploads
- Sanitization of user inputs
- Secure handling of temporary files
- No direct file system access from the web interface

## Requirements

- Python 3.8+
- FFmpeg (for MKV to SRT conversion)
- OpenAI Python SDK (for translation, optional)