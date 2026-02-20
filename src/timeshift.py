#!/usr/bin/env python3
import sys
import datetime
import argparse


def shift_timestamp(timestamp: str, shift_seconds: float) -> str:
    """Shift a timestamp string by *shift_seconds* (positive → earlier, negative → later)."""
    try:
        # SRT timestamps are always in the same day, so we can use any date.
        time_obj = datetime.datetime.strptime(timestamp, "%H:%M:%S,%f")
        new_time = time_obj - datetime.timedelta(seconds=shift_seconds)

        # Guard against under‑flow – SRT cannot represent negative times.
        if new_time < datetime.datetime(1900, 1, 1):
            return "00:00:00,000"

        # ``%f`` gives microseconds; we need only three digits (milliseconds).
        return new_time.strftime("%H:%M:%S,%f")[:-3]
    except ValueError:
        # If the timestamp cannot be parsed we simply return it unchanged.
        return timestamp


def timestamp_to_seconds(timestamp: str) -> float:
    """Convert an ``HH:MM:SS`` or ``HH:MM:SS,mmm`` timestamp to a float number of seconds."""
    if ',' in timestamp:
        # Include fractional part
        t = datetime.datetime.strptime(timestamp, "%H:%M:%S,%f")
    else:
        # No fractional part
        t = datetime.datetime.strptime(timestamp, "%H:%M:%S")
    return (
        t.hour * 3600
        + t.minute * 60
        + t.second
        + t.microsecond / 1_000_000
    )


def parse_args():
    """Parse command‑line arguments – exactly one of the two options must be supplied."""
    parser = argparse.ArgumentParser(
        description=(
            """
            Shift timestamps in an SRT file, from STDIN.
            Supply either a fixed number of seconds (``--shift-seconds``)
            or the desired start time of the first entry (``--first-entry-starts-at``).
            """
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "-s",
        "--shift-seconds",
        type=float,
        help="Number of seconds to shift timestamps (can be negative).",
    )
    group.add_argument(
        "-f",
        "--first-entry-starts-at",
        type=str,
        help=(
            "Desired start time of the first subtitle entry, in the form "
            "HH:MM:SS or HH:MM:SS,mmm (e.g. 00:01:32 or 00:01:32,945)."
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # If the user gave a concrete shift we can use it straight away.
    shift_seconds = args.shift_seconds

    # When the user gave a target start time we have to compute the shift
    # from the first timestamp we encounter.
    desired_start_seconds = None
    if args.first_entry_starts_at:
        try:
            desired_start_seconds = timestamp_to_seconds(args.first_entry_starts_at)
        except ValueError:
            sys.stderr.write(
                f"Error: cannot parse '--first-entry-starts-at' value "
                f"'{args.first_entry_starts_at}'. Expected format HH:MM:SS or HH:MM:SS,mmm\n"
            )
            sys.exit(1)

    # Process the input stream in a single pass.
    for line in sys.stdin:
        if "-->" in line:
            # Split the line into start / end timestamps.
            start_raw, end_raw = (part.strip() for part in line.split("-->"))

            # If we still do not know the shift (because we are using the
            # ``first-entry-starts-at`` mode) compute it from the first entry.
            if shift_seconds is None:
                actual_start_seconds = timestamp_to_seconds(start_raw)
                shift_seconds = actual_start_seconds - desired_start_seconds
                # ``shift_seconds`` is now a concrete float and will be reused.

            # Apply the shift to both timestamps.
            new_start = shift_timestamp(start_raw, shift_seconds)
            new_end = shift_timestamp(end_raw, shift_seconds)
            print(f"{new_start} --> {new_end}")
        else:
            # Non‑timestamp lines (index numbers, text, blank lines) are printed unchanged.
            print(line, end="")


if __name__ == "__main__":
    main()
