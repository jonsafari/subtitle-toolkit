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
AVAILABLE_LANGUAGES = ["en", "es", "de", "fr"]
DEFAULT_LANGUAGE = "en"

def load_translations(language: str) -> dict:
    """Load translations for a specific language."""
    translation_file = TRANSLATIONS_DIR / f"{language}.json"
    if translation_file.exists():
        with open(translation_file, "r", encoding="utf-8") as f:
            return json.load(f)
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
async def favicon():
    return FileResponse(PROJECT_ROOT / "static" / "favicon.ico")

# Tool paths (relative to project root)
TIMESHIFT_SCRIPT = PROJECT_ROOT / "src/timeshift.py"
MKV2SRT_SCRIPT = PROJECT_ROOT / "src/mkv2srt.py"
TRANSLATE_SCRIPT = PROJECT_ROOT / "src/translate.py"

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    lang = get_language_from_request(request)
    return templates.TemplateResponse(request, "index.html", {
        "lang": lang,
        "translations": load_translations(lang)
    })

@app.get("/timeshift", response_class=HTMLResponse)
async def timeshift_page(request: Request):
    lang = get_language_from_request(request)
    return templates.TemplateResponse(request, "timeshift.html", {
        "lang": lang,
        "translations": load_translations(lang)
    })

@app.post("/timeshift", response_class=HTMLResponse)
async def timeshift_submit(
    request: Request,
    shift_seconds: float = Form(None),
    first_entry_starts_at: str = Form(None),
    srt_file: str = Form(None)
):
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
        cmd = ["python3", TIMESHIFT_SCRIPT]
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

@app.post("/timeshift/download", response_class=HTMLResponse)
async def timeshift_download(request: Request, output: str = Form(None)):
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
async def mkv2srt_page(request: Request):
    lang = get_language_from_request(request)
    return templates.TemplateResponse(request, "mkv2srt.html", {
        "lang": lang,
        "translations": load_translations(lang)
    })

@app.post("/mkv2srt", response_class=HTMLResponse)
async def mkv2srt_submit(
    request: Request,
    mkv_file: UploadFile = Form(None),
    language: str = Form(None),
    output_file: str = Form(None)
):
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
        cmd = ["python3", MKV2SRT_SCRIPT, "--input", tmp_input_path]
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
async def translate_page(request: Request):
    lang = get_language_from_request(request)
    # Get available instruction files (relative to app.py location)
    instruction_files = []
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
    srt_file: str = Form(None),
    instructions_file: str = Form(None),
    chunk_size: int = Form(30),
    api_base: str = Form("http://localhost:8080"),
    model_id: str = Form("local-model"),
    api_key: str = Form("dummy-key"),
    output_file: str = Form(None)
):
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
        cmd = ["python3", TRANSLATE_SCRIPT, tmp_input_path]
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

@app.post("/set-language")
async def set_language(request: Request, lang: str = Form(...)):
    """Set the language preference."""
    if lang not in AVAILABLE_LANGUAGES:
        lang = DEFAULT_LANGUAGE
    
    response = RedirectResponse(url=request.headers.get("referer", "/"), status_code=303)
    response.set_cookie("language", lang, max_age=30*24*60*60)  # 30 days
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)