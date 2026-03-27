#!/usr/bin/env python3
"""
Batch translation module for translating multiple subtitle files in a directory.

This module scans a directory for subtitle files matching a source language pattern,
checks if corresponding target language files exist, and translates only the missing ones.

Public API:
    - scan_directory: Scan directory for subtitle files needing translation
    - translate_batch: Translate a list of (source, target) file pairs
    - format_time: Format elapsed time as human-readable string
"""
import argparse
import os
import sys
import json
import time
import zipfile
from pathlib import Path
from typing import List, Tuple, Optional, Callable
from tqdm import tqdm

# Import from translate module
try:
    from translate import translate_file
except ImportError:
    from .translate import translate_file

__all__ = [
    "scan_directory",
    "translate_batch",
    "format_time",
]


def format_time(seconds: float) -> str:
    """
    Format elapsed time as human-readable string.
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted time string (e.g., "2h 15m 30s", "45m 12s", "30s")
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if minutes > 0:
            return f"{hours}h {minutes}m {secs}s"
        return f"{hours}h {minutes}m"


def scan_directory(
    directory: Path,
    source_lang: str,
    target_lang: str,
    recursive: bool = False,
    extensions: List[str] = None
) -> List[Tuple[Path, Path]]:
    """
    Scan directory for subtitle files that need translation.
    
    Looks for files matching pattern: <basename>.<source_lang>.<ext>
    and checks if corresponding <basename>.<target_lang>.<ext> exists.
    
    Args:
        directory: Path to directory to scan
        source_lang: Source language code (e.g., 'en', 'pt-BR')
        target_lang: Target language code (e.g., 'es', 'fr')
        recursive: If True, scan subdirectories recursively
        extensions: List of file extensions to match (default: ['.srt', '.vtt'])
        
    Returns:
        List of (source_file, target_file) tuples for files that need translation
        (i.e., source exists but target does not)
    """
    if extensions is None:
        extensions = ['.srt', '.vtt']
    
    if not directory.is_dir():
        sys.exit(f"Directory does not exist: {directory}")
    
    file_pairs = []
    skipped_files = []
    
    # Determine glob pattern
    if recursive:
        glob_pattern = '**/*'
    else:
        glob_pattern = '*'
    
    # Scan for source files
    for source_file in directory.glob(glob_pattern):
        if not source_file.is_file():
            continue
        
        # Check if file matches source language pattern
        # Pattern: <basename>.<source_lang>.<ext>
        suffix = source_file.suffix  # e.g., '.srt'
        if suffix.lower() not in [e.lower() for e in extensions]:
            continue
        
        # Get the part before the extension
        name_without_ext = source_file.stem  # e.g., 'show_S03E01.en'
        
        # Check if it ends with .<source_lang>
        lang_pattern = f'.{source_lang}'
        if not name_without_ext.endswith(lang_pattern):
            continue
        
        # Extract basename (without language tag)
        basename = name_without_ext[:-len(lang_pattern)]  # e.g., 'show_S03E01'
        
        # Construct target filename
        target_name = f"{basename}.{target_lang}{suffix}"
        target_file = source_file.parent / target_name
        
        # Check if target already exists
        if target_file.exists():
            skipped_files.append((source_file, target_file, "already exists"))
        else:
            file_pairs.append((source_file, target_file))
    
    return file_pairs, skipped_files


def translate_batch(
    file_pairs: List[Tuple[Path, Path]],
    instructions_path: Path,
    chunk_size: int,
    api_base: str,
    model_id: str,
    api_key: str,
    progress_callback: Optional[Callable] = None
) -> None:
    """
    Translate a list of (source, target) file pairs.
    
    Stops on first error.
    
    Args:
        file_pairs: List of (source_file, target_file) tuples
        instructions_path: Path to instructions file
        chunk_size: Number of units per chunk
        api_base: LLM API base URL
        model_id: LLM model ID
        api_key: LLM API key
        progress_callback: Optional callback(episode_num, total_episodes, 
                          chunk_num, total_chunks, chunk_units, elapsed_time, status)
                          
    Raises:
        SystemExit: On file I/O errors
        Exception: On API errors (stops immediately)
    """
    if not file_pairs:
        print("No files to translate.")
        return
    
    total_episodes = len(file_pairs)
    start_time = time.time()
    
    # Progress bar for episodes
    episode_iter = enumerate(file_pairs, start=1)
    if progress_callback:
        episode_iter = enumerate(file_pairs, start=1)  # No tqdm with callback
    else:
        episode_iter = enumerate(tqdm(file_pairs, desc="Episodes", total=total_episodes), start=1)
    
    for episode_num, (source_file, target_file) in episode_iter:
        elapsed_time = time.time() - start_time
        
        if not progress_callback:
            print(f"\nEpisode {episode_num}/{total_episodes}: {source_file.name}")
            print(f"  → {target_file.name}")
        
        # Track per-episode progress
        episode_start_time = time.time()
        total_chunks = 0
        current_chunk = 0
        
        def chunk_progress_callback(
            chunk_num: int,
            total_chunks_val: int,
            chunk_units: int,
            chunk_elapsed: float,
            status: str
        ):
            """Callback for chunk-level progress within an episode."""
            nonlocal total_chunks, current_chunk
            
            if total_chunks_val > 0 and total_chunks == 0:
                total_chunks = total_chunks_val
                current_chunk = chunk_num
            
            current_chunk = chunk_num
            
            if progress_callback:
                total_elapsed = time.time() - start_time
                progress_callback(
                    episode_num=episode_num,
                    total_episodes=total_episodes,
                    chunk_num=chunk_num,
                    total_chunks=total_chunks,
                    chunk_units=chunk_units,
                    elapsed_time=total_elapsed,
                    status=status
                )
        
        try:
            translate_file(
                source_path=source_file,
                target_path=target_file,
                instructions_path=instructions_path,
                chunk_size=chunk_size,
                api_base=api_base,
                model_id=model_id,
                api_key=api_key,
                progress_callback=chunk_progress_callback
            )
            
            episode_elapsed = time.time() - episode_start_time
            if not progress_callback:
                print(f"  ✓ Completed in {format_time(episode_elapsed)}")
                
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"\n{'='*60}")
            print(f"ERROR: Translation failed at episode {episode_num}/{total_episodes}")
            print(f"  File: {source_file}")
            print(f"  Error: {e}")
            print(f"\nSuccessfully translated {episode_num - 1} episodes before failure.")
            print(f"Partially translated files are in the output directory.")
            print(f"{'='*60}")
            raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch translate subtitle files in a directory using an AI model. "
                    "Only translates files that don't already have a target language version."
    )
    parser.add_argument(
        'directory',
        type=Path,
        help='Path to directory containing subtitle files'
    )
    parser.add_argument(
        '--source-lang',
        type=str,
        required=True,
        help='Source language code (e.g., en, pt-BR, eng)'
    )
    parser.add_argument(
        '--target-lang',
        type=str,
        required=True,
        help='Target language code (e.g., es, fr, deu)'
    )
    parser.add_argument(
        '--recursive',
        action='store_true',
        help='Scan subdirectories recursively'
    )
    parser.add_argument(
        '--extensions',
        type=str,
        default='.srt,.vtt',
        help='Comma-separated list of file extensions to match (default: .srt,.vtt)'
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
        default=600,
        help='Number of subtitle units per chunk. Default: %(default)s'
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
        '--output-dir',
        type=Path,
        default=None,
        help='Output directory (default: same as input, mirroring structure)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be translated without actually translating'
    )
    parser.add_argument(
        '--progress-output',
        type=str,
        default=None,
        help='Output progress updates as JSON to stderr (for web interface). Default: %(default)s'
    )

    args = parser.parse_args()

    # Parse extensions
    extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in args.extensions.split(',')]
    
    # Validate instructions file
    if not args.instructions.is_file():
        sys.exit(f"Instructions file does not exist: {args.instructions}")
    
    # Scan directory
    print(f"Batch Translation: {args.directory}")
    print(f"Source: {args.source_lang} → Target: {args.target_lang}")
    print(f"{'Recursive: Yes' if args.recursive else 'Recursive: No'}")
    print(f"Extensions: {', '.join(extensions)}")
    print("=" * 60)
    
    print("\nScanning directory...")
    file_pairs, skipped_files = scan_directory(
        directory=args.directory,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        recursive=args.recursive,
        extensions=extensions
    )
    
    # Report scan results
    print(f"Found {len(file_pairs) + len(skipped_files)} subtitle files matching pattern *.{args.source_lang}.*")
    if skipped_files:
        print(f"  - {len(skipped_files)} already translated (skipping)")
    if file_pairs:
        print(f"  - {len(file_pairs)} need translation")
    
    # Dry run mode
    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN MODE - No translation will be performed")
        print("=" * 60)
        
        if file_pairs:
            print(f"\nFiles that would be translated ({len(file_pairs)}):")
            for i, (source, target) in enumerate(file_pairs, 1):
                rel_source = source.relative_to(args.directory)
                rel_target = target.relative_to(args.directory)
                print(f"  {i}. {rel_source} → {rel_target}")
        else:
            print("\nNo files need translation.")
        
        if skipped_files:
            print(f"\nFiles skipped ({len(skipped_files)}):")
            for source, target, reason in skipped_files:
                rel_source = source.relative_to(args.directory)
                rel_target = target.relative_to(args.directory)
                print(f"  - {rel_source} ({rel_target} {reason})")
        
        print("\n" + "=" * 60)
        return
    
    # No files to translate
    if not file_pairs:
        print("\nNo files need translation. Exiting.")
        return
    
    # Set API key if provided
    if args.api_key and args.api_key != 'dummy-key':
        os.environ['LLM_API_KEY'] = args.api_key
    
    # Adjust target paths if output directory is specified
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        adjusted_pairs = []
        for source, target in file_pairs:
            # Mirror directory structure
            rel_path = source.relative_to(args.directory)
            new_target = args.output_dir / rel_path.parent / target.name
            new_target.parent.mkdir(parents=True, exist_ok=True)
            adjusted_pairs.append((source, new_target))
        file_pairs = adjusted_pairs
    
    # Progress callback for JSON output
    def json_progress_callback(
        episode_num: int,
        total_episodes: int,
        chunk_num: int,
        total_chunks: int,
        chunk_units: int,
        elapsed_time: float,
        status: str
    ):
        """Emit progress as JSON to stderr."""
        if args.progress_output:
            # Calculate ETA
            eta_seconds = 0
            if status == "translating" and episode_num > 0 and total_episodes > 0:
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
                eta_str = f"{int(eta_seconds / 60)}m {int(eta_seconds % 60)}s"
            else:
                eta_str = f"{int(eta_seconds / 3600)}h {int((eta_seconds % 3600) / 60)}m"
            
            progress_data = {
                "type": "batch_progress",
                "episode_num": episode_num,
                "total_episodes": total_episodes,
                "chunk_num": chunk_num,
                "total_chunks": total_chunks,
                "chunk_units": chunk_units,
                "elapsed_time": round(elapsed_time, 1),
                "eta_seconds": round(eta_seconds, 1),
                "eta_str": eta_str,
                "status": status,
                "percent_complete": round((episode_num / total_episodes) * 100, 1) if total_episodes > 0 else 0
            }
            print(json.dumps(progress_data), file=sys.stderr, flush=True)
    
    # Translate
    print("\n" + "=" * 60)
    print("Translation Progress")
    print("=" * 60 + "\n")
    
    try:
        translate_batch(
            file_pairs=file_pairs,
            instructions_path=args.instructions,
            chunk_size=args.chunk_size,
            api_base=args.api_base,
            model_id=args.model_id,
            api_key=args.api_key,
            progress_callback=json_progress_callback if args.progress_output else None
        )
        
        total_elapsed = time.time() - time.time()
        print("\n" + "=" * 60)
        print(f"Batch translation complete! {len(file_pairs)} episodes translated.")
        print("=" * 60)
        
    except Exception as e:
        sys.exit(1)


if __name__ == "__main__":
    main()
