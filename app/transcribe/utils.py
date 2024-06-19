import logging
import os
import random
from enum import Enum
from functools import lru_cache
from typing import BinaryIO

from langchain_community.document_loaders import YoutubeAudioLoader
from langchain_community.document_loaders.generic import GenericLoader
from langchain_community.document_loaders.parsers.audio import OpenAIWhisperParser
from pydub import AudioSegment


class LANG_CODE(str, Enum):
    ENGLISH = "en"
    POLISH = "pl"


def yt_transcribe(url: str, save_dir: str):
    """
    Transcribe the videos to text

    inspiration: https://python.langchain.com/docs/integrations/document_loaders/youtube_audio/
    :param url: yt video url
    :param save_dir:
    """
    logging.info(f"Processing url: {url}, save_dir: {save_dir}")

    from main import get_settings
    loader = GenericLoader(YoutubeAudioLoader([url], save_dir),
                           OpenAIWhisperParser(api_key=get_settings().openai_api_key))
    docs = loader.load()

    logging.info("Ready!!!")

    # read all docs, get page_content and concanate
    result = [doc.page_content for doc in docs]

    return result


def transcribe(file: BinaryIO, lang: LANG_CODE):
    """
    Transcribe audio file to text

    inspiration: https://python.langchain.com/docs/integrations/document_loaders/youtube_audio/
    :param lang: Lang code
    :param file: audio file
    """
    logging.info(
        f"Transcribing audio file: {file}, lang: {lang}")

    file_stats = os.stat(file.name)
    logging.debug("File stats: " + str(file_stats))
    size = file_stats.st_size

    logging.debug(f"File size: {size}")

    docs = []
    if size > 24000000:
        logging.debug("File size > 24MB, splitting audio file into 10min parts")

        ten_minutes = 10 * 60 * 1000

        parts = AudioSegment.from_file(file)

        processing_id = str(random.randint(0, 100000))

        # todo parallelize
        for i in range(0, len(parts), ten_minutes):
            logging.debug(f"Processing chunk {i} to {i + ten_minutes} / {len(parts)}")
            chunk = parts[i:i + ten_minutes]

            chunk_filename = f"downloads/{processing_id}chunk_{i}_file_.mp3"
            chunk_file = chunk.export(chunk_filename, format="mp3")

            docs.append(small_file(chunk_file, lang))

            logging.debug("---- Got another transcription chunk ----")

            os.remove(chunk_filename)
    else:
        docs = [small_file(file, lang)]

    return " ".join(docs)


@lru_cache
def small_file(file: BinaryIO, lang: LANG_CODE):
    """
    :param file: binary file
    :param lang:  language: The language of the input audio. Supplying the input language in
              [ISO-639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes) format will
              improve accuracy and latency.
    :return:
    """
    logging.info(f"Transcribing audio file using openai api: {file}, with lang: {lang}")

    from main import client
    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        file=file,
        language=lang.value,
        response_format="text",
    )

    return transcription
