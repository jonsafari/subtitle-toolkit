#!/usr/bin/env python3
"""
Subtitle format converter using lattifai-captions library.

This module provides functionality to convert subtitle files between different formats
including SRT, VTT, ASS, SSA, SUB, SBV, TXT, SAMI, SMI, CSV, TSV, JSON, TextGrid,
TTML, and professional NLE formats.
"""
import argparse
import sys
from pathlib import Path
from typing import Optional, List

try:
    from lattifai.caption import Caption
    from lattifai.caption.config import INPUT_CAPTION_FORMATS, OUTPUT_CAPTION_FORMATS
except ImportError as e:
    print(f"Error: lattifai-captions library not found. Install it with: pip install lattifai-captions")
    print(f"Original error: {e}")
    sys.exit(1)


def get_supported_input_formats() -> List[str]:
    """Return list of supported input formats."""
    return INPUT_CAPTION_FORMATS


def get_supported_output_formats() -> List[str]:
    """Return list of supported output formats."""
    return OUTPUT_CAPTION_FORMATS


def convert_subtitle(
    input_content: str,
    output_format: str,
    input_format: Optional[str] = None,
    preserve_formatting: bool = True,
    output_path: Optional[Path] = None
) -> bytes:
    """
    Convert subtitle content from one format to another.

    Args:
        input_content: The subtitle file content as a string
        output_format: Target output format (e.g., 'srt', 'vtt', 'ass')
        input_format: Source format (optional, will auto-detect if not provided)
        preserve_formatting: If True, preserve original text formatting.
                           If False, normalize text (remove HTML tags, collapse whitespace, etc.)
        output_path: Optional output file path. If None, returns bytes.

    Returns:
        Converted subtitle content as bytes

    Raises:
        ValueError: If input format cannot be detected or output format is invalid
        RuntimeError: If conversion fails
    """
    # Validate output format
    if output_format not in OUTPUT_CAPTION_FORMATS:
        raise ValueError(f"Unsupported output format: {output_format}. Supported formats: {OUTPUT_CAPTION_FORMATS}")

    # Determine input format
    effective_input_format = input_format
    if input_format and input_format != "auto":
        if input_format not in INPUT_CAPTION_FORMATS:
            raise ValueError(f"Unsupported input format: {input_format}. Supported formats: {INPUT_CAPTION_FORMATS}")

    # Read the caption content
    # We need to pass the content as a string, and specify the format if known
    # Note: from_string requires a specific format (not "auto")
    try:
        # If format is "auto" or None, try to detect it or default to srt
        format_to_use = effective_input_format
        if format_to_use in (None, "auto"):
            # Try to detect format from content or default to srt
            # For string content, we can't auto-detect, so default to srt
            format_to_use = "srt"

        caption = Caption.from_string(
            content=input_content,
            format=format_to_use,
            normalize_text=not preserve_formatting  # Inverse: preserve_formatting=True means normalize_text=False
        )
    except Exception as e:
        raise RuntimeError(f"Failed to parse input subtitle content: {e}")

    # Write to output format
    try:
        if output_path:
            caption.write(path=output_path, output_format=output_format)
            return Path(output_path).read_bytes()
        else:
            return caption.to_bytes(output_format=output_format)
    except Exception as e:
        raise RuntimeError(f"Failed to write output in format {output_format}: {e}")


def main():
    """CLI entry point for subtitle format conversion."""
    epilog_text = f"""
Examples:
  %(prog)s input.srt -o output.vtt
  %(prog)s input.ass -o output.srt --input-format ass
  %(prog)s input.srt -o output.sbv --preserve-formatting
  %(prog)s input.srt -o output.json
  %(prog)s --input-format srt --output-format vtt  # Read from stdin, write to stdout

Supported input formats:
  {", ".join(INPUT_CAPTION_FORMATS)}

Supported output formats:
  {", ".join(OUTPUT_CAPTION_FORMATS)}

Powered by:
  lattifai-captions (Apache-2.0 License)
  https://github.com/lattifai/captions
"""
    parser = argparse.ArgumentParser(
        description="Convert subtitle files between different formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog_text
    )

    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=None,
        help="Input subtitle file path (optional, read from stdin if not provided)"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output file path (optional, write to stdout if not provided)"
    )
    parser.add_argument(
        "--input-format",
        choices=INPUT_CAPTION_FORMATS,
        default="auto",
        help="Input format (default: auto-detect)"
    )
    parser.add_argument(
        "--output-format",
        choices=OUTPUT_CAPTION_FORMATS,
        default=None,
        help="Output format (required when reading from stdin or writing to stdout)"
    )
    parser.add_argument(
        "--preserve-formatting",
        action="store_true",
        default=True,
        help="Preserve original text formatting (default: True)"
    )
    parser.add_argument(
        "--normalize-text",
        action="store_true",
        default=False,
        help="Normalize text (remove HTML tags, collapse whitespace, etc.) - opposite of --preserve-formatting"
    )

    args = parser.parse_args()

    # Determine output format
    output_format = args.output_format
    if not output_format:
        # Infer from output file extension if provided
        if args.output:
            ext = args.output.suffix.lstrip(".").lower()
            if ext not in OUTPUT_CAPTION_FORMATS:
                print(f"Warning: Could not determine output format from extension '{ext}'. "
                      f"Please use --output-format to specify.")
                output_format = "srt"
            else:
                output_format = ext
        else:
            # No output format specified and no output file - error
            print("Error: --output-format is required when writing to stdout")
            sys.exit(1)

    # Read input content
    input_content = ""
    if args.input:
        try:
            input_content = args.input.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Error reading input file: {e}")
            sys.exit(1)
    else:
        # Read from stdin
        input_content = sys.stdin.read()

    # Convert
    try:
        result = convert_subtitle(
            input_content=input_content,
            output_format=output_format,
            input_format=args.input_format if args.input_format != "auto" else None,
            preserve_formatting=not args.normalize_text,
            output_path=args.output
        )

        # Output result
        if args.output:
            print(f"Successfully converted {args.input} to {args.output} ({output_format} format)")
            print(f"Output size: {len(result)} bytes")
        else:
            # Write to stdout as text (for web interface compatibility)
            sys.stdout.write(result.decode('utf-8'))
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
