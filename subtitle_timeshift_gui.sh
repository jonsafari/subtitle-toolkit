#!/bin/sh
# By Jon Dehdari, 2025
# Simple GUI to timeshift your subtitle file


# First optionally select a video, and determine when the first subtitle should be.
VIDEO_FILE=$(zenity --title='Open video and determine when the first subtitle should start' --text 'Open video and determine when the first subtitle should start' --file-selection --filename="$MODEL_DIR" ) && open $VIDEO_FILE

#START_SECS=$(zenity --title='When should the first subtitle start (in seconds)?' --text 'When should the first subtitle start (in seconds)?' --entry --entry-text=0.0) || exit
START_TIME=$(zenity --title='When should the first subtitle start, in HH:MM:SS,mmm format?' --text 'When should the first subtitle start, in HH:MM:SS,mmm format?' --entry --entry-text='HH:MM:SS,mmm') || exit

SRT_FILE=$(zenity --title='Select subtitle (SRT) input file' --text 'Select subtitle (SRT) input file' --file-selection) || exit
OUT_FILENAME=$(zenity --title='New name of corrected subtitle file' --text 'New name of corrected subtitle file' --entry --entry-text=$SRT_FILE) || exit

# Create temporary file, in case input and output are same file
tmpfile=$(mktemp)

cat $SRT_FILE | subtitle_timeshift.py --first-entry-starts-at ${START_TIME} > $tmpfile && mv $tmpfile ${OUT_FILENAME}
