import io
import logging
import os
from pathlib import PosixPath
import random
import re
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from enum import Enum
from typing import BinaryIO
from typing import cast, Literal, Union, List
import langsmith as ls
import asyncio

from langchain_community.document_loaders.generic import GenericLoader
from pydub import AudioSegment

from app.cache import conditional_lru_cache
from app.config import get_downloads_path
from app.settings import get_settings
from app.transcribe.OpenAIWhisperParser import OpenAIWhisperParser
from app.youtube.loader import YoutubeAudioLoader

TEN_MINUTES = 10 * 60 * 1000
AUDIO_SPLIT_BYTES = 24000000


class LANG_CODE(str, Enum):
    ENGLISH = "en"
    POLISH = "pl"


class WHISPER_RESPONSE_FORMAT(str, Enum):
    JSON = "json"
    TEXT = "text"
    SRT = "srt"
    VERBOSE_JSON = "verbose_json"
    VTT = "vtt"


def downloads_path():
    return get_downloads_path()


def convert_response_format(format: WHISPER_RESPONSE_FORMAT) -> Union[
        Literal["json", "text", "srt", "verbose_json", "vtt"], None]:
    return cast(Union[
        Literal["json", "text", "srt", "verbose_json", "vtt"], None], format.value)


# Helper functions for time conversion and subtitle combining
def _time_str_to_ms(time_str: str) -> int:
    """Converts HH:MM:SS,ms or HH:MM:SS.ms string to milliseconds."""
    if not time_str:
        return 0
    # Allow both comma and dot as separator
    parts = re.split(r'[:,\.]', time_str)
    if len(parts) != 4:
        logging.warning(
            f"Unexpected time format encountered: {time_str}. Returning 0ms.")
        return 0

    try:
        h, m, s, ms = map(int, parts)
        return (h * 3600 + m * 60 + s) * 1000 + ms
    except ValueError:
        logging.warning(
            f"Could not parse time string components: {time_str}. Returning 0ms.")
        return 0


def _ms_to_time_str(ms: int, separator: str = ',') -> str:
    """Converts milliseconds to HH:MM:SS<separator>ms string."""
    if ms < 0:
        ms = 0  # Ensure non-negative time
    td = timedelta(milliseconds=ms)
    total_seconds = int(td.total_seconds())
    milliseconds = int(round(td.microseconds / 1000))  # Round milliseconds
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{milliseconds:03d}"


def _combine_subtitle_chunks(results: list[Union[str, None]],
                             chunk_duration_ms: int,
                             format_type: Literal["srt", "vtt"]) -> str:
    """Combines SRT or VTT chunk results with adjusted timestamps and sequence numbers."""
    combined_lines = []
    global_seq_num = 1
    separator = '.' if format_type == 'vtt' else ','

    # Regex to capture SRT/VTT blocks. Handles optional sequence numbers and VTT settings line.
    # Group 1: Optional sequence number line (like "1\n")
    # Group 2: Start timestamp
    # Group 3: End timestamp
    # Group 4: Optional VTT settings part of the timestamp line
    # Group 5: Text content
    pattern = re.compile(
        # Optional sequence number line (non-capturing group for start anchor)
        r"^(?:(\d+)\s*\n)?"
        # Timestamps (allow trailing spaces/settings for VTT)
        r"(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})([^\S\n]*[^\n]*)?\s*\n"
        r"([\s\S]*?)"  # Text content
        r"(?=\n\n|\Z)",  # Lookahead for blank line or end of string
        re.MULTILINE
    )

    if format_type == 'vtt':
        combined_lines.append("WEBVTT\n")  # Add header only once

    # Track the highest end time seen in each chunk to calculate proper offsets
    chunk_offsets = []
    # First pass: find max end time in each chunk to determine offsets
    for chunk_index, chunk_content in enumerate(results):
        if chunk_content is None or not isinstance(chunk_content, str) or not chunk_content.strip():
            # For missing/empty chunks, use the theoretical duration as a fallback
            chunk_offsets.append(chunk_duration_ms if chunk_index > 0 else 0)
            continue

        # Clean VTT header for parsing
        current_chunk_text = chunk_content
        if format_type == 'vtt':
            current_chunk_text = re.sub(
                r"^WEBVTT\s*\n+", "", current_chunk_text)

        matches = list(pattern.finditer(current_chunk_text))

        if not matches:
            # If no matches, use theoretical duration as fallback
            chunk_offsets.append(chunk_duration_ms if chunk_index > 0 else 0)
            continue

        # Find the maximum end time in this chunk
        max_end_ms = 0
        for match in matches:
            _, _, end_time_str, _, _ = match.groups()
            end_ms = _time_str_to_ms(end_time_str)
            max_end_ms = max(max_end_ms, end_ms)

        # For first chunk, offset is 0. For subsequent chunks, it's the sum of all previous max end times
        chunk_offsets.append(max_end_ms if chunk_index == 0 else max_end_ms)

    # Calculate cumulative offsets - each chunk starts where the previous ended
    cumulative_offsets = [0]  # First chunk starts at 0
    for i in range(1, len(chunk_offsets)):
        # Add previous chunk's max end time to running total
        cumulative_offsets.append(cumulative_offsets[i-1] + chunk_offsets[i-1])

    # Log offset information for debugging
    logging.debug(f"Calculated chunk offsets: {cumulative_offsets}")

    for chunk_index, chunk_content in enumerate(results):
        # Get the timing offset for this chunk from our calculation
        chunk_start_offset_ms = cumulative_offsets[chunk_index]

        if chunk_content is None or not isinstance(chunk_content, str) or not chunk_content.strip():
            logging.warning(
                f"Skipping empty, None, or non-string chunk at index {chunk_index}")
            continue  # Skip this chunk entirely

        # Clean VTT header if present in individual chunks
        current_chunk_text = chunk_content
        if format_type == 'vtt':
            current_chunk_text = re.sub(
                r"^WEBVTT\s*\n+", "", current_chunk_text)

        matches = pattern.finditer(current_chunk_text)
        found_match_in_chunk = False

        for match in matches:
            found_match_in_chunk = True
            # group(1)=seq_num, group(2)=start, group(3)=end, group(4)=vtt_settings, group(5)=text
            _seq_num_line, start_time_str, end_time_str, vtt_settings, text = match.groups()

            # VTT settings might be None if not present
            vtt_settings = vtt_settings or ""

            start_ms = _time_str_to_ms(start_time_str)
            end_ms = _time_str_to_ms(end_time_str)

            # Adjust times by adding the offset for the start of this chunk
            new_start_ms = start_ms + chunk_start_offset_ms
            new_end_ms = end_ms + chunk_start_offset_ms

            if new_end_ms < new_start_ms:
                logging.warning(
                    f"Adjusted end time {new_end_ms}ms ({end_time_str} + {chunk_start_offset_ms}ms offset) "
                    f"is before start time {new_start_ms}ms ({start_time_str} + {chunk_start_offset_ms}ms offset) "
                    f"for seq {global_seq_num}. Clamping end = start."
                )
                new_end_ms = new_start_ms

            new_start_str = _ms_to_time_str(new_start_ms, separator)
            new_end_str = _ms_to_time_str(new_end_ms, separator)

            # Add sequence number (required for SRT, good practice for VTT)
            combined_lines.append(f"{global_seq_num}")
            # Add times (append VTT settings if any)
            combined_lines.append(
                f"{new_start_str} --> {new_end_str}{vtt_settings}")
            # Add text (strip leading/trailing whitespace from capture, preserve internal newlines)
            combined_lines.append(text.strip())
            # Add blank line separator
            combined_lines.append("")

            global_seq_num += 1

        if not found_match_in_chunk and current_chunk_text.strip():
            logging.warning(
                f"Chunk {chunk_index} content present but no subtitle blocks found by regex:\n---\n{current_chunk_text[:200]}...\n---")

    # Join lines, ensuring final newline if content exists
    # Check if more than just header was added
    if len(combined_lines) > (1 if format_type == 'vtt' else 0):
        result = "\n".join(combined_lines)
        # Ensure it ends with a newline, but not double newline if already present
        if result.endswith("\n\n"):
            pass  # Correctly ends with double newline
        elif result.endswith("\n"):
            result += "\n"  # Add the second newline for subtitle block separation
        else:
            result += "\n\n"  # Add required newlines
        return result
    else:
        # No valid subtitle blocks found in any chunk
        logging.warning("No valid subtitle blocks found in any chunk.")
        return "WEBVTT\n\n" if format_type == 'vtt' else ""  # Return empty valid file


def download_and_extract_audio_from_link(url: str, save_dir: str) -> PosixPath | None:
    """
    Download audio from a video link supported by yt_dlp library

    Args:
        url: YouTube video URL
        save_dir: Directory to save the audio file
        proxy_servers: Optional list of proxy servers

    Returns:
        Path to the downloaded audio file or None if download fails
    """
    logging.info(
        f"Downloading audio from: {url}, save_dir: {save_dir}")

    settings = get_settings()
    proxy_servers = settings.proxy_servers.split(
        ",") if settings.proxy_servers and settings.use_proxy else None

    # Create directory if it doesn't exist
    os.makedirs(save_dir, exist_ok=True)

    # Initialize the loader
    loader = YoutubeAudioLoader([url], save_dir, proxy_servers)

    # Download the audio
    print(f"Downloading audio from: {url}")
    blobs = list(loader.yield_blobs())

    if not blobs:
        print(f"Failed to download audio from: {url}")
        return None

    # Return path to the downloaded file
    audio_path = blobs[0].path
    print(f"Audio downloaded successfully: {audio_path}")
    return audio_path


@conditional_lru_cache
@ls.traceable(
    run_type="llm",
    name="Transcription from file",
    tags=["file", "transcription", "audio"],
    metadata={"flow": "transcription"}
)
async def transcribe(file: BinaryIO,
                     lang: LANG_CODE = LANG_CODE.ENGLISH,
                     response_format: WHISPER_RESPONSE_FORMAT = WHISPER_RESPONSE_FORMAT.TEXT
                     ) -> Union[str, List[object]]:
    """
    Transcribe audio file to text
    """
    logging.info(
        f"Transcribing audio file: {file.name if hasattr(file, 'name') else 'Unnamed Stream'}, lang: {lang}, format: {response_format}")

    # Reset file position
    _reset_file_position(file)

    # Get file size
    size = _get_file_size(file)
    logging.debug(f"Determined file size: {size} bytes")

    # Process file based on size
    if size > AUDIO_SPLIT_BYTES:
        docs = await _process_large_file(file, lang, response_format, size)
        processed_chunks = True
    else:
        docs = await _process_small_file(file, lang, response_format)
        processed_chunks = False

    # Aggregate results
    return _aggregate_results(docs, response_format, processed_chunks)


def _reset_file_position(file: BinaryIO) -> None:
    """Reset file pointer to beginning if possible"""
    if file.seekable():
        file.seek(0)


def _get_file_size(file: BinaryIO) -> int:
    """Get file size reliably from various file-like objects"""
    size = -1
    try:
        if hasattr(file, 'name') and os.path.exists(file.name):
            size = os.path.getsize(file.name)
        elif hasattr(file, 'getbuffer'):
            size = len(file.getbuffer())
        elif hasattr(file, 'getvalue'):
            size = len(file.getvalue())
        elif hasattr(file, 'tell') and hasattr(file, 'seek'):
            pos = file.tell()
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(pos)
    except Exception as e:
        logging.error(f"Error getting file size: {e}")
        size = 0
    return size


async def _process_large_file(file: BinaryIO, lang: LANG_CODE, response_format: WHISPER_RESPONSE_FORMAT, size: int) -> List[Union[str, object, None]]:
    """Process large audio file by splitting into chunks"""
    logging.info(
        f"File size {size} > {AUDIO_SPLIT_BYTES}, splitting into chunks")

    # Prepare audio source
    audio_source = _prepare_audio_source(file)

    try:
        # Load audio with pydub
        parts = _load_audio(audio_source)

        # Process chunks
        docs = await _process_audio_chunks(parts, lang, response_format)

        return docs
    finally:
        # Clean up temporary files
        _cleanup_temp_files(audio_source)


async def _process_small_file(file: BinaryIO, lang: LANG_CODE, response_format: WHISPER_RESPONSE_FORMAT) -> List[Union[str, object, None]]:
    """Process small audio file in one go"""
    logging.info("File size within limit, processing as a single file")
    try:
        if file.seekable():
            file.seek(0)
        result = await small_file(file, lang, response_format)
        return [result]
    except Exception as e:
        logging.error(
            f"Error during single file transcription: {e}", exc_info=True)
        return [None]


def _aggregate_results(docs: List[Union[str, object, None]], response_format: WHISPER_RESPONSE_FORMAT, processed_chunks: bool) -> Union[str, List[object]]:
    """Aggregate results based on response format"""
    # Filter out None results
    valid_docs = [doc for doc in docs if doc is not None]

    if not valid_docs:
        return _get_empty_result(response_format)

    # Format-specific aggregation
    if response_format == WHISPER_RESPONSE_FORMAT.TEXT:
        return " ".join(str(doc) for doc in valid_docs)
    elif response_format in (WHISPER_RESPONSE_FORMAT.SRT, WHISPER_RESPONSE_FORMAT.VTT):
        return _aggregate_subtitle_format(valid_docs, response_format, processed_chunks)
    elif response_format in (WHISPER_RESPONSE_FORMAT.JSON, WHISPER_RESPONSE_FORMAT.VERBOSE_JSON):
        return valid_docs
    else:
        return " ".join(str(doc) for doc in valid_docs)


@conditional_lru_cache
async def small_file(file: BinaryIO, lang: LANG_CODE = LANG_CODE.ENGLISH, response_format: WHISPER_RESPONSE_FORMAT = WHISPER_RESPONSE_FORMAT.TEXT):
    """
    :param response_format:
    :param file: binary file
    :param lang:  language: The language of the input audio. Supplying the input language in
            [ISO-639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes) format will
            improve accuracy and latency.
    :return:
    """
    logging.info(
        f"Transcribing audio file using openai api: '{file}', with lang: '{lang}', response_format: '{response_format}'")

    from app.settings import client_openai
    transcription = await client_openai.audio.transcriptions.create(
        model="whisper-1",
        file=file,
        language=lang.value,
        response_format=convert_response_format(response_format),
    )

    return transcription


def _prepare_audio_source(file: BinaryIO) -> Union[str, BinaryIO]:
    """Prepare audio source for pydub, handling non-seekable streams."""
    temp_audio_path = None

    # Handle non-seekable stream
    if not file.seekable():
        logging.warning(
            "Input file stream is not seekable. Reading into temporary file.")
        temp_audio_path = f"{downloads_path()}/temp_audio_{random.randint(0, 100000)}.audio"
        try:
            with open(temp_audio_path, 'wb') as temp_f:
                while True:
                    chunk = file.read(10 * 1024 * 1024)  # 10MB chunks
                    if not chunk:
                        break
                    temp_f.write(chunk)
            return temp_audio_path
        except Exception as e:
            logging.error(f"Failed to create temporary file: {e}")
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
            raise IOError("Error processing non-seekable audio stream.") from e
    else:
        # Use seekable file directly
        file.seek(0)
        return file


def _load_audio(audio_source: Union[str, BinaryIO]) -> AudioSegment:
    """Load audio with pydub from file or stream."""
    file_format = None
    if isinstance(audio_source, BinaryIO) and hasattr(audio_source, 'name'):
        _, ext = os.path.splitext(audio_source.name)
        if ext:
            file_format = ext[1:]

    logging.debug(f"Loading audio with format hint: {file_format}")
    try:
        return AudioSegment.from_file(audio_source, format=file_format)
    except Exception as e:
        logging.error(f"Pydub failed to load audio: {e}", exc_info=True)
        raise ValueError(f"Could not process audio file: {e}") from e


async def _process_audio_chunks(parts: AudioSegment, lang: LANG_CODE,
                                response_format: WHISPER_RESPONSE_FORMAT) -> List[Union[str, object, None]]:
    """Process audio in chunks."""
    processing_id = str(random.randint(0, 100000))
    ten_minutes_ms = TEN_MINUTES

    async def process_chunk(chunk_index, start_ms, end_ms):
        chunk_num = chunk_index + 1
        logging.debug(
            f"Processing chunk {chunk_num} ({start_ms/1000.0:.2f}s to {end_ms/1000.0:.2f}s)")

        chunk_audio = parts[start_ms:end_ms]
        chunk_filename = f"{downloads_path()}/{processing_id}_chunk{chunk_num}.mp3"

        try:
            # Export chunk to file
            with open(chunk_filename, "wb") as chunk_f:
                chunk_audio.export(chunk_f, format="mp3")

            # Process chunk
            with open(chunk_filename, "rb") as chunk_f_read:
                result = await small_file(chunk_f_read, lang, response_format)
            return result
        except Exception as e:
            logging.error(
                f"Chunk {chunk_num} processing error: {e}", exc_info=True)
            return None
        finally:
            if os.path.exists(chunk_filename):
                try:
                    os.remove(chunk_filename)
                except OSError as e:
                    logging.warning(
                        f"Failed to remove chunk file {chunk_filename}: {e}")

    # Create tasks for each chunk
    tasks = []
    for i, start_ms in enumerate(range(0, len(parts), ten_minutes_ms)):
        end_ms = min(start_ms + ten_minutes_ms, len(parts))
        if start_ms >= end_ms:
            continue
        tasks.append(process_chunk(i, start_ms, end_ms))

    # Run tasks concurrently
    return await asyncio.gather(*tasks)


def _cleanup_temp_files(audio_source: Union[str, BinaryIO]) -> None:
    """Clean up temporary files if created."""
    if isinstance(audio_source, str) and os.path.exists(audio_source):
        try:
            os.remove(audio_source)
            logging.debug(f"Removed temporary audio file: {audio_source}")
        except OSError as e:
            logging.warning(
                f"Could not remove temporary file {audio_source}: {e}")


def _get_empty_result(response_format: WHISPER_RESPONSE_FORMAT) -> Union[str, List]:
    """Return appropriate empty result based on format."""
    logging.warning("No successful transcription results obtained.")
    if response_format == WHISPER_RESPONSE_FORMAT.TEXT:
        return ""
    elif response_format == WHISPER_RESPONSE_FORMAT.SRT:
        return ""
    elif response_format == WHISPER_RESPONSE_FORMAT.VTT:
        return "WEBVTT\n\n"
    elif response_format in (WHISPER_RESPONSE_FORMAT.JSON, WHISPER_RESPONSE_FORMAT.VERBOSE_JSON):
        return []
    return ""


def _aggregate_subtitle_format(valid_docs: List[Union[str, object]],
                               response_format: WHISPER_RESPONSE_FORMAT,
                               processed_chunks: bool) -> str:
    """Aggregate subtitle format results (SRT/VTT)."""
    is_vtt = response_format == WHISPER_RESPONSE_FORMAT.VTT
    format_str: Literal['srt', 'vtt'] = 'vtt' if is_vtt else 'srt'

    if processed_chunks:
        # Combine chunks with timestamp adjustments
        return _combine_subtitle_chunks(valid_docs, TEN_MINUTES, format_str)
    elif len(valid_docs) == 1:
        # Single result needs format validation
        single_result_str = str(valid_docs[0])

        if is_vtt and not single_result_str.strip().startswith("WEBVTT"):
            logging.warning("Adding missing WEBVTT header")
            result = "WEBVTT\n\n" + single_result_str.strip() + "\n\n"
        elif not is_vtt and re.match(r"^\s*WEBVTT", single_result_str):
            logging.warning("Removing WEBVTT header from SRT result")
            result = re.sub(r"^\s*WEBVTT\s*\n+", "",
                            single_result_str) + "\n\n"
        else:
            result = single_result_str

        # Ensure proper ending
        if not result.endswith("\n\n"):
            if result.endswith("\n"):
                result += "\n"
            else:
                result += "\n\n"
        return result

    # Fallback case
    logging.error("Unexpected state for subtitle aggregation")
    return ""
