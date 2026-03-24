#!/usr/bin/env python3
"""
Translate module for translating subtitle files using AI models.

Public API:
    - detect_line_ending: Detect line ending style in text
    - read_file: Read a file with UTF-8 encoding
    - write_file: Write content to a file with UTF-8 encoding
    - split_into_units: Split SRT content into subtitle units
    - chunk_units: Group units into chunks for batch processing
"""
import argparse
import os
import sys
import json
import time
from pathlib import Path
from typing import List, Optional
from tqdm import tqdm
import litellm

__all__ = [
    "detect_line_ending",
    "read_file",
    "write_file",
    "split_into_units",
    "chunk_units",
]


def detect_line_ending(text: str) -> str:
    """
    Detect the line‑ending style used in *text*.
    Returns '\r\n' if CRLF is found, otherwise '\n'.
    """
    return '\r\n' if '\r\n' in text else '\n'


def read_file(path: Path) -> str:
    """
    Read a file in binary mode and decode as UTF‑8.
    """
    try:
        with path.open('rb') as f:
            return f.read().decode('utf-8')
    except Exception as e:
        sys.exit(f"Error reading {path}: {e}")


def write_file(path: Path, content: str) -> None:
    """
    Write *content* to *path* using UTF‑8 encoding.
    Creates parent directories if they don't exist.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8', newline='') as f:
            f.write(content)
    except Exception as e:
        sys.exit(f"Error writing {path}: {e}")


def split_into_units(text: str, line_ending: str) -> List[str]:
    """
    Split the subtitle file into units.
    A unit is the block of text that ends with an empty line.
    """
    separator = line_ending * 2
    units = text.split(separator)
    # Remove any stray empty strings that may appear at the end
    units = [u for u in units if u.strip() != '']
    return units


def chunk_units(units: List[str], chunk_size: int) -> List[List[str]]:
    """
    Group the list of units into chunks of *chunk_size* units.
    """
    return [units[i:i + chunk_size] for i in range(0, len(units), chunk_size)]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Translate subtitle units from an SRT file using an AI model. "
    )
    parser.add_argument(
        'input_file',
        type=Path,
        help='Path to the input .srt file.'
    )
    parser.add_argument(
        '--instructions',
        type=Path,
        default=Path('translation_instruction_prompts/subtitle_translate_-_en-es_-_default.txt'),
        help='Path to the instructions file. Default: %(default)s'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=30,
        help='Number of subtitle units per chunk. Default: %(default)s'
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Output file path. Default: derived from input filename, e.g., input_translated.srt'
    )
    parser.add_argument(
        '--api-base',
        type=str,
        default='http://localhost:8080',
        help='LLM base URL. Default: %(default)s'
    )
    parser.add_argument(
        '--model-id',
        type=str,
        default='local-model',
        help='LLM model ID (use LiteLLM formatting). Default: %(default)s'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        default='dummy-key',
        help='LLM API key. Default: %(default)s'
    )
    parser.add_argument(
        '--progress-output',
        type=str,
        default=None,
        help='Output progress updates as JSON to stderr (for web interface). Default: %(default)s'
    )

    args = parser.parse_args()

    # Set API key if provided (otherwise litellm uses environment variables)
    if args.api_key and args.api_key != 'dummy-key':
        os.environ['LLM_API_KEY'] = args.api_key

    # Validate input paths
    if not args.input_file.is_file():
        sys.exit(f"Input file does not exist: {args.input_file}")
    if not args.instructions.is_file():
        sys.exit(f"Instructions file does not exist: {args.instructions}")

    # Determine output file path
    if args.output:
        output_path = args.output
    else:
        # Derive output filename from input filename
        input_path = Path(args.input_file)
        stem = input_path.stem  # filename without extension
        output_path = input_path.parent / f"{stem}_translated.srt"

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)



    # Read files
    srt_text = read_file(args.input_file)
    instructions_text = read_file(args.instructions)

    # Detect line ending style from the input file
    line_ending = detect_line_ending(srt_text)

    # Split into units
    units = split_into_units(srt_text, line_ending)

    # Chunk the units
    chunks = chunk_units(units, args.chunk_size)

    separator = line_ending * 2

    # Helper function to emit progress updates
    def emit_progress(current_chunk: int, total_chunks: int, chunk_units: int, elapsed_time: float, status: str = "translating"):
        """Emit progress update as JSON to stderr if progress output is enabled."""
        if args.progress_output:
            progress_data = {
                "current_chunk": current_chunk,
                "total_chunks": total_chunks,
                "chunk_units": chunk_units,
                "elapsed_time": elapsed_time,
                "status": status,
                "percent_complete": (current_chunk / total_chunks) * 100 if total_chunks > 0 else 0
            }
            # Write to stderr as JSON line
            print(json.dumps(progress_data), file=sys.stderr, flush=True)

    # Translate each chunk and write to output file incrementally
    # Truncate output file if it exists
    with open(output_path, 'w', encoding='utf-8') as f:
        pass  # This truncates the file

    # Emit start progress
    emit_progress(0, len(chunks), 0, 0, "starting")

    start_time = time.time()

    # Use tqdm only if not outputting progress (to avoid mixing output)
    chunk_iter = enumerate(chunks, start=1)
    if args.progress_output:
        chunk_iter = enumerate(chunks, start=1)  # No tqdm when outputting progress
    else:
        chunk_iter = enumerate(tqdm(chunks, desc="Translating chunks"), start=1)

    for idx, chunk in chunk_iter:
        chunk_start_time = time.time()
        source_text_chunk = separator.join(chunk) + line_ending

        response = litellm.completion(
            model=args.model_id,
            messages=[
                {"role": "system", "content": instructions_text.rstrip()},
                {"role": "user", "content": source_text_chunk},
            ],
            reasoning_effort="low",
            api_base=args.api_base if args.api_base else None,
        )

        translation = response.choices[0].message.content + separator

        # Write translation directly to output file
        with open(output_path, 'a', encoding='utf-8') as f:
            f.write(translation)

        elapsed_time = time.time() - start_time
        emit_progress(idx, len(chunks), len(chunk), elapsed_time, "translating")

        if not args.progress_output:
            print(f"Translated chunk {idx}/{len(chunks)} ({len(chunk)} units)")

    elapsed_time = time.time() - start_time
    emit_progress(len(chunks), len(chunks), 0, elapsed_time, "completed")

    print(f"\nFinished! Translated {len(chunks)} chunks written to {output_path.resolve()}")


if __name__ == "__main__":
    main()
