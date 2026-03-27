#!/usr/bin/env python3
"""
FastAPI web interface for the Subtitle Toolkit
"""
from fastapi import FastAPI, Request, Form, UploadFile
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import subprocess
import os
import sys
import tempfile
from pathlib import Path
import shutil
import json
import asyncio
from typing import Dict, Any, Optional, List, Generator

# Get the project root (parent of web directory)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# PROJECT_ROOT is already the src directory, so add it to path
sys.path.insert(0, str(PROJECT_ROOT))

# Import translate_batch module
try:
    from translate_batch import scan_directory, translate_batch
    print(f"DEBUG: translate_batch imported successfully: {translate_batch}")
except ImportError as e:
    print(f"Warning: Could not import translate_batch: {e}")
    scan_directory = None
    translate_batch = None

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

    # Build form values for error recovery
    form_values = {
        "srt_file": srt_file or "",
        "shift_seconds": str(shift_seconds) if shift_seconds is not None else "",
        "first_entry_starts_at": first_entry_starts_at or ""
    }

    # Validate inputs
    if not srt_file:
        return templates.TemplateResponse(request, "timeshift.html", {
            "lang": lang,
            "translations": translations,
            "error": translations.get("please_upload_srt", "Please upload an SRT file"),
            "form_values": form_values
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
                "error": translations.get("error_processing_file", "Please provide either shift seconds or start time"),
                "form_values": form_values
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
            "error": f"{translations.get('error_processing_file', 'Error processing file')}: {e.stderr}",
            "form_values": form_values
        })
    except Exception as e:
        return templates.TemplateResponse(request, "timeshift.html", {
            "lang": lang,
            "translations": translations,
            "error": f"{translations.get('unexpected_error', 'Unexpected error')}: {str(e)}",
            "form_values": form_values
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
    output_file: Optional[str] = Form(None),
    provider: str = Form("local"),
    custom_instructions_file: Optional[UploadFile] = Form(None)
) -> HTMLResponse:
    lang = get_language_from_request(request)
    translations = load_translations(lang)
    
    # Get available instruction files
    instruction_files: List[Path] = []
    instruction_dir = APP_DIR / "translation_instruction_prompts"
    if instruction_dir.exists():
        instruction_files = [f for f in instruction_dir.iterdir() if f.is_file()]

    # Validate inputs
    if not srt_file:
        return templates.TemplateResponse(request, "translate.html", {
            "lang": lang,
            "translations": translations,
            "instruction_files": instruction_files,
            "error": translations.get("please_upload_srt", "Please upload an SRT file"),
            "form_values": {
                "srt_file": srt_file or "",
                "instructions_file": instructions_file or "",
                "chunk_size": chunk_size,
                "api_base": api_base,
                "model_id": model_id,
                "api_key": api_key,
                "output_file": output_file or "",
                "provider": provider
            }
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
            # Check if it's a file path or instructions text
            instruction_path = Path(instructions_file)
            if instruction_path.exists() and instruction_path.is_file():
                # It's a file path, use it directly
                pass
            else:
                # It's instructions text, create a temp file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp_inst:
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
            "instruction_files": instruction_files,
            "error": f"{translations.get('error_processing_file', 'Error processing file')}: {e.stderr}",
            "form_values": {
                "srt_file": srt_file or "",
                "instructions_file": instructions_file or "",
                "chunk_size": chunk_size,
                "api_base": api_base,
                "model_id": model_id,
                "api_key": api_key,
                "output_file": output_file or "",
                "provider": provider
            }
        })
    except Exception as e:
        return templates.TemplateResponse(request, "translate.html", {
            "lang": lang,
            "translations": translations,
            "instruction_files": instruction_files,
            "error": f"{translations.get('unexpected_error', 'Unexpected error')}: {str(e)}",
            "form_values": {
                "srt_file": srt_file or "",
                "instructions_file": instructions_file or "",
                "chunk_size": chunk_size,
                "api_base": api_base,
                "model_id": model_id,
                "api_key": api_key,
                "output_file": output_file or "",
                "provider": provider
            }
        })


def generate_translation_progress(
    srt_file: str,
    instructions_file: Optional[str],
    chunk_size: int,
    api_base: str,
    model_id: str,
    api_key: str,
    output_file: Optional[str],
    provider: str,
    custom_instructions_file: Optional[UploadFile]
) -> Generator[str, None, None]:
    """
    Generator function that runs the translation script and yields SSE-formatted progress updates.
    """
    import tempfile
    import os
    import time
    
    # Create a temporary file for the input
    tmp_input_path = None
    instruction_path = None
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as tmp_input:
            tmp_input.write(srt_file)
            tmp_input_path = tmp_input.name

        # Create a temporary instruction file if provided
        if instructions_file:
            # Check if it's a file path or instructions text
            instruction_path = Path(instructions_file)
            if instruction_path.exists() and instruction_path.is_file():
                # It's a file path, use it directly
                pass
            else:
                # It's instructions text, create a temp file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp_inst:
                    tmp_inst.write(instructions_file)
                    instruction_path = Path(tmp_inst.name)

        # Build command with progress output enabled
        cmd: List[str] = ["python3", str(TRANSLATE_SCRIPT), str(tmp_input_path)]
        if instruction_path:
            cmd.extend(["--instructions", str(instruction_path)])
        cmd.extend(["--chunk-size", str(chunk_size)])
        cmd.extend(["--api-base", api_base])
        cmd.extend(["--model-id", model_id])
        cmd.extend(["--api-key", api_key])
        cmd.append("--progress-output")  # Enable progress output
        if output_file:
            cmd.extend(["--output", output_file])

        # Start the process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        # Track state
        total_chunks = 0
        last_progress = None
        start_time = None
        output_collected = []

        try:
            while True:
                # Read from stderr (progress updates)
                stderr_line = process.stderr.readline()
                if stderr_line:
                    stderr_line = stderr_line.strip()
                    if stderr_line:
                        try:
                            progress_data = json.loads(stderr_line)
                            status = progress_data.get("status", "translating")
                            current_chunk = progress_data.get("current_chunk", 0)
                            total_chunks = progress_data.get("total_chunks", 0)
                            chunk_units = progress_data.get("chunk_units", 0)
                            elapsed_time = progress_data.get("elapsed_time", 0)
                            percent_complete = progress_data.get("percent_complete", 0)

                            # Calculate ETA
                            eta_seconds = 0
                            if status == "translating" and current_chunk > 0:
                                remaining_chunks = total_chunks - current_chunk
                                avg_time_per_chunk = elapsed_time / current_chunk
                                eta_seconds = avg_time_per_chunk * remaining_chunks

                            # Format ETA
                            if eta_seconds < 60:
                                eta_str = f"{int(eta_seconds)}s"
                            elif eta_seconds < 3600:
                                eta_str = f"{int(eta_seconds / 60)}m {int(eta_seconds % 60)}s"
                            else:
                                eta_str = f"{int(eta_seconds / 3600)}h {int((eta_seconds % 3600) / 60)}m"

                            # Yield SSE event
                            event_data = {
                                "type": "progress",
                                "status": status,
                                "current_chunk": current_chunk,
                                "total_chunks": total_chunks,
                                "chunk_units": chunk_units,
                                "elapsed_time": round(elapsed_time, 1),
                                "percent_complete": round(percent_complete, 1),
                                "eta_seconds": round(eta_seconds, 1),
                                "eta_str": eta_str
                            }
                            yield f"data: {json.dumps(event_data)}\n\n"

                        except json.JSONDecodeError:
                            # Not a progress update, ignore
                            pass

                # Check if process is done
                if process.poll() is not None:
                    break

                # Small sleep to prevent busy waiting
                time.sleep(0.1)

        finally:
            # Wait for process to complete and collect output
            stdout, stderr = process.communicate(timeout=300)
            output_collected.append(stdout)

            # Check for errors
            if process.returncode != 0:
                error_msg = stderr if stderr else "Unknown error occurred"
                error_event = {
                    "type": "error",
                    "message": error_msg
                }
                yield f"data: {json.dumps(error_event)}\n\n"
            else:
                # Success event with output
                success_event = {
                    "type": "complete",
                    "output": stdout,
                    "message": "Translation completed successfully"
                }
                yield f"data: {json.dumps(success_event)}\n\n"

        # Clean up
        if tmp_input_path and os.path.exists(tmp_input_path):
            os.unlink(tmp_input_path)
        if instruction_path and instruction_path.name.startswith('tmp') and os.path.exists(instruction_path):
            os.unlink(instruction_path)

    except Exception as e:
        error_event = {
            "type": "error",
            "message": str(e)
        }
        yield f"data: {json.dumps(error_event)}\n\n"


@app.post("/translate/stream")
async def translate_stream(
    request: Request,
    srt_file: Optional[str] = Form(None),
    instructions_file: Optional[str] = Form(None),
    chunk_size: int = Form(30),
    api_base: str = Form("http://localhost:8080"),
    model_id: str = Form("local-model"),
    api_key: str = Form("dummy-key"),
    output_file: Optional[str] = Form(None),
    provider: str = Form("local"),
    custom_instructions_file: Optional[UploadFile] = Form(None)
) -> StreamingResponse:
    """Stream translation progress via Server-Sent Events (SSE)."""
    
    # Validate inputs
    if not srt_file:
        return StreamingResponse(
            generate_error_stream("Please upload an SRT file"),
            media_type="text/event-stream"
        )

    def event_stream():
        yield from generate_translation_progress(
            srt_file=srt_file,
            instructions_file=instructions_file,
            chunk_size=chunk_size,
            api_base=api_base,
            model_id=model_id,
            api_key=api_key,
            output_file=output_file,
            provider=provider,
            custom_instructions_file=custom_instructions_file
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


def generate_error_stream(message: str) -> Generator[str, None, None]:
    """Generate an error SSE event."""
    error_event = {
        "type": "error",
        "message": message
    }
    yield f"data: {json.dumps(error_event)}\n\n"


@app.get("/translate/result", response_class=HTMLResponse)
async def translate_result_page(request: Request) -> HTMLResponse:
    """Show the translation result page (called after SSE completes)."""
    lang = get_language_from_request(request)
    translations = load_translations(lang)

    # Get available instruction files
    instruction_files: List[Path] = []
    instruction_dir = APP_DIR / "translation_instruction_prompts"
    if instruction_dir.exists():
        instruction_files = [f for f in instruction_dir.iterdir() if f.is_file()]

    return templates.TemplateResponse(request, "translate_result.html", {
        "lang": lang,
        "translations": translations,
        "instruction_files": instruction_files
    })


# ============================================================================
# Batch Translation Endpoints
# ============================================================================

@app.get("/translate-batch", response_class=HTMLResponse)
async def translate_batch_page(request: Request) -> HTMLResponse:
    """Show the batch translation page."""
    lang = get_language_from_request(request)
    translations = load_translations(lang)
    
    # Get available instruction files
    instruction_files: List[Path] = []
    instruction_dir = APP_DIR / "translation_instruction_prompts"
    if instruction_dir.exists():
        instruction_files = [f for f in instruction_dir.iterdir() if f.is_file()]

    return templates.TemplateResponse(request, "translate_batch.html", {
        "lang": lang,
        "translations": translations,
        "instruction_files": instruction_files
    })


@app.post("/translate-batch/stream")
async def translate_batch_stream(
    request: Request,
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    recursive: bool = Form(False),
    extensions: str = Form(".srt,.vtt"),
    instructions_file: Optional[str] = Form(None),
    instructions_upload: Optional[UploadFile] = Form(None),
    chunk_size: int = Form(600),
    api_base: str = Form("http://localhost:8080"),
    model_id: str = Form("local-model"),
    api_key: str = Form("dummy-key"),
    dry_run: bool = Form(False),
    files: Optional[List[UploadFile]] = Form(None)
) -> StreamingResponse:
    """Stream batch translation progress via Server-Sent Events (SSE)."""
    
    # Debug logging
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"instructions_file type: {type(instructions_file)}, value: {instructions_file[:100] if instructions_file else None}...")
    logger.debug(f"instructions_upload: {instructions_upload}")
    
    # Validate inputs
    if not files or len(files) == 0:
        return StreamingResponse(
            generate_error_stream("Please upload at least one subtitle file"),
            media_type="text/event-stream"
        )
    
    def event_stream():
        yield from generate_batch_translation_progress(
            files=files,
            source_lang=source_lang,
            target_lang=target_lang,
            recursive=recursive,
            extensions=extensions,
            instructions_file=instructions_file,
            instructions_upload=instructions_upload,
            chunk_size=chunk_size,
            api_base=api_base,
            model_id=model_id,
            api_key=api_key,
            dry_run=dry_run
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


def generate_batch_translation_progress(
    files: List[UploadFile],
    source_lang: str,
    target_lang: str,
    recursive: bool,
    extensions: str,
    instructions_file: Optional[str],
    instructions_upload: Optional[UploadFile],
    chunk_size: int,
    api_base: str,
    model_id: str,
    api_key: str,
    dry_run: bool
) -> Generator[str, None, None]:
    """
    Generator function that runs batch translation and yields SSE-formatted progress updates.
    """
    import tempfile
    import os
    import time
    import zipfile
    import errno
    
    # Parse extensions
    ext_list = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions.split(',')]
    
    tmp_dir = None
    instruction_path = None
    
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir_path = Path(tmp_dir)
            
            # Save uploaded files to temp directory
            # Group files by their relative path (if any) or put in root
            saved_files = []
            for file in files:
                if file and file.filename:
                    # Save file with original name
                    tmp_file = tmp_dir_path / file.filename
                    with open(tmp_file, 'wb') as f:
                        content = file.file.read()
                        f.write(content)
                    saved_files.append(tmp_file)
            
            # Create a temp instruction file if provided
            instruction_path = None
            
            # Priority: 1) Uploaded file, 2) Pasted text, 3) File path, 4) Default
            if instructions_upload and instructions_upload.filename:
                # Use uploaded file
                instruction_path = tmp_dir_path / "instructions.txt"
                with open(instruction_path, 'wb') as f:
                    content = instructions_upload.file.read()
                    f.write(content)
            elif instructions_file and instructions_file.strip():
                # Check if it's a file path or instructions text
                instruction_path = Path(instructions_file)
                if instruction_path.exists() and instruction_path.is_file():
                    # It's a file path, use it directly
                    pass
                else:
                    # It's instructions text, create a temp file
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp_inst:
                        tmp_inst.write(instructions_file)
                        instruction_path = Path(tmp_inst.name)
            
            if instruction_path is None:
                # Use default instruction file
                instruction_path = APP_DIR / "translation_instruction_prompts" / "subtitle_translate_-_en-es_-_default.txt"
                if not instruction_path.exists():
                    instruction_path = PROJECT_ROOT / "translation_instruction_prompts" / "subtitle_translate_-_en-es_-_default.txt"
            
            # Scan for files to translate (treating tmp_dir as the "directory")
            file_pairs, skipped_files = scan_directory(
                directory=tmp_dir_path,
                source_lang=source_lang,
                target_lang=target_lang,
                recursive=recursive,
                extensions=ext_list
            )
            
            # Yield initial progress
            initial_data = {
                "type": "initial",
                "total_files": len(file_pairs),
                "skipped_files": len(skipped_files),
                "dry_run": dry_run
            }
            yield f"data: {json.dumps(initial_data)}\n\n"
            
            # Dry run mode
            if dry_run:
                dry_run_data = {
                    "type": "dry_run_complete",
                    "files_to_translate": [
                        {"source": str(src.relative_to(tmp_dir_path)), "target": str(tgt.relative_to(tmp_dir_path))}
                        for src, tgt in file_pairs
                    ],
                    "skipped": [
                        {"source": str(src.relative_to(tmp_dir_path)), "target": str(tgt.relative_to(tmp_dir_path))}
                        for src, tgt, _ in skipped_files
                    ]
                }
                yield f"data: {json.dumps(dry_run_data)}\n\n"
                yield f"data: {json.dumps({'type': 'complete', 'message': 'Dry run complete'})}\n\n"
                return
            
            # No files to translate
            if not file_pairs:
                yield f"data: {json.dumps({'type': 'complete', 'message': 'No files need translation'})}\n\n"
                return
            
            # Set API key
            if api_key and api_key != 'dummy-key':
                os.environ['LLM_API_KEY'] = api_key
            
            start_time = time.time()
            total_episodes = len(file_pairs)
            
            # Use a thread-safe queue for real-time progress updates
            from queue import Queue, Empty
            progress_queue = Queue()
            translation_error = None
            translation_complete = False
            
            def progress_callback(
                episode_num: int,
                total_episodes: int,
                chunk_num: int,
                total_chunks: int,
                chunk_units: int,
                elapsed_time: float,
                status: str
            ):
                """Callback that puts progress updates in a thread-safe queue."""
                try:
                    # Calculate ETA
                    eta_seconds = 0
                    if status == "translating" and episode_num > 0:
                        episodes_done = episode_num - 1
                        if chunk_num > 0 and total_chunks > 0:
                            episode_progress = chunk_num / total_chunks
                            total_progress = episodes_done + episode_progress
                        else:
                            total_progress = episodes_done
                        
                        if total_progress > 0:
                            avg_time_per_episode = elapsed_time / total_progress
                            remaining_episodes = total_episodes - episode_num
                            eta_seconds = avg_time_per_episode * remaining_episodes
                    
                    # Format ETA
                    if eta_seconds < 60:
                        eta_str = f"{int(eta_seconds)}s"
                    elif eta_seconds < 3600:
                        eta_str = f"{int(eta_seconds / 60)}m"
                    else:
                        eta_str = f"{int(eta_seconds / 3600)}h"
                    
                    progress_data = {
                        "type": "progress",
                        "episode_num": episode_num,
                        "total_episodes": total_episodes,
                        "chunk_num": chunk_num,
                        "total_chunks": total_chunks,
                        "elapsed_time": round(elapsed_time, 1),
                        "eta_str": eta_str,
                        "status": status,
                        "percent_complete": round((episode_num / total_episodes) * 100, 1)
                    }
                    progress_queue.put(f"data: {json.dumps(progress_data)}\n\n")
                except Exception as e:
                    logger.error(f"Progress callback error: {e}")
            
            def run_translation():
                """Run translation in a background thread."""
                nonlocal translation_error, translation_complete
                try:
                    translate_batch(
                        file_pairs=file_pairs,
                        instructions_path=instruction_path,
                        chunk_size=chunk_size,
                        api_base=api_base,
                        model_id=model_id,
                        api_key=api_key,
                        progress_callback=progress_callback
                    )
                    translation_complete = True
                except Exception as e:
                    translation_error = e
                    translation_complete = True
            
            # Start translation in background thread
            import threading
            translation_thread = threading.Thread(target=run_translation)
            translation_thread.start()
            
            # Yield progress updates in real-time while translation runs
            while not translation_complete:
                try:
                    # Wait for progress update with timeout to check completion
                    progress_update = progress_queue.get(timeout=0.5)
                    yield progress_update
                except Empty:
                    # No update yet, continue waiting
                    continue
            
            # Yield any remaining progress updates
            while not progress_queue.empty():
                yield progress_queue.get()
            
            # Check for errors
            if translation_error:
                raise translation_error
            
            # Create ZIP file with translated files
            zip_buffer = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for source, target in file_pairs:
                    if target.exists():
                        zip_file.write(target, arcname=target.name)
            zip_buffer.close()
            
            # Yield completion with ZIP file path
            complete_data = {
                "type": "complete",
                "message": f"Batch translation complete! {len(file_pairs)} files translated.",
                "zip_file": str(zip_buffer.name)
            }
            yield f"data: {json.dumps(complete_data)}\n\n"
            
            # Clean up temp instruction file
            if instruction_path and str(instruction_path).startswith(tempfile.gettempdir()):
                if instruction_path.exists():
                    os.unlink(instruction_path)
                    
    except Exception as e:
        error_data = {
            "type": "error",
            "message": str(e)
        }
        yield f"data: {json.dumps(error_data)}\n\n"


@app.post("/translate-batch/download-zip")
async def translate_batch_download_zip(zip_file: str = Form(...)):  # type: ignore[no-untyped-def]
    """Download the translated files as a ZIP archive."""
    try:
        zip_path = Path(zip_file)
        if not zip_path.exists():
            return FileResponse(
                "",
                media_type="text/plain",
                headers={"Content-Disposition": "attachment; filename=error.txt"}
            )
        
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename="translated_subtitles.zip",
            background=lambda: zip_path.unlink(missing_ok=True) if zip_path.exists() else None
        )
    except Exception as e:
        return FileResponse(
            "",
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=error.txt"}
        )


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

    # Build form values for error recovery
    form_values = {
        "subtitle_file": subtitle_file or "",
        "input_format": input_format or "auto",
        "output_format": output_format or "",
        "preserve_formatting": preserve_formatting
    }

    # Validate inputs
    if not subtitle_file:
        return templates.TemplateResponse(request, "convert.html", {
            "lang": lang,
            "translations": translations,
            "error": translations.get("please_upload_subtitle", "Please upload a subtitle file"),
            "form_values": form_values
        })

    if not output_format:
        return templates.TemplateResponse(request, "convert.html", {
            "lang": lang,
            "translations": translations,
            "error": translations.get("please_select_output_format", "Please select an output format"),
            "form_values": form_values
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
            "error": f"{translations.get('error_processing_file', 'Error processing file')}: {e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr}",
            "form_values": form_values
        })
    except Exception as e:
        return templates.TemplateResponse(request, "convert.html", {
            "lang": lang,
            "translations": translations,
            "error": f"{translations.get('unexpected_error', 'Unexpected error')}: {str(e)}",
            "form_values": form_values
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

    # Build form values for error recovery
    form_values = {
        "srt_file": srt_file or "",
        "correct_at": correct_at or "",
        "offset_at": offset_at or "",
        "offset_seconds": str(offset_seconds) if offset_seconds is not None else "",
        "drift_rate": drift_rate or "",
        "reference_time": reference_time or ""
    }

    # Validate inputs
    if not srt_file:
        return templates.TemplateResponse(request, "autosync.html", {
            "lang": lang,
            "translations": translations,
            "error": translations.get("please_upload_srt", "Please upload an SRT file"),
            "form_values": form_values
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
                "error": translations.get("error_processing_file", "Please provide valid correction parameters"),
                "form_values": form_values
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
            "error": f"{translations.get('error_processing_file', 'Error processing file')}: {e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr}",
            "form_values": form_values
        })
    except Exception as e:
        return templates.TemplateResponse(request, "autosync.html", {
            "lang": lang,
            "translations": translations,
            "error": f"{translations.get('unexpected_error', 'Unexpected error')}: {str(e)}",
            "form_values": form_values
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
