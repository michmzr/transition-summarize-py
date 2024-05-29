import logging
import os
import random
from typing import BinaryIO
from fastapi import UploadFile, File
from langchain_community.document_loaders import YoutubeAudioLoader
from langchain_community.document_loaders.generic import GenericLoader
from langchain_community.document_loaders.parsers.audio import OpenAIWhisperParser
from openai import OpenAI
from pydub import AudioSegment

client = OpenAI()

def yt_transcribe(url, save_dir,):
    """
    Transcribe the videos to text

    inspiration: https://python.langchain.com/docs/integrations/document_loaders/youtube_audio/
    :param url: yt video url
    :param save_dir:
    :param local: set a flag to switch between local and remote parsing change this to True if you want to use local parsing
    :return: transcribed text without timestamps
    """
    logging.info(f"Processing url: {url}, save_dir: {save_dir}")

    # Transcribe the videos to text

    loader = GenericLoader(YoutubeAudioLoader([url], save_dir), OpenAIWhisperParser())
    docs = loader.load()

    logging.info("Ready!!!")

    # read all docs, get page_content and concanate
    result = [doc.page_content for doc in docs]

    return result


def transcribe(file: BinaryIO):
    """
    Transcribe audio file to text

    inspiration: https://python.langchain.com/docs/integrations/document_loaders/youtube_audio/
    :param file: audio file
    """
    logging.info(
        f"Transcribing audio file: {file}")


    # calculating total size of f in bytes
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

            # todo as a temp file
            chunk_filename = f"downloads/{processing_id}chunk_{i}_file_.mp3"
            chunk_file = chunk.export(chunk_filename, format="mp3")

            docs.append(small_file(chunk_file))

            logging.debug("---- Got another transcription chunk ----")

            os.remove(chunk_filename)
    else:
        docs = [small_file(file)]

    return " ".join(docs)


def small_file(file: BinaryIO):
    logging.info( f"Transcribing audio file using openai api: {file}")

    # todo language
    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        file=file,
        response_format="text",
    )
    #logging.debug(f"-------------------\nGot from OpenAI: \n{transcription}\n--------------------\n")
    return transcription