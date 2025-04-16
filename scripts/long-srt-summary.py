#!/usr/bin/env python3
"""
Script to load an SRT file and split it into customizable time chunks.
"""

import os
import re
import argparse
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class SubtitleEntry:
    """Represents a single subtitle entry from an SRT file."""
    index: int
    start_time: datetime
    end_time: datetime
    text: str


def parse_time(time_str: str) -> datetime:
    """Convert SRT time format to datetime object."""
    # SRT format: 00:00:00,000
    hours, minutes, seconds_ms = time_str.split(':')
    seconds, milliseconds = seconds_ms.split(',')

    return datetime(
        year=1900, month=1, day=1,
        hour=int(hours), minute=int(minutes),
        second=int(seconds), microsecond=int(milliseconds) * 1000
    )


def format_time(dt: datetime) -> str:
    """Convert datetime object to SRT time format."""
    return f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d},{dt.microsecond//1000:03d}"


def parse_srt_file(file_path: str) -> List[SubtitleEntry]:
    """Parse an SRT file and return a list of SubtitleEntry objects."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"SRT file not found: {file_path}")

    entries = []
    current_entry = None

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines
        if not line:
            i += 1
            continue

        # Check if this line is a subtitle index
        if line.isdigit():
            # If we have a previous entry, add it to our list
            if current_entry:
                entries.append(current_entry)

            # Start a new entry
            index = int(line)
            i += 1

            # Parse the time line
            if i < len(lines):
                time_line = lines[i].strip()
                time_match = re.match(
                    r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})', time_line)

                if time_match:
                    start_time = parse_time(time_match.group(1))
                    end_time = parse_time(time_match.group(2))
                    i += 1

                    # Collect the text lines
                    text_lines = []
                    while i < len(lines) and lines[i].strip():
                        text_lines.append(lines[i].strip())
                        i += 1

                    # Create the entry
                    current_entry = SubtitleEntry(
                        index=index,
                        start_time=start_time,
                        end_time=end_time,
                        text=' '.join(text_lines)
                    )

        i += 1

    # Add the last entry if there is one
    if current_entry:
        entries.append(current_entry)

    return entries


def split_into_chunks(entries: List[SubtitleEntry], chunk_duration_minutes: int) -> List[List[SubtitleEntry]]:
    """Split subtitle entries into chunks of specified duration in minutes."""
    if not entries:
        return []

    chunks = []
    current_chunk = []

    # Calculate chunk duration in timedelta
    chunk_duration = timedelta(minutes=chunk_duration_minutes)

    # Get the start time of the first entry
    chunk_start_time = entries[0].start_time

    for entry in entries:
        # If this entry starts after the current chunk's end time, start a new chunk
        if entry.start_time >= chunk_start_time + chunk_duration:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                chunk_start_time = entry.start_time

        current_chunk.append(entry)

    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def write_chunk_to_srt(chunk: List[SubtitleEntry], output_path: str) -> None:
    """Write a chunk of subtitle entries to an SRT file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, entry in enumerate(chunk, 1):
            f.write(f"{i}\n")
            f.write(
                f"{format_time(entry.start_time)} --> {format_time(entry.end_time)}\n")
            f.write(f"{entry.text}\n\n")


def main():
    parser = argparse.ArgumentParser(
        description='Split an SRT file into chunks of specified duration.')
    parser.add_argument('--input', '-i', type=str, default='scripts/data/30min.srt',
                        help='Path to the input SRT file')
    parser.add_argument('--output-dir', '-o', type=str, default='scripts/data/chunks',
                        help='Directory to save the output chunks')
    parser.add_argument('--chunk-duration', '-d', type=int, default=10,
                        help='Duration of each chunk in minutes')

    args = parser.parse_args()

    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)

    # Parse the SRT file
    print(f"Parsing SRT file: {args.input}")
    entries = parse_srt_file(args.input)
    print(f"Found {len(entries)} subtitle entries")

    # Split into chunks
    print(f"Splitting into chunks of {args.chunk_duration} minutes")
    chunks = split_into_chunks(entries, args.chunk_duration)
    print(f"Created {len(chunks)} chunks")

    # Write chunks to files
    for i, chunk in enumerate(chunks, 1):
        output_path = os.path.join(args.output_dir, f"chunk_{i:03d}.srt")
        write_chunk_to_srt(chunk, output_path)
        print(f"Wrote chunk {i} to {output_path}")

    print("Done!")


if __name__ == "__main__":
    main()
