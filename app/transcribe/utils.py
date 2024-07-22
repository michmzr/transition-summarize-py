import logging
import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
from typing import BinaryIO
from typing import cast, Literal, Union

from langchain_community.document_loaders.generic import GenericLoader
from langchain_community.document_loaders.parsers.audio import OpenAIWhisperParser
from pydub import AudioSegment

from cache import conditional_lru_cache
from youtube.loader import YoutubeAudioLoader

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
    from main import get_settings
    return get_settings().data_dir


def convert_response_format(format: WHISPER_RESPONSE_FORMAT) -> Union[
    Literal["json", "text", "srt", "verbose_json", "vtt"], None]:
    return cast(Union[
                    Literal["json", "text", "srt", "verbose_json", "vtt"], None], format.value)


@conditional_lru_cache
def yt_transcribe(url: str,
                  save_dir: str,
                  lang: LANG_CODE = LANG_CODE.ENGLISH,
                  response_format: WHISPER_RESPONSE_FORMAT = WHISPER_RESPONSE_FORMAT.TEXT,
                  ):
    """
    Transcribe the videos to text

    inspiration: https://python.langchain.com/docs/integrations/document_loaders/youtube_audio/
    :param url: yt video url
    :param save_dir:
    """
    logging.info(f"Processing url: {url}, save_dir: {save_dir}, lang: {lang}, response_format: {response_format}")

    from main import get_settings

    proxy_servers = get_settings().proxy_servers.split(",") if get_settings().proxy_servers else None

    loader = GenericLoader(YoutubeAudioLoader([url], save_dir, proxy_servers),
                           OpenAIWhisperParser(api_key=get_settings().openai_api_key,
                                               language=lang.value,
                                               response_format=convert_response_format(response_format)
                                               ))
    docs = loader.load()

    logging.info("Ready!!!")

    # read all docs, get page_content and concanate
    result = [doc.page_content for doc in docs]

    return result


def transcribe(file: BinaryIO,
               lang: LANG_CODE = LANG_CODE.ENGLISH,
               response_format: WHISPER_RESPONSE_FORMAT = WHISPER_RESPONSE_FORMAT.TEXT):
    """
    Transcribe audio file to text

    inspiration: https://python.langchain.com/docs/integrations/document_loaders/youtube_audio/
    :param lang: Lang code
    :param file: audio file
    """
    logging.info(f"Transcribing audio file: {file}, lang: {lang}")

    file_stats = os.stat(file.name)
    logging.debug("File stats: " + str(file_stats))
    size = file_stats.st_size

    logging.debug(f"File size: {size}")

    docs = []
    if size > AUDIO_SPLIT_BYTES:
        logging.debug("File size > 24MB, splitting audio file into 10min parts")

        ten_minutes = TEN_MINUTES
        parts = AudioSegment.from_file(file)
        processing_id = str(random.randint(0, 100000))

        def process_chunk(i):
            logging.debug(f"Processing chunk {i} to {i + ten_minutes} / {len(parts)}")
            chunk = parts[i:i + ten_minutes]
            chunk_filename = f"{downloads_path()}/{processing_id}chunk_{i}_file_.mp3"
            chunk_file = chunk.export(chunk_filename, format="mp3")
            result = small_file(chunk_file, lang, response_format)
            os.remove(chunk_filename)
            return result

        with ThreadPoolExecutor() as executor:
            future_to_index = {executor.submit(process_chunk, i): i for i in range(0, len(parts), ten_minutes)}
            ordered_results = [None] * len(future_to_index)
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    ordered_results[index // ten_minutes] = result
                except Exception as exc:
                    logging.error(f"Chunk {index} generated an exception: {exc}")

        docs = ordered_results
    else:
        docs = [small_file(file, lang, response_format)]

    return " ".join(docs)


@conditional_lru_cache
def small_file(file: BinaryIO,
               lang: LANG_CODE = LANG_CODE.ENGLISH,
               response_format: WHISPER_RESPONSE_FORMAT = WHISPER_RESPONSE_FORMAT.TEXT
               ):
    """
    :param file: binary file
    :param lang:  language: The language of the input audio. Supplying the input language in
              [ISO-639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes) format will
              improve accuracy and latency.
    :return:
    """
    logging.info(
        f"Transcribing audio file using openai api: {file}, with lang: {lang}, response_format: {response_format}")

    from main import client
    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        file=file,
        language=lang.value,
        response_format=convert_response_format(response_format),
    )

    return transcription
