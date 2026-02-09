#!/usr/bin/env python3
"""
FastAPI web interface for the Subtitle Toolkit
"""
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import subprocess
import os
import tempfile
from pathlib import Path
import shutil

app = FastAPI(title="Subtitle Toolkit Web Interface")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Tool paths
TIMESHIFT_SCRIPT = "./subtitle_timeshift.py"
MKV2SRT_SCRIPT = "./subtitle_mkv2srt.py"
TRANSLATE_SCRIPT = "./subtitle_translate.py"

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/timeshift", response_class=HTMLResponse)
async def timeshift_page(request: Request):
    return templates.TemplateResponse("timeshift.html", {"request": request})

@app.post("/timeshift", response_class=HTMLResponse)
async def timeshift_submit(
    request: Request,
    shift_seconds: float = Form(None),
    first_entry_starts_at: str = Form(None),
    srt_file: str = Form(None)
):
    # Validate inputs
    if not srt_file:
        return templates.TemplateResponse("timeshift.html", {
            "request": request,
            "error": "Please upload an SRT file"
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
            return templates.TemplateResponse("timeshift.html", {
                "request": request,
                "error": "Please provide either shift seconds or start time"
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

        return templates.TemplateResponse("timeshift_result.html", {
            "request": request,
            "output": result.stdout
        })

    except subprocess.CalledProcessError as e:
        return templates.TemplateResponse("timeshift.html", {
            "request": request,
            "error": f"Error processing file: {e.stderr}"
        })
    except Exception as e:
        return templates.TemplateResponse("timeshift.html", {
            "request": request,
            "error": f"Unexpected error: {str(e)}"
        })

@app.get("/mkv2srt", response_class=HTMLResponse)
async def mkv2srt_page(request: Request):
    return templates.TemplateResponse("mkv2srt.html", {"request": request})

@app.post("/mkv2srt", response_class=HTMLResponse)
async def mkv2srt_submit(
    request: Request,
    mkv_file: str = Form(None),
    language: str = Form(None),
    output_file: str = Form(None)
):
    # Validate inputs
    if not mkv_file:
        return templates.TemplateResponse("mkv2srt.html", {
            "request": request,
            "error": "Please upload an MKV file"
        })

    # Process the file
    try:
        # Create a temporary file for the input
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.mkv', delete=False) as tmp_input:
            tmp_input.write(mkv_file.encode('utf-8') if isinstance(mkv_file, str) else mkv_file)
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

        return templates.TemplateResponse("mkv2srt_result.html", {
            "request": request,
            "output": result.stdout
        })

    except subprocess.CalledProcessError as e:
        return templates.TemplateResponse("mkv2srt.html", {
            "request": request,
            "error": f"Error processing file: {e.stderr}"
        })
    except Exception as e:
        return templates.TemplateResponse("mkv2srt.html", {
            "request": request,
            "error": f"Unexpected error: {str(e)}"
        })

@app.get("/translate", response_class=HTMLResponse)
async def translate_page(request: Request):
    # Get available instruction files
    instruction_files = []
    instruction_dir = Path("translation_instruction_prompts")
    if instruction_dir.exists():
        instruction_files = [f for f in instruction_dir.iterdir() if f.is_file()]

    return templates.TemplateResponse("translate.html", {
        "request": request,
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
    api_key: str = Form("dummy-key")
):
    # Validate inputs
    if not srt_file:
        return templates.TemplateResponse("translate.html", {
            "request": request,
            "error": "Please upload an SRT file"
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

        return templates.TemplateResponse("translate_result.html", {
            "request": request,
            "output": result.stdout
        })

    except subprocess.CalledProcessError as e:
        return templates.TemplateResponse("translate.html", {
            "request": request,
            "error": f"Error processing file: {e.stderr}"
        })
    except Exception as e:
        return templates.TemplateResponse("translate.html", {
            "request": request,
            "error": f"Unexpected error: {str(e)}"
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
