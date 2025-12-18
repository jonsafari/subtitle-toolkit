#!/usr/bin/env python3
"""
split_srt.py

Splits a large .srt file into smaller chunks of subtitle units.
Each chunk is written to /tmp/ (or a user‑supplied directory) and
is prefixed with the contents of subtitle_translate.txt.

Usage:
    python split_srt.py input.srt
    python split_srt.py input.srt --instructions my_instructions.txt
    python split_srt.py input.srt --chunk-size 30 --output-dir /tmp/chunks
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List
from openai import OpenAI


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
    """
    try:
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
        description="Split a large .srt file into smaller chunks subtitle units and translate them. "
    )
    parser.add_argument(
        'input_file',
        type=Path,
        help='Path to the input .srt file.'
    )
    parser.add_argument(
        '--instructions',
        type=Path,
        default=Path('subtitle_translate.txt'),
        help='Path to the instructions file (default: subtitle_translate.txt).'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=30,
        help='Number of subtitle units per chunk (default: 30).'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('/tmp/'),
        help='Directory where the chunk files will be written (default: /tmp/).'
    )
    parser.add_argument(
        '--api-base',
        type=str,
        default='http://localhost:8080',
        help='OpenAI-API base URL. (default: http://localhost:8080)'
    )
    parser.add_argument(
        '--model-id',
        type=str,
        default='local-model',
        help='OpenAI-API model ID (default: local-model)'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        default='dummy-key',
        help='OpenAI-API key. (default: dummy-key)'
    )

    args = parser.parse_args()

    # Validate input paths
    if not args.input_file.is_file():
        sys.exit(f"Input file does not exist: {args.input_file}")
    if not args.instructions.is_file():
        sys.exit(f"Instructions file does not exist: {args.instructions}")

    # Ensure output directory exists
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Connect to OpenAI-API endpoing
    client = OpenAI(
        base_url=args.api_base, # + '/v1/',
        api_key=args.api_key,
    )

    # Read files
    srt_text = read_file(args.input_file)
    instructions_text = read_file(args.instructions)

    # Detect line ending style from the input file
    line_ending = detect_line_ending(srt_text)

    # Split into units
    units = split_into_units(srt_text, line_ending)

    # Chunk the units
    chunks = chunk_units(units, args.chunk_size)

    digits = len(str(len(chunks)))

    separator = line_ending * 2

    # Translate each chunk and write to disk
    for idx, chunk in enumerate(chunks, start=1):
        chunk_path = args.output_dir / f"chunk_{idx:0{digits}d}.srt"
        source_text_chunk = separator.join(chunk) + line_ending
        #print(f'Input chunk:\n{source_text_chunk}')

        chat_completion = client.chat.completions.create(
            model=args.model_id,
            messages=[
                #{"role": "system", "content": "You are a helpful assistant."},
                #{"role": "user", "content": 'What is the capital of Bolivia? Be brief.'},
                {"role": "system", "content": instructions_text.rstrip()},
                {"role": "user", "content": source_text_chunk},
            ],
            #stream=True,
            #max_tokens=100
        )



        translation = chat_completion.choices[0].message.content + separator
        #print(f'Output translation:\n{translation}')

        # Build the content: instructions + two line endings + joined units
        # We use the same line ending style as the original file
        #chunk_content = instructions_text.rstrip() + separator + separator.join(chunk) + line_ending

        write_file(chunk_path, translation)

        print(f"Wrote chunk {idx}/{len(chunks)} ({len(chunk)} units) to {chunk_path}")

    print(f"\nFinished writing {len(chunks)} chunks in {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
