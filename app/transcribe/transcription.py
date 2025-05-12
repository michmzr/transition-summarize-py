import io
import logging
import os
import random
import re
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from enum import Enum
from typing import BinaryIO
from typing import cast, Literal, Union, List
import langsmith as ls

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


@ls.traceable(
    run_type="llm",
    name="Transcription",
    tags=["yt", "transcription"],
    metadata={"flow": "transcription"}
)
@conditional_lru_cache
def yt_transcribe(url: str,
                  save_dir: str,
                  lang: LANG_CODE,
                  response_format: WHISPER_RESPONSE_FORMAT):
    """
    Transcribe the videos to text

    inspiration: https://python.langchain.com/docs/integrations/document_loaders/youtube_audio/
    :param lang:
    :param response_format:
    :param url: yt video url
    :param save_dir:
    """
    logging.info(
        f"Processing url: {url}, save_dir: {save_dir}, lang: {lang}, response_format: {response_format}")

    settings = get_settings()
    proxy_servers = settings.proxy_servers.split(
        ",") if settings.proxy_servers and settings.use_proxy else None

    logging.debug(
        f"Proxy servers: {proxy_servers} - using proxy: {settings.use_proxy}")

    # TODO check if file was already downloaded
    # TODO check if transcription was already done - DB
    loader = GenericLoader(YoutubeAudioLoader([url], save_dir, proxy_servers),
                           OpenAIWhisperParser(api_key=settings.openai_api_key,
                                               language=lang.value,
                                               response_format=convert_response_format(
                                                   response_format),
                                               temperature=0
                                               ))
    docs = loader.load()

    # read all docs, get page_content and concatenate
    return " ".join([doc.page_content for doc in docs])


@ls.traceable(
    run_type="llm",
    name="Transcription from file",
    tags=["file", "transcription"],
    metadata={"flow": "transcription"}
)
async def transcribe(file: BinaryIO,
               lang: LANG_CODE = LANG_CODE.ENGLISH,
               response_format: WHISPER_RESPONSE_FORMAT = WHISPER_RESPONSE_FORMAT.TEXT
               ) -> Union[str, List[object]]:
    """
    Transcribe audio file to text

    Handles large files by splitting into chunks and merging the results.
    For SRT/VTT formats, timestamps and sequence numbers are adjusted.
    For JSON/VERBOSE_JSON formats, returns a list of results from each chunk.

    inspiration: https://python.langchain.com/docs/integrations/document_loaders/youtube_audio/
    :param response_format: Desired output format (TEXT, SRT, VTT, JSON, VERBOSE_JSON)
    :param lang: Lang code (e.g., ENGLISH, POLISH)
    :param file: audio file (BinaryIO)
    :return: Transcription result as a string (for TEXT, SRT, VTT) or list of objects (for JSON, VERBOSE_JSON)
    """
    logging.info(
        f"Transcribing audio file: {file.name if hasattr(file, 'name') else 'Unnamed Stream'}, lang: {lang}, format: {response_format}")

    # Ensure file pointer is at the beginning if possible
    if file.seekable():
        file.seek(0)

    # Get file size reliably
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
        logging.error(
            f"Error getting file size: {e}. Attempting transcription assuming small file.")
        size = 0  # Force small file path if stats fail

    logging.debug(
        f"Determined file size: {size} bytes (approx. if read from stream)")

    # Allow for mixed types initially
    docs: List[Union[str, object, None]] = []
    processed_chunks = False

    if size > AUDIO_SPLIT_BYTES:
        processed_chunks = True
        logging.info(
            f"File size {size} > {AUDIO_SPLIT_BYTES}, splitting audio file into chunks.")

        # Handle non-seekable stream for Pydub by copying to a temp file
        if not file.seekable():
            logging.warning(
                "Input file stream is not seekable. Reading into temporary file for chunk processing.")
            temp_file_path = f"{downloads_path()}/temp_audio_{random.randint(0, 100000)}.audio"
            try:
                with open(temp_file_path, 'wb') as temp_f:
                    # We already read the initial part if size wasn't determinable before
                    if 'initial_chunk' in locals() and initial_chunk:
                        temp_f.write(initial_chunk)
                        logging.debug(
                            f"Wrote initial {len(initial_chunk)} bytes from size check to temp file.")
                    # Read the rest of the stream
                    while True:
                        # Read 10MB at a time
                        more_data = file.read(10 * 1024 * 1024)
                        if not more_data:
                            break
                        temp_f.write(more_data)
                audio_source = temp_file_path
                logging.debug(
                    f"Using temporary file for pydub: {audio_source}")
            except Exception as e:
                logging.error(
                    f"Failed to create/use temporary file for non-seekable stream: {e}")
                # Clean up partial temp file if it exists
                if os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                    except OSError:
                        pass
                raise IOError(
                    "Error processing non-seekable audio stream.") from e
        else:
            # Seekable file, pydub can handle it directly
            file.seek(0)  # Ensure pydub reads from start
            audio_source = file
            logging.debug(
                f"Using seekable file stream for pydub: {getattr(file, 'name', 'Unnamed Stream')}")

        temp_audio_path_to_clean = None
        if isinstance(audio_source, str):
            temp_audio_path_to_clean = audio_source  # Mark for cleanup

        try:
            # Use the determined audio_source (path or file object)
            # Explicitly provide format if possible, otherwise let pydub guess
            file_format = None
            if hasattr(file, 'name') and isinstance(file.name, str):
                _, ext = os.path.splitext(file.name)
                if ext:
                    file_format = ext[1:]  # e.g., 'mp3', 'wav'
            logging.debug(
                f"Attempting to load audio with pydub (format hint: {file_format})...")
            parts = AudioSegment.from_file(
                audio_source, format=file_format)  # Might need format hint
            logging.debug(
                f"Audio loaded successfully. Duration: {len(parts) / 1000.0}s")
        except Exception as e:
            logging.error(
                f"Pydub failed to load audio from {type(audio_source)}: {e}", exc_info=True)
            # Clean up temp file if we created one
            if temp_audio_path_to_clean and os.path.exists(temp_audio_path_to_clean):
                try:
                    os.remove(temp_audio_path_to_clean)
                except OSError as ose:
                    logging.warning(
                        f"Pydub cleanup failed to remove temp file {temp_audio_path_to_clean}: {ose}")
            raise ValueError(
                f"Could not process audio file. Pydub error: {e}") from e

        processing_id = str(random.randint(0, 100000))
        ten_minutes_ms = TEN_MINUTES

        async def process_chunk(chunk_index, start_ms, end_ms):
            chunk_num = chunk_index + 1
            logging.debug(
                f"Processing chunk {chunk_num} ({start_ms / 1000.0:.2f}s to {end_ms / 1000.0:.2f}s) / Total Duration: {len(parts) / 1000.0:.2f}s")
            chunk_audio = parts[start_ms:end_ms]
            # Use a robust format like wav or flac for intermediate chunks if mp3 causes issues? Stick to mp3 for now.
            chunk_filename = f"{downloads_path()}/{processing_id}_chunk{chunk_num}.mp3"

            try:
                # Export the chunk to a temporary file for Whisper API
                with open(chunk_filename, "wb") as chunk_f:
                    chunk_audio.export(chunk_f, format="mp3")
                logging.debug(
                    f"Exported chunk {chunk_num} to {chunk_filename}")

                # Re-open the exported file in binary read mode for the API call
                with open(chunk_filename, "rb") as chunk_f_read:
                    # Pass the file object to small_file
                    result = await small_file(chunk_f_read, lang, response_format)
                logging.debug(
                    f"Chunk {chunk_num} processed successfully by small_file.")
                return result
            except Exception as exc:
                logging.error(
                    f"Chunk {chunk_num} ({start_ms}ms to {end_ms}ms) generated an exception during processing or API call: {exc}", exc_info=True)
                return None  # Indicate failure for this chunk
            finally:
                # Ensure temporary chunk file is deleted
                if os.path.exists(chunk_filename):
                    try:
                        os.remove(chunk_filename)
                        logging.debug(f"Removed chunk file {chunk_filename}")
                    except OSError as ose:
                        logging.warning(
                            f"Failed to remove chunk file {chunk_filename}: {ose}")

        with ThreadPoolExecutor() as executor:
            # Create futures with start/end times
            futures = {}
            for i, start_ms in enumerate(range(0, len(parts), ten_minutes_ms)):
                end_ms = min(start_ms + ten_minutes_ms, len(parts))
                if start_ms >= end_ms:
                    continue  # Skip zero-duration chunks if any
                future = executor.submit(process_chunk, i, start_ms, end_ms)
                futures[future] = i  # Map future back to original index

            # Prepare ordered results list
            num_chunks = math.ceil(len(parts) / ten_minutes_ms)
            # Handle case where audio length is zero or very small resulting in zero chunks
            if num_chunks == 0 and len(parts) > 0:
                num_chunks = 1
            elif num_chunks == 0:
                # continue with empty list
                logging.warning("Audio appears to have zero length.")
            ordered_results = [None] * num_chunks

            for future in as_completed(futures):
                index = futures[future]
                try:
                    result = future.result()
                    if index < len(ordered_results):
                        ordered_results[index] = result
                    else:
                        logging.error(
                            f"Index {index} out of bounds for ordered_results (size {len(ordered_results)}) for future {future}")
                except Exception as exc:
                    # Exception raised *by the task* (process_chunk) is caught by future.result()
                    # process_chunk should return None on error, so this path handles unexpected exceptions maybe?
                    logging.error(
                        f"Exception retrieving result for chunk index {index}: {exc}", exc_info=True)
                    # Result for this chunk remains None in ordered_results

            docs = ordered_results

        # Clean up the main temporary audio file if created
        if temp_audio_path_to_clean and os.path.exists(temp_audio_path_to_clean):
            try:
                os.remove(temp_audio_path_to_clean)
                logging.debug(
                    f"Removed temporary audio file: {temp_audio_path_to_clean}")
            except OSError as ose:
                logging.warning(
                    f"Could not remove temporary audio file {temp_audio_path_to_clean}: {ose}")

    else:  # File size <= AUDIO_SPLIT_BYTES
        processed_chunks = False
        logging.info("File size within limit, processing as a single file.")
        try:
            # Ensure file object is passed correctly and pointer is at start
            if file.seekable():
                file.seek(0)  # Ensure reading from the start

            single_result = await small_file(file, lang, response_format)
            docs = [single_result]
        except Exception as e:
            logging.error(
                f"Error during single file transcription: {e}", exc_info=True)
            docs = [None]  # Indicate error

    # --- Aggregation Logic ---
    final_result: Union[str, List[object]]

    # Filter out None results before processing/joining
    valid_docs = [doc for doc in docs if doc is not None]

    if not valid_docs:
        logging.warning("No successful transcription results obtained.")
        # Return appropriate empty result based on format
        if response_format == WHISPER_RESPONSE_FORMAT.TEXT:
            final_result = ""
        elif response_format == WHISPER_RESPONSE_FORMAT.SRT:
            final_result = ""
        elif response_format == WHISPER_RESPONSE_FORMAT.VTT:
            final_result = "WEBVTT\n\n"
        elif response_format in (WHISPER_RESPONSE_FORMAT.JSON, WHISPER_RESPONSE_FORMAT.VERBOSE_JSON):
            final_result = []
        else:
            final_result = ""  # Default empty
        return final_result  # Early exit

    # Process based on format
    if response_format == WHISPER_RESPONSE_FORMAT.TEXT:
        # Join text parts, ensuring they are strings
        final_result = " ".join(str(doc) for doc in valid_docs)
    elif response_format in (WHISPER_RESPONSE_FORMAT.SRT, WHISPER_RESPONSE_FORMAT.VTT):
        is_vtt = response_format == WHISPER_RESPONSE_FORMAT.VTT
        format_str: Literal['srt', 'vtt'] = 'vtt' if is_vtt else 'srt'
        # Combine if multiple chunks were processed OR if single chunk result needs format check
        if processed_chunks:
            # Pass the original ordered_results (potentially containing None) to the combiner
            # This allows calculating offset correctly based on chunk index.
            final_result = _combine_subtitle_chunks(
                docs, TEN_MINUTES, format_str)
        elif len(valid_docs) == 1:
            # Small file or only one valid chunk. Result should be a string.
            single_result_str = str(valid_docs[0])
            # Basic validation/cleanup for single subtitle file
            if is_vtt and not single_result_str.strip().startswith("WEBVTT"):
                logging.warning(
                    "Adding missing WEBVTT header to single VTT result.")
                final_result = "WEBVTT\n\n" + single_result_str.strip() + "\n\n"
            elif not is_vtt and re.match(r"^\s*WEBVTT", single_result_str):
                logging.warning(
                    "Removing WEBVTT header from single SRT result.")
                final_result = re.sub(
                    r"^\s*WEBVTT\s*\n+", "", single_result_str) + "\n\n"
            else:
                final_result = single_result_str  # Assume it's okay
            # Ensure final newline(s)
            if not final_result.endswith("\n\n"):
                if final_result.endswith("\n"):
                    final_result += "\n"
                else:
                    final_result += "\n\n"

        else:
            # No valid docs, should have been caught earlier, but as fallback:
            logging.error(
                f"Unexpected state for SRT/VTT aggregation. Valid docs: {len(valid_docs)}, processed_chunks: {processed_chunks}")

        if is_vtt:
            final_result = "WEBVTT\n\n" + final_result

    elif response_format in (WHISPER_RESPONSE_FORMAT.JSON, WHISPER_RESPONSE_FORMAT.VERBOSE_JSON):
        # Return list of results (assuming they are appropriate JSON objects/dicts from small_file)
        final_result = valid_docs
    else:
        # Fallback for any unexpected format
        logging.warning(
            f"Unhandled response format for aggregation: {response_format}. Joining as text.")
        final_result = " ".join(str(doc) for doc in valid_docs)

    return final_result


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
