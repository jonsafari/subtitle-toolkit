#!/usr/bin/env python3
"""
Autosync module for drift correction in subtitle timestamps.

This module provides linear drift correction for subtitles that are out of sync
due to frame rate differences or other timing issues. Unlike simple time-shifting,
drift correction applies a time-varying offset that increases/decreases across
the video duration.

Public API:
    - apply_drift_correction: Apply drift correction to SRT content
    - DriftConfig: Configuration for drift correction
    - parse_time: Parse time strings to milliseconds
    - format_time: Format milliseconds to SRT timestamp
"""
import sys
import re
import argparse
from dataclasses import dataclass
from typing import List, Tuple, Optional
from pathlib import Path

__all__ = ["apply_drift_correction", "DriftConfig", "parse_time", "format_time"]


# Common frame rate conversion drift rates (offset per second)
COMMON_DRIFT_RATES = {
    "23.976_to_24": 0.00100167,      # ~4.5 seconds per hour
    "24_to_23.976": -0.00100167,
    "29.97_to_30": 0.00100167,       # ~6 seconds per hour
    "30_to_29.97": -0.00100167,
    "25_to_23.976": -0.042,          # ~2.5 minutes per hour
    "23.976_to_25": 0.042,
}


@dataclass
class DriftConfig:
    """Configuration for drift correction.
    
    Attributes:
        reference_time: Time in ms where we know the offset is correct (or zero)
        offset_time: Time in ms where we know the offset value
        offset_at_offset_time: Offset in ms at offset_time (positive = subtitles late)
        sync_points: Optional list of (time_ms, offset_ms) tuples for multi-point correction
    """
    reference_time: float
    offset_time: float
    offset_at_offset_time: float
    sync_points: Optional[List[Tuple[float, float]]] = None
    
    @property
    def drift_rate(self) -> float:
        """Calculate the drift rate (offset per millisecond)."""
        if self.sync_points:
            # For multi-point, return the overall rate
            first = self.sync_points[0]
            last = self.sync_points[-1]
            return (last[1] - first[1]) / (last[0] - first[0])
        
        return self.offset_at_offset_time / (self.offset_time - self.reference_time)
    
    def get_offset_at_time(self, time_ms: float) -> float:
        """Get the offset (in ms) that should be applied at a given time.
        
        Args:
            time_ms: Time in milliseconds
            
        Returns:
            Offset in milliseconds to add to the timestamp
        """
        if self.sync_points and len(self.sync_points) >= 2:
            # Multi-point piecewise linear interpolation
            return self._get_offset_multi_point(time_ms)
        else:
            # Simple two-point linear drift
            return self._get_offset_two_point(time_ms)
    
    def _get_offset_two_point(self, time_ms: float) -> float:
        """Calculate offset using two-point linear drift."""
        drift_rate = self.drift_rate
        # Offset at any time = drift_rate * (time - reference_time)
        return drift_rate * (time_ms - self.reference_time)
    
    def _get_offset_multi_point(self, time_ms: float) -> float:
        """Calculate offset using piecewise linear interpolation."""
        # Sort sync points by time
        sorted_points = sorted(self.sync_points, key=lambda x: x[0])
        
        # Find the segment containing this time
        for i in range(len(sorted_points) - 1):
            t1, o1 = sorted_points[i]
            t2, o2 = sorted_points[i + 1]
            if t1 <= time_ms < t2:
                # Linear interpolation within segment
                ratio = (time_ms - t1) / (t2 - t1)
                return o1 + ratio * (o2 - o1)
        
        # Extrapolate before first or after last point
        if time_ms < sorted_points[0][0]:
            # Use first point's offset (constant extrapolation)
            return sorted_points[0][1]
        else:
            # Use last segment's drift rate
            t1, o1 = sorted_points[-2]
            t2, o2 = sorted_points[-1]
            drift_rate = (o2 - o1) / (t2 - t1)
            return o1 + drift_rate * (time_ms - t1)


def parse_time(time_str: str) -> float:
    """Parse a time string to milliseconds.
    
    Supports formats:
    - HH:MM:SS,mmm (SRT format with comma)
    - HH:MM:SS.mmm (SRT format with period)
    - HH:MM:SS (no milliseconds)
    - MM:SS,mmm (short format)
    - MM:SS.mmm (short format)
    - MM:SS (short format, no milliseconds)
    - Seconds (just a number)
    
    Args:
        time_str: Time string in various formats
        
    Returns:
        Time in milliseconds as float
        
    Raises:
        ValueError: If the time string cannot be parsed
    """
    time_str = time_str.strip()
    
    # Handle plain seconds (e.g., "30" or "30.5")
    if re.match(r'^-?\d+\.?\d*$', time_str):
        return float(time_str) * 1000
    
    # Normalize separator (comma or period for milliseconds)
    # Split on the last colon to separate hours from rest
    parts = time_str.replace(',', '.').split(':')
    
    if len(parts) == 1:
        # Just seconds
        return float(parts[0]) * 1000
    elif len(parts) == 2:
        # MM:SS.mmm
        minutes, seconds = parts
        return (float(minutes) * 60 + float(seconds)) * 1000
    elif len(parts) == 3:
        # HH:MM:SS.mmm
        hours, minutes, seconds = parts
        return (float(hours) * 3600 + float(minutes) * 60 + float(seconds)) * 1000
    else:
        raise ValueError(f"Cannot parse time string: {time_str}")


def format_time(ms: float) -> str:
    """Format milliseconds to SRT timestamp format (HH:MM:SS,mmm).
    
    Args:
        ms: Time in milliseconds
        
    Returns:
        Formatted timestamp string
    """
    # Ensure non-negative
    ms = max(0, ms)
    
    total_seconds = ms / 1000
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    
    # Extract milliseconds (3 digits)
    milliseconds = int((ms % 1000))
    
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace('.', ',')


def parse_srt_line(line: str) -> Optional[Tuple[str, str]]:
    """Parse a timestamp line from SRT format.
    
    Args:
        line: A line containing timestamps (e.g., "00:00:01,000 --> 00:00:03,500")
        
    Returns:
        Tuple of (start_time_str, end_time_str) or None if not a timestamp line
    """
    if '-->' not in line:
        return None
    
    try:
        # Split on -->
        parts = line.split('-->')
        if len(parts) != 2:
            return None
        
        start = parts[0].strip()
        end = parts[1].strip()
        
        # Validate that we got valid times
        parse_time(start)  # Will raise if invalid
        parse_time(end)
        
        return (start, end)
    except (ValueError, IndexError):
        return None


def apply_drift_correction(
    srt_content: str,
    config: DriftConfig,
    clamp_to_zero: bool = True,
    preserve_line_endings: bool = True
) -> str:
    """Apply drift correction to SRT subtitle content.
    
    Args:
        srt_content: The SRT file content as a string
        config: DriftConfig specifying the correction parameters
        clamp_to_zero: If True, clamp negative timestamps to 00:00:00,000
        preserve_line_endings: If True, preserve original line endings (\r\n vs \n)
        
    Returns:
        Corrected SRT content as a string
    """
    # Detect line ending
    if preserve_line_endings:
        if '\r\n' in srt_content:
            line_ending = '\r\n'
        else:
            line_ending = '\n'
    else:
        line_ending = '\n'
    
    lines = srt_content.splitlines()
    result_lines = []
    
    for line in lines:
        parsed = parse_srt_line(line)
        
        if parsed:
            start_str, end_str = parsed
            
            # Convert to milliseconds
            start_ms = parse_time(start_str)
            end_ms = parse_time(end_str)
            
            # Calculate offsets at start and end times
            offset_start = config.get_offset_at_time(start_ms)
            offset_end = config.get_offset_at_time(end_ms)
            
            # Apply offsets
            new_start_ms = start_ms + offset_start
            new_end_ms = end_ms + offset_end
            
            # Clamp to zero if needed
            if clamp_to_zero:
                new_start_ms = max(0, new_start_ms)
                new_end_ms = max(0, new_end_ms)
            
            # Ensure start <= end (in case of extreme drift)
            if new_start_ms > new_end_ms:
                # Clamp start to end
                new_start_ms = new_end_ms
            
            # Format back to SRT timestamp
            new_start_str = format_time(new_start_ms)
            new_end_str = format_time(new_end_ms)
            
            result_lines.append(f"{new_start_str} --> {new_end_str}")
        else:
            # Non-timestamp line, pass through unchanged
            result_lines.append(line)
    
    return line_ending.join(result_lines) + line_ending


def validate_sync_points(
    reference_time: float,
    offset_time: float,
    sync_points: Optional[List[Tuple[float, float]]]
) -> List[str]:
    """Validate sync point configuration.
    
    Args:
        reference_time: Reference time in ms
        offset_time: Offset time in ms
        sync_points: Optional list of sync points
        
    Returns:
        List of warning messages (empty if valid)
    """
    warnings = []
    
    if sync_points:
        if len(sync_points) < 2:
            warnings.append("Need at least 2 sync points for multi-point correction")
        
        # Check for duplicate times
        times = [p[0] for p in sync_points]
        if len(times) != len(set(times)):
            warnings.append("Duplicate times in sync points")
        
        # Check ordering
        sorted_times = sorted(times)
        if times != sorted_times:
            warnings.append("Sync points are not in time order (will be sorted automatically)")
    
    return warnings


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            """
            Apply drift correction to SRT subtitles.
            
            Unlike simple time-shifting, drift correction handles cases where
            subtitles gradually drift out of sync over time (e.g., due to
            frame rate differences between video and subtitle).
            
            Examples:
              # Two-point correction: subtitles correct at 0:30, 5 seconds late at 10:00
              cat input.srt | subtitle-tk autosync --correct-at 00:00:30 --offset-at 00:10:00 --offset 5.0
              
              # Multiple sync points
              cat input.srt | subtitle-tk autosync --point 00:00:30:0 --point 00:05:00:2.5 --point 00:10:00:5.0
              
              # Using common frame rate drift
              cat input.srt | subtitle-tk autosync --drift-rate 23.976_to_24 --reference 00:00:00
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--correct-at", "-c",
        type=str,
        help="Time where subtitles are correct (no offset). Format: HH:MM:SS[,.mmm]"
    )
    mode_group.add_argument(
        "--points", "-p",
        type=str,
        nargs="+",
        metavar="TIME:OFFSET",
        help="Multiple sync points in format HH:MM:SS:OFFSET_SECONDS. Example: 00:00:30:0 00:10:00:5"
    )
    mode_group.add_argument(
        "--drift-rate", "-d",
        type=str,
        choices=list(COMMON_DRIFT_RATES.keys()),
        help="Apply a known drift rate from common frame rate conversions"
    )
    
    # Two-point correction arguments
    parser.add_argument(
        "--offset-at", "-o",
        type=str,
        help="Time where we know the offset. Format: HH:MM:SS[,.mmm]"
    )
    parser.add_argument(
        "--offset",
        type=float,
        help="Offset in seconds at --offset-at time (positive = subtitles are late)"
    )
    
    # Drift rate mode argument
    parser.add_argument(
        "--reference", "-r",
        type=str,
        default="00:00:00",
        help="Reference time for drift rate mode. Default: 00:00:00"
    )
    
    # Output options
    parser.add_argument(
        "--output", "-O",
        type=str,
        help="Output file (default: stdout)"
    )
    parser.add_argument(
        "--no-clamp",
        action="store_true",
        help="Don't clamp negative timestamps to zero"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print verbose information about the correction"
    )
    
    return parser.parse_args()


def main() -> None:
    """Main entry point for the autosync command."""
    args = parse_args()
    
    # Parse reference time
    reference_time_ms = parse_time(args.reference)
    
    # Build DriftConfig based on mode
    if args.correct_at and args.offset_at and args.offset is not None:
        # Two-point mode
        reference_time_ms = parse_time(args.correct_at)
        offset_time_ms = parse_time(args.offset_at)
        offset_ms = args.offset * 1000  # Convert to milliseconds
        
        config = DriftConfig(
            reference_time=reference_time_ms,
            offset_time=offset_time_ms,
            offset_at_offset_time=offset_ms
        )
        
        if args.verbose:
            print(f"Two-point drift correction:", file=sys.stderr)
            print(f"  Reference: {args.correct_at} (offset = 0)", file=sys.stderr)
            print(f"  Offset at: {args.offset_at} (offset = {args.offset}s)", file=sys.stderr)
            print(f"  Drift rate: {config.drift_rate * 1000:.3f} ms/s ({config.drift_rate * 100:.3f}%%)", file=sys.stderr)
    
    elif args.points:
        # Multi-point mode
        sync_points = []
        for point in args.points:
            # Parse TIME:OFFSET format
            # Find the last colon that's part of the time (after HH:MM:SS)
            match = re.match(r'(.+):(-?\d+\.?\d*)$', point)
            if not match:
                print(f"Error: Invalid sync point format: {point}. Expected TIME:OFFSET", file=sys.stderr)
                sys.exit(1)
            
            time_str, offset_str = match.groups()
            time_ms = parse_time(time_str)
            offset_ms = float(offset_str) * 1000
            sync_points.append((time_ms, offset_ms))
        
        config = DriftConfig(
            reference_time=sync_points[0][0],
            offset_time=sync_points[-1][0],
            offset_at_offset_time=sync_points[-1][1],
            sync_points=sync_points
        )
        
        # Validate
        warnings = validate_sync_points(reference_time_ms, sync_points[-1][0], sync_points)
        for warning in warnings:
            print(f"Warning: {warning}", file=sys.stderr)
        
        if args.verbose:
            print(f"Multi-point drift correction with {len(sync_points)} points:", file=sys.stderr)
            for time_ms, offset_ms in sync_points:
                print(f"  {format_time(time_ms)}: offset = {offset_ms/1000:+.3f}s", file=sys.stderr)
            print(f"  Overall drift rate: {config.drift_rate * 1000:.3f} ms/s", file=sys.stderr)
    
    elif args.drift_rate:
        # Known drift rate mode
        drift_rate = COMMON_DRIFT_RATES[args.drift_rate]
        # Create a config that applies this rate from the reference time
        # We use a dummy offset_time 1 second after reference to set the rate
        config = DriftConfig(
            reference_time=reference_time_ms,
            offset_time=reference_time_ms + 1000,  # 1 second later
            offset_at_offset_time=drift_rate * 1000  # offset in ms for 1 second
        )
        
        if args.verbose:
            print(f"Known drift rate: {args.drift_rate}", file=sys.stderr)
            print(f"  Rate: {drift_rate * 1000:.3f} ms/s ({drift_rate * 100:.3f}%%)", file=sys.stderr)
            print(f"  Reference: {format_time(reference_time_ms)}", file=sys.stderr)
    
    # Read SRT content from stdin
    srt_content = sys.stdin.read()
    
    # Apply correction
    result = apply_drift_correction(
        srt_content,
        config,
        clamp_to_zero=not args.no_clamp
    )
    
    # Output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(result)
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
