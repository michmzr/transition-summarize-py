#!/usr/bin/env python3
"""
Script to load an SRT file and split it into customizable time chunks.
"""
from pathlib import Path as p

import os
import re
import argparse
import concurrent.futures
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from langchain import PromptTemplate
from langchain.chains.summarize import load_summarize_chain
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.document_loaders import TextLoader
import langsmith as ls

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


def chunk_transcript(output_dir: str, trans_file_path: str, chunk_duration_minutes: int) -> List[str]:
    # Parse the SRT file
    entries = parse_srt_file(trans_file_path)
    print(f"Found {len(entries)} subtitle entries")

    # Split into chunks
    print(f"Splitting into chunks of {chunk_duration_minutes} minutes")
    chunks = split_into_chunks(entries, chunk_duration_minutes)
    print(f"Created {len(chunks)} chunks")

    chunks_paths = []
    # Write chunks to files
    for i, chunk in enumerate(chunks, 1):
        output_path = os.path.join(output_dir, f"chunk_{i:03d}.srt")
        write_chunk_to_srt(chunk, output_path)
        print(f"Wrote chunk {i} to {output_path}")
        chunks_paths.append(output_path)

    return chunks_paths


def prompts01(lang: str):
    map_prompt_template = """
                        Write a summary of this chunk of text that includes the main points and any important details.
                        Strongly adhere to the following guidelines:
                            - Incorporate main ideas and essential information, eliminating extraneous language and focusing on critical aspects.
                            - Rely strictly on the provided text, without including external information.
                            - Format the summary in paragraph form for easy understanding.
                            - If chunks describes any technniques, approaches, strategies,patterns, methods, tools, software, hardware, services, products etc. list them in seperated subsections. Give as mush details as possible ,If empty, just skip it
                            - Prepare very detailed bullet points list: what happened, subjects, details, people, places, things, events, etc.
                        ###
                        {text}
                        """

    chunk_prompt = PromptTemplate(
        template=map_prompt_template, input_variables=["text"])

    combine_prompt_template = """As a professional summarizer, create a detailed, in-depth, and concise summary in language code="""+lang+""" of the provided text, while strongly adhering to these guidelines:
            - Incorporate main ideas and essential information, eliminating extraneous language and focusing on critical aspects.
            - Rely strictly on the provided text, without including external information.
            - Format the summary in paragraph form for easy understanding.
            - The entire content should be organized in a clear and logical manner
            - use markdown to format the text, you can use emojis, bullet points, numbered lists, etc. to make the summary more engaging and easy to read.

            Include extra information such as:
            - list of mentioned articles, books, podcasts,persons, movies etc. in seperated subsections. If empty, just skip it
            - list of guidelines, practises,techniques, rules, principles, steps, procedures etc. in seperated subsections. If empty, just skip it
            - list of examples, scenarios, use cases, case studies etc. in seperated subsections. If empty, just skip it
            - list of tools, software, hardware, services, products etc. in seperated subsections. If empty, just skip it

            My needs:
            - I want to get super detailed summary of super important text. I use it for my research job and i need to get all the details from the text.

            I will pay you extra if you can provide me with a very detailed summary of the text in the language of the text. I need to get all the details from the text.

            ###
            {text}
            """

    combine_prompt = PromptTemplate(
        template=combine_prompt_template, input_variables=["text"]
    )

    return chunk_prompt, combine_prompt


def map_reduce_chain(llm, docs, chunk_prompt: PromptTemplate, combine_prompt: PromptTemplate):
    map_reduce_chain = load_summarize_chain(
        llm,
        chain_type="map_reduce",
        map_prompt=chunk_prompt,
        token_max=10000,
        combine_prompt=combine_prompt,
        return_intermediate_steps=True,
    )
    map_reduce_outputs = map_reduce_chain(
        {"input_documents": docs})
    return map_reduce_outputs


def analyze_map_reduce_outputs(map_reduce_outputs):
    final_mp_data = []

    for doc, out in zip(
        map_reduce_outputs["input_documents"], map_reduce_outputs["intermediate_steps"]
    ):
        output = {}
        output["file_name"] = p(doc.metadata["source"]).stem
        output["file_type"] = p(doc.metadata["source"]).suffix
        output["chunks"] = doc.page_content
        output["concise_summary"] = out
        final_mp_data.append(output)

    return final_mp_data


@ls.traceable(
    run_type="prompt",
    name="Test Long Summary Map Reduce",
    tags=["smap_reduce"],
    metadata={"flow": "test_long_summary"}
)
def summarize_map_reduce(llm, docs, chunk_prompt: PromptTemplate, combine_prompt: PromptTemplate):
    map_reduce_outputs = map_reduce_chain(
        llm, docs, chunk_prompt, combine_prompt)
    return analyze_map_reduce_outputs(map_reduce_outputs)


def run_model_map_reduce(model_name: str, docs: List, prompts: Tuple[PromptTemplate, PromptTemplate], output_dir: str):
    """Process a single model"""
    print(f"Running {model_name}")

    if model_name.startswith("gpt"):
        llm = ChatOpenAI(model=model_name, temperature=0)
    elif model_name.startswith("claude"):
        llm = ChatAnthropic(model=model_name, temperature=0)

    # Map reduce chain
    map_reduce_outputs = summarize_map_reduce(
        llm, docs, prompts[0], prompts[1])

    # Save map reduce outputs to file
    print(f"Saving {model_name} outputs to {output_dir}")
    with open(os.path.join(output_dir, model_name + "_map_reduce_parts_outputs.json"), "w") as f:
        f.write(str(map_reduce_outputs))
    with open(os.path.join(output_dir, model_name + "_map_reduce_summary.md"), "w") as f:
        f.write(str(map_reduce_outputs[0]["concise_summary"]))

    return model_name

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

    lang = "pl"

    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)

    # Make chunks
    chunks = chunk_transcript(args.output_dir, args.input, args.chunk_duration)
    print(f"Created {len(chunks)} chunks")

    # Set up LangChain
    models = ["gpt-4o", "gpt-4o-mini", "claude-3-7-sonnet-20250219",
              "claude-3-5-haiku-20241022"]  #

    # Load chunks to LangChain once (shared across all models)
    docs = []
    for chunk in chunks:
        docs.extend(TextLoader(chunk).load())

    # Prepare prompts once (shared across all models)
    prompts = prompts01(lang)

    # Run models in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for model in models:
            futures.append(
                executor.submit(run_model_map_reduce, model, docs,
                                prompts, args.output_dir)
            )

        # Wait for all tasks to complete
        for future in concurrent.futures.as_completed(futures):
            try:
                model_name = future.result()
                print(f"Completed processing for {model_name}")
            except Exception as e:
                print(f"Error processing model: {e}")

    # Remove chunks
    for chunk in chunks:
        os.remove(chunk)


if __name__ == "__main__":
    main()
