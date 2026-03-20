#!/usr/bin/env python3
"""
FastAPI web interface for the Subtitle Toolkit
"""
from fastapi import FastAPI, Request, Form, UploadFile
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import subprocess
import os
import tempfile
from pathlib import Path
import shutil
import json
from typing import Dict, Any, Optional, List

# Get the project root (parent of web directory)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Get the app directory (parent of web directory)
APP_DIR = PROJECT_ROOT

app = FastAPI(title="Subtitle Toolkit Web Interface")
templates = Jinja2Templates(directory=PROJECT_ROOT / "templates")
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")

# Translation directory (relative to project root)
TRANSLATIONS_DIR = PROJECT_ROOT / "translations"

# Available languages
AVAILABLE_LANGUAGES = ["en", "ar", "de", "es", "fa", "fr", "id", "it", "ja", "ko", "nl", "pl", "pt", "tr", "uk", "vi", "zh"]
DEFAULT_LANGUAGE = "en"

def load_translations(language: str) -> Dict[str, Any]:
    """Load translations for a specific language."""
    translation_file = TRANSLATIONS_DIR / f"{language}.json"
    if translation_file.exists():
        with open(translation_file, "r", encoding="utf-8") as f:
            return json.load(f)  # type: ignore[no-any-return]
    return {}

def get_language_from_request(request: Request) -> str:
    """Get language from query parameter, cookie, or default."""
    lang = request.query_params.get("lang")
    if not lang:
        lang = request.cookies.get("language", DEFAULT_LANGUAGE)
    if lang not in AVAILABLE_LANGUAGES:
        lang = DEFAULT_LANGUAGE
    return lang

@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "static" / "favicon.ico")

# Tool paths (relative to src directory)
TIMESHIFT_SCRIPT = PROJECT_ROOT / "timeshift.py"
MKV2SRT_SCRIPT = PROJECT_ROOT / "mkv2srt.py"
TRANSLATE_SCRIPT = PROJECT_ROOT / "translate.py"
CONVERT_SCRIPT = PROJECT_ROOT / "convert.py"
AUTOSYNC_SCRIPT = PROJECT_ROOT / "autosync.py"
SUBTITLE_TRACKS_SCRIPT = PROJECT_ROOT / "subtitle_tracks.py"

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request) -> HTMLResponse:
    lang = get_language_from_request(request)
    return templates.TemplateResponse(request, "index.html", {
        "lang": lang,
        "translations": load_translations(lang)
    })

@app.get("/timeshift", response_class=HTMLResponse)
async def timeshift_page(request: Request) -> HTMLResponse:
    lang = get_language_from_request(request)
    return templates.TemplateResponse(request, "timeshift.html", {
        "lang": lang,
        "translations": load_translations(lang)
    })

@app.post("/timeshift", response_class=HTMLResponse)
async def timeshift_submit(
    request: Request,
    shift_seconds: Optional[float] = Form(None),
    first_entry_starts_at: Optional[str] = Form(None),
    srt_file: Optional[str] = Form(None)
) -> HTMLResponse:
    lang = get_language_from_request(request)
    translations = load_translations(lang)

    # Validate inputs
    if not srt_file:
        return templates.TemplateResponse(request, "timeshift.html", {
            "lang": lang,
            "translations": translations,
            "error": translations.get("please_upload_srt", "Please upload an SRT file")
        })

    # Process the file
    try:
        # Create a temporary file for the input
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as tmp_input:
            tmp_input.write(srt_file)
            tmp_input_path = tmp_input.name

        # Build command
        cmd: List[str] = ["python3", str(TIMESHIFT_SCRIPT)]
        if shift_seconds is not None:
            cmd.extend(["--shift-seconds", str(shift_seconds)])
        elif first_entry_starts_at:
            cmd.extend(["--first-entry-starts-at", first_entry_starts_at])
        else:
            return templates.TemplateResponse(request, "timeshift.html", {
                "lang": lang,
                "translations": translations,
                "error": translations.get("error_processing_file", "Please provide either shift seconds or start time")
            })

        # Run the command
        result = subprocess.run(
            cmd,
            input=srt_file,
            text=True,
            capture_output=True,
            check=True
        )

        # Clean up
        os.unlink(tmp_input_path)

        return templates.TemplateResponse(request, "timeshift_result.html", {
            "lang": lang,
            "translations": translations,
            "output": result.stdout
        })

    except subprocess.CalledProcessError as e:
        return templates.TemplateResponse(request, "timeshift.html", {
            "lang": lang,
            "translations": translations,
            "error": f"{translations.get('error_processing_file', 'Error processing file')}: {e.stderr}"
        })
    except Exception as e:
        return templates.TemplateResponse(request, "timeshift.html", {
            "lang": lang,
            "translations": translations,
            "error": f"{translations.get('unexpected_error', 'Unexpected error')}: {str(e)}"
        })

@app.post("/timeshift/download")
async def timeshift_download(request: Request, output: Optional[str] = Form(None)):  # type: ignore[no-untyped-def]
    if not output:
        # If no output provided, redirect to timeshift page
        return templates.TemplateResponse(request, "timeshift.html", {})

    # Create a temporary file with the output content
    tmp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write(output)
            tmp_file_path = tmp_file.name

        # Return the file for download
        return FileResponse(
            tmp_file_path,
            media_type="application/octet-stream",
            filename="processed_subtitles.srt"
        )
    except Exception:
        # Clean up in case of error
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        raise

@app.get("/mkv2srt", response_class=HTMLResponse)
async def mkv2srt_page(request: Request) -> HTMLResponse:
    lang = get_language_from_request(request)
    return templates.TemplateResponse(request, "mkv2srt.html", {
        "lang": lang,
        "translations": load_translations(lang)
    })

@app.post("/mkv2srt", response_class=HTMLResponse)
async def mkv2srt_submit(
    request: Request,
    mkv_file: Optional[UploadFile] = Form(None),
    language: Optional[str] = Form(None),
    output_file: Optional[str] = Form(None)
) -> HTMLResponse:
    lang = get_language_from_request(request)
    translations = load_translations(lang)

    # Validate inputs
    if not mkv_file or mkv_file.filename is None or mkv_file.filename == "":
        return templates.TemplateResponse(request, "mkv2srt.html", {
            "lang": lang,
            "translations": translations,
            "error": translations.get("please_upload_mkv", "Please upload an MKV file")
        })

    # Process the file
    try:
        # Create a temporary file for the input
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.mkv', delete=False) as tmp_input:
            # Read file content and write to temporary file
            content = await mkv_file.read()
            tmp_input.write(content)
            tmp_input_path = tmp_input.name

        # Build command
        cmd: List[str] = ["python3", str(MKV2SRT_SCRIPT), "--input", str(tmp_input_path)]
        if language:
            cmd.extend(["--language", language])
        if output_file:
            cmd.extend(["--output", output_file])

        # Run the command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Clean up
        os.unlink(tmp_input_path)

        return templates.TemplateResponse(request, "mkv2srt_result.html", {
            "lang": lang,
            "translations": translations,
            "output": result.stdout
        })

    except subprocess.CalledProcessError as e:
        # Provide more detailed error information
        error_msg = f"{translations.get('error_processing_file', 'Error processing file')}: {e.stderr} ({translations.get('return_code', 'return code')}: {e.returncode})"
        if e.stdout:
            error_msg += f" | {translations.get('stdout', 'stdout')}: {e.stdout[:200]}..."
        return templates.TemplateResponse(request, "mkv2srt.html", {
            "lang": lang,
            "translations": translations,
            "error": error_msg
        })
    except Exception as e:
        return templates.TemplateResponse(request, "mkv2srt.html", {
            "lang": lang,
            "translations": translations,
            "error": f"{translations.get('unexpected_error', 'Unexpected error')}: {str(e)} ({translations.get('type', 'type')}: {type(e).__name__})"
        })

@app.get("/translate", response_class=HTMLResponse)
async def translate_page(request: Request) -> HTMLResponse:
    lang = get_language_from_request(request)
    # Get available instruction files (relative to app.py location)
    instruction_files: List[Path] = []
    instruction_dir = APP_DIR / "translation_instruction_prompts"
    if instruction_dir.exists():
        instruction_files = [f for f in instruction_dir.iterdir() if f.is_file()]

    return templates.TemplateResponse(request, "translate.html", {
        "lang": lang,
        "translations": load_translations(lang),
        "instruction_files": instruction_files
    })

@app.post("/translate", response_class=HTMLResponse)
async def translate_submit(
    request: Request,
    srt_file: Optional[str] = Form(None),
    instructions_file: Optional[str] = Form(None),
    chunk_size: int = Form(30),
    api_base: str = Form("http://localhost:8080"),
    model_id: str = Form("local-model"),
    api_key: str = Form("dummy-key"),
    output_file: Optional[str] = Form(None)
) -> HTMLResponse:
    lang = get_language_from_request(request)
    translations = load_translations(lang)

    # Validate inputs
    if not srt_file:
        return templates.TemplateResponse(request, "translate.html", {
            "lang": lang,
            "translations": translations,
            "error": translations.get("please_upload_srt", "Please upload an SRT file")
        })

    # Process the file
    try:
        # Create a temporary file for the input
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as tmp_input:
            tmp_input.write(srt_file)
            tmp_input_path = tmp_input.name

        # Create a temporary instruction file if provided
        instruction_path = None
        if instructions_file:
            instruction_path = Path(instructions_file)
            if not instruction_path.exists():
                # Create a temporary instruction file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_inst:
                    tmp_inst.write(instructions_file)
                    instruction_path = Path(tmp_inst.name)

        # Build command
        cmd: List[str] = ["python3", str(TRANSLATE_SCRIPT), str(tmp_input_path)]
        if instruction_path:
            cmd.extend(["--instructions", str(instruction_path)])
        cmd.extend(["--chunk-size", str(chunk_size)])
        cmd.extend(["--api-base", api_base])
        cmd.extend(["--model-id", model_id])
        cmd.extend(["--api-key", api_key])
        if output_file:
            cmd.extend(["--output", output_file])

        # Run the command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Clean up
        os.unlink(tmp_input_path)
        if instruction_path and instruction_path.name.startswith('tmp'):
            os.unlink(instruction_path)

        return templates.TemplateResponse(request, "translate_result.html", {
            "lang": lang,
            "translations": translations,
            "output": result.stdout
        })

    except subprocess.CalledProcessError as e:
        return templates.TemplateResponse(request, "translate.html", {
            "lang": lang,
            "translations": translations,
            "error": f"{translations.get('error_processing_file', 'Error processing file')}: {e.stderr}"
        })
    except Exception as e:
        return templates.TemplateResponse(request, "translate.html", {
            "lang": lang,
            "translations": translations,
            "error": f"{translations.get('unexpected_error', 'Unexpected error')}: {str(e)}"
        })

@app.get("/convert", response_class=HTMLResponse)
async def convert_page(request: Request) -> HTMLResponse:
    lang = get_language_from_request(request)
    return templates.TemplateResponse(request, "convert.html", {
        "lang": lang,
        "translations": load_translations(lang)
    })

@app.post("/convert", response_class=HTMLResponse)
async def convert_submit(
    request: Request,
    subtitle_file: Optional[str] = Form(None),
    input_format: Optional[str] = Form(None),
    output_format: Optional[str] = Form(None),
    preserve_formatting: bool = Form(True)
) -> HTMLResponse:
    lang = get_language_from_request(request)
    translations = load_translations(lang)

    # Validate inputs
    if not subtitle_file:
        return templates.TemplateResponse(request, "convert.html", {
            "lang": lang,
            "translations": translations,
            "error": translations.get("please_upload_subtitle", "Please upload a subtitle file")
        })

    if not output_format:
        return templates.TemplateResponse(request, "convert.html", {
            "lang": lang,
            "translations": translations,
            "error": translations.get("please_select_output_format", "Please select an output format")
        })

    # Process the file
    try:
        # Build command
        cmd: List[str] = ["python3", str(CONVERT_SCRIPT)]
        cmd.extend(["--output-format", output_format])
        if input_format and input_format != "auto":
            cmd.extend(["--input-format", input_format])
        if not preserve_formatting:
            cmd.append("--normalize-text")

        # Run the command with input from stdin
        result = subprocess.run(
            cmd,
            input=subtitle_file,
            text=True,
            capture_output=True,
            check=True
        )

        return templates.TemplateResponse(request, "convert_result.html", {
            "lang": lang,
            "translations": translations,
            "output": result.stdout,
            "output_format": output_format
        })

    except subprocess.CalledProcessError as e:
        return templates.TemplateResponse(request, "convert.html", {
            "lang": lang,
            "translations": translations,
            "error": f"{translations.get('error_processing_file', 'Error processing file')}: {e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr}"
        })
    except Exception as e:
        return templates.TemplateResponse(request, "convert.html", {
            "lang": lang,
            "translations": translations,
            "error": f"{translations.get('unexpected_error', 'Unexpected error')}: {str(e)}"
        })

@app.post("/convert/download")
async def convert_download(request: Request, output: Optional[str] = Form(None), output_format: Optional[str] = Form(None)):  # type: ignore[no-untyped-def]
    if not output:
        # If no output provided, redirect to convert page
        return templates.TemplateResponse(request, "convert.html", {})

    # Determine file extension from output format
    format_to_ext = {
        "srt": ".srt",
        "vtt": ".vtt",
        "ass": ".ass",
        "ssa": ".ssa",
        "sub": ".sub",
        "sbv": ".sbv",
        "txt": ".txt",
        "sami": ".sami",
        "smi": ".smi",
        "csv": ".csv",
        "tsv": ".tsv",
        "json": ".json",
        "textgrid": ".TextGrid",
        "gemini": ".json",
        "ttml": ".ttml",
        "imsc1": ".ttml",
        "ebu_tt_d": ".ttml",
        "avid_ds": "_avid.txt",
        "fcpxml": ".fcpxml",
        "premiere_xml": ".xml",
        "audition_csv": "_audition.csv",
        "edimarker_csv": "_edimarker.csv",
    }

    ext = format_to_ext.get(output_format, ".srt")

    # Create a temporary file with the output content
    tmp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix=ext, delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write(output)
            tmp_file_path = tmp_file.name

        # Return the file for download
        return FileResponse(
            tmp_file_path,
            media_type="application/octet-stream",
            filename=f"converted_subtitles{ext}"
        )
    except Exception:
        # Clean up in case of error
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        raise

@app.get("/autosync", response_class=HTMLResponse)
async def autosync_page(request: Request) -> HTMLResponse:
    lang = get_language_from_request(request)
    return templates.TemplateResponse(request, "autosync.html", {
        "lang": lang,
        "translations": load_translations(lang)
    })

@app.post("/autosync", response_class=HTMLResponse)
async def autosync_submit(
    request: Request,
    srt_file: Optional[str] = Form(None),
    correct_at: Optional[str] = Form(None),
    offset_at: Optional[str] = Form(None),
    offset_seconds: Optional[float] = Form(None),
    drift_rate: Optional[str] = Form(None),
    reference_time: Optional[str] = Form(None),
    sync_point_time: Optional[List[str]] = Form(None),
    sync_point_offset: Optional[List[float]] = Form(None)
) -> HTMLResponse:
    lang = get_language_from_request(request)
    translations = load_translations(lang)

    # Validate inputs
    if not srt_file:
        return templates.TemplateResponse(request, "autosync.html", {
            "lang": lang,
            "translations": translations,
            "error": translations.get("please_upload_srt", "Please upload an SRT file")
        })

    # Process the file
    try:
        # Build command
        cmd: List[str] = ["python3", str(AUTOSYNC_SCRIPT)]

        # Determine which mode to use
        if drift_rate:
            # Known drift rate mode
            cmd.extend(["--drift-rate", drift_rate])
            if reference_time:
                cmd.extend(["--reference", reference_time])
        elif sync_point_time and len(sync_point_time) >= 2:
            # Multi-point mode
            points = []
            for i in range(len(sync_point_time)):
                if sync_point_offset and i < len(sync_point_offset):
                    points.append(f"{sync_point_time[i]}:{sync_point_offset[i]}")
                else:
                    points.append(f"{sync_point_time[i]}:0")
            cmd.extend(["--points"] + points)
        elif correct_at and offset_at and offset_seconds is not None:
            # Two-point mode
            cmd.extend(["--correct-at", correct_at])
            cmd.extend(["--offset-at", offset_at])
            cmd.extend(["--offset", str(offset_seconds)])
        else:
            return templates.TemplateResponse(request, "autosync.html", {
                "lang": lang,
                "translations": translations,
                "error": translations.get("error_processing_file", "Please provide valid correction parameters")
            })

        # Run the command with input from stdin
        result = subprocess.run(
            cmd,
            input=srt_file,
            text=True,
            capture_output=True,
            check=True
        )

        return templates.TemplateResponse(request, "autosync_result.html", {
            "lang": lang,
            "translations": translations,
            "output": result.stdout
        })

    except subprocess.CalledProcessError as e:
        return templates.TemplateResponse(request, "autosync.html", {
            "lang": lang,
            "translations": translations,
            "error": f"{translations.get('error_processing_file', 'Error processing file')}: {e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr}"
        })
    except Exception as e:
        return templates.TemplateResponse(request, "autosync.html", {
            "lang": lang,
            "translations": translations,
            "error": f"{translations.get('unexpected_error', 'Unexpected error')}: {str(e)}"
        })

@app.post("/autosync/download")
async def autosync_download(request: Request, output: Optional[str] = Form(None)):  # type: ignore[no-untyped-def]
    if not output:
        # If no output provided, redirect to autosync page
        return templates.TemplateResponse(request, "autosync.html", {})

    # Create a temporary file with the output content
    tmp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write(output)
            tmp_file_path = tmp_file.name

        # Return the file for download
        return FileResponse(
            tmp_file_path,
            media_type="application/octet-stream",
            filename="corrected_subtitles.srt"
        )
    except Exception:
        # Clean up in case of error
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        raise

@app.get("/subtitle-tracks", response_class=HTMLResponse)
async def subtitle_tracks_page(request: Request) -> HTMLResponse:
    """Show the subtitle tracks management page."""
    lang = get_language_from_request(request)
    return templates.TemplateResponse(request, "subtitle_tracks.html", {
        "lang": lang,
        "translations": load_translations(lang)
    })


@app.post("/subtitle-tracks/list", response_class=HTMLResponse)
async def subtitle_tracks_list(
    request: Request,
    video_file: Optional[UploadFile] = Form(None)
) -> HTMLResponse:
    """List subtitle tracks in a video file."""
    lang = get_language_from_request(request)
    translations = load_translations(lang)

    if not video_file or video_file.filename is None or video_file.filename == "":
        return templates.TemplateResponse(request, "subtitle_tracks.html", {
            "lang": lang,
            "translations": translations,
            "error": translations.get("please_upload_video", "Please upload a video file")
        })

    try:
        # Save uploaded file (stream to disk to handle large files)
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.mkv', delete=False) as tmp_input:
            while True:
                chunk = await video_file.read(8192)
                if not chunk:
                    break
                tmp_input.write(chunk)
            tmp_input_path = tmp_input.name

        # Run list command
        cmd: List[str] = ["python3", str(SUBTITLE_TRACKS_SCRIPT), "list", str(tmp_input_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Clean up
        os.unlink(tmp_input_path)

        return templates.TemplateResponse(request, "subtitle_tracks_result.html", {
            "lang": lang,
            "translations": translations,
            "output": result.stdout,
            "tool_name": "Track Listing"
        })

    except subprocess.CalledProcessError as e:
        error_msg = f"{translations.get('error_processing_file', 'Error processing file')}: {e.stderr}"
        return templates.TemplateResponse(request, "subtitle_tracks.html", {
            "lang": lang,
            "translations": translations,
            "error": error_msg
        })
    except Exception as e:
        return templates.TemplateResponse(request, "subtitle_tracks.html", {
            "lang": lang,
            "translations": translations,
            "error": f"{translations.get('unexpected_error', 'Unexpected error')}: {str(e)}"
        })


@app.post("/subtitle-tracks/extract", response_class=HTMLResponse)
async def subtitle_tracks_extract(
    request: Request,
    video_file: Optional[UploadFile] = Form(None),
    track_index: Optional[int] = Form(None),
    language: Optional[str] = Form(None),
    extract_all: bool = Form(False),
    as_zip: bool = Form(False),
    forced_only: bool = Form(False),
    no_forced: bool = Form(False)
) -> HTMLResponse:
    """Extract subtitle tracks from a video file."""
    lang = get_language_from_request(request)
    translations = load_translations(lang)

    if not video_file or video_file.filename is None or video_file.filename == "":
        return templates.TemplateResponse(request, "subtitle_tracks.html", {
            "lang": lang,
            "translations": translations,
            "error": translations.get("please_upload_video", "Please upload a video file")
        })

    try:
        # Create temp directory for outputs
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir_path = Path(tmp_dir)

            # Save uploaded file (stream to disk to handle large files)
            tmp_input_path = tmp_dir_path / "input.mkv"
            with open(tmp_input_path, 'wb') as f:
                while True:
                    chunk = await video_file.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)

            # Build command
            cmd: List[str] = ["python3", str(SUBTITLE_TRACKS_SCRIPT), "extract", str(tmp_input_path)]

            if extract_all:
                cmd.extend(["--all"])
                if as_zip:
                    cmd.extend(["--as-zip"])
                cmd.extend(["--output", str(tmp_dir_path)])
            else:
                if track_index is not None:
                    cmd.extend(["--track", str(track_index)])
                if language:
                    cmd.extend(["--language", language])
                if forced_only:
                    cmd.append("--forced-only")
                if no_forced:
                    cmd.append("--no-forced")

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Find output files
            output_files = list(tmp_dir_path.glob("*.srt"))
            zip_files = list(tmp_dir_path.glob("*.zip"))

            if zip_files:
                # Read ZIP file content and return as Response
                with open(zip_files[0], 'rb') as f:
                    zip_content = f.read()
                from starlette.responses import Response
                return Response(
                    content=zip_content,
                    media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename={video_file.filename.rsplit('.', 1)[0]}_subtitles.zip"}
                )
            elif output_files:
                # Return first SRT file
                with open(output_files[0], 'r', encoding='utf-8') as f:
                    content = f.read()
                return templates.TemplateResponse(request, "subtitle_tracks_result.html", {
                    "lang": lang,
                    "translations": translations,
                    "output": content,
                    "tool_name": "Track Extraction",
                    "download_filename": output_files[0].name
                })
            else:
                return templates.TemplateResponse(request, "subtitle_tracks.html", {
                    "lang": lang,
                    "translations": translations,
                    "error": "No subtitle tracks were extracted"
                })

    except subprocess.CalledProcessError as e:
        error_msg = f"{translations.get('error_processing_file', 'Error processing file')}: {e.stderr}"
        return templates.TemplateResponse(request, "subtitle_tracks.html", {
            "lang": lang,
            "translations": translations,
            "error": error_msg
        })
    except Exception as e:
        return templates.TemplateResponse(request, "subtitle_tracks.html", {
            "lang": lang,
            "translations": translations,
            "error": f"{translations.get('unexpected_error', 'Unexpected error')}: {str(e)}"
        })


@app.post("/subtitle-tracks/merge", response_class=HTMLResponse)
async def subtitle_tracks_merge(
    request: Request,
    subtitle_files: Optional[List[UploadFile]] = Form(None),
    priority: str = Form("first")
) -> HTMLResponse:
    """Merge multiple subtitle files."""
    lang = get_language_from_request(request)
    translations = load_translations(lang)

    if not subtitle_files or len(subtitle_files) < 2:
        return templates.TemplateResponse(request, "subtitle_tracks.html", {
            "lang": lang,
            "translations": translations,
            "error": translations.get("please_upload_at_least_two", "Please upload at least two subtitle files")
        })

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir_path = Path(tmp_dir)

            # Save uploaded files (stream to disk to handle large files)
            input_files = []
            for i, file in enumerate(subtitle_files):
                if file and file.filename:
                    tmp_file = tmp_dir_path / f"input_{i}.srt"
                    with open(tmp_file, 'wb') as f:
                        while True:
                            chunk = await file.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)
                    input_files.append(tmp_file)

            if len(input_files) < 2:
                return templates.TemplateResponse(request, "subtitle_tracks.html", {
                    "lang": lang,
                    "translations": translations,
                    "error": "Need at least two valid subtitle files to merge"
                })

            # Output file
            output_file = tmp_dir_path / "merged.srt"

            # Build command
            cmd: List[str] = ["python3", str(SUBTITLE_TRACKS_SCRIPT), "merge"]
            for f in input_files:
                cmd.append(str(f))
            cmd.extend(["--output", str(output_file), "--priority", priority])

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Read output
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()

            return templates.TemplateResponse(request, "subtitle_tracks_result.html", {
                "lang": lang,
                "translations": translations,
                "output": content,
                "tool_name": "Subtitle Merging",
                "download_filename": "merged.srt"
            })

    except subprocess.CalledProcessError as e:
        error_msg = f"{translations.get('error_processing_file', 'Error processing file')}: {e.stderr}"
        return templates.TemplateResponse(request, "subtitle_tracks.html", {
            "lang": lang,
            "translations": translations,
            "error": error_msg
        })
    except Exception as e:
        return templates.TemplateResponse(request, "subtitle_tracks.html", {
            "lang": lang,
            "translations": translations,
            "error": f"{translations.get('unexpected_error', 'Unexpected error')}: {str(e)}"
        })


@app.post("/subtitle-tracks/download")
async def subtitle_tracks_download(request: Request, output: Optional[str] = Form(None), filename: Optional[str] = Form(None)):  # type: ignore[no-untyped-def]
    """Download subtitle tracks result."""
    if not output:
        return templates.TemplateResponse(request, "subtitle_tracks.html", {})

    # Create a temporary file with the output content
    tmp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write(output)
            tmp_file_path = tmp_file.name

        # Return the file for download
        return FileResponse(
            tmp_file_path,
            media_type="application/octet-stream",
            filename=filename or "subtitles.srt"
        )
    except Exception:
        # Clean up in case of error
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        raise


@app.post("/set-language")
async def set_language(request: Request, lang: str = Form(...)) -> RedirectResponse:
    """Set the language preference."""
    if lang not in AVAILABLE_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    response = RedirectResponse(url=request.headers.get("referer", "/"), status_code=303)
    response.set_cookie("language", lang, max_age=30*24*60*60)  # 30 days
    return response

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Subtitle Toolkit Web Interface")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)
