#!/usr/bin/env python3
import sys
import datetime

def shift_timestamp(timestamp, shift_seconds):
    """Shifts a timestamp string down by a given number of seconds."""
    try:
        time_obj = datetime.datetime.strptime(timestamp, "%H:%M:%S,%f")
        new_time = time_obj - datetime.timedelta(seconds=shift_seconds)
        if new_time < datetime.datetime(1900, 1, 1):
            return "00:00:00,000"
        return new_time.strftime("%H:%M:%S,%f")[:-3]  # Remove extra zeros
    except ValueError:
        return timestamp  # Return original if parsing fails

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <shift_seconds>")
        sys.exit(1)

    try:
        shift_seconds = float(sys.argv[1])
    except ValueError:
        print("Error: Shift seconds must be a number.")
        sys.exit(1)

    for line in sys.stdin:
        if "-->" in line:
            parts = line.split("-->")
            start_time = parts[0].strip()
            end_time = parts[1].strip()
            new_start_time = shift_timestamp(start_time, shift_seconds)
            new_end_time = shift_timestamp(end_time, shift_seconds)
            print(f"{new_start_time} --> {new_end_time}")
        else:
            print(line, end="")
