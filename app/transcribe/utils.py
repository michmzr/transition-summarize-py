import logging
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


def transcribe(file: UploadFile):
    """
    Transcribe audio file to text

    inspiration: https://python.langchain.com/docs/integrations/document_loaders/youtube_audio/
    :param file: audio file
    """
    logging.info(
        f"Transcribing audio file: {file.filename}, content_type: {file.content_type} - file size: {len(file.file.size)}")

    docs = []

    tempFile = file.file

    if tempFile.size > 24000000:
        logging.info("File size > 24MB, splitting audio file into 10min parts")

        ten_minutes = 10 * 60 * 1000

        parts = AudioSegment.from_file(tempFile)
        # Iterate over 10 minutes
        for i in range(0, len(parts), ten_minutes):
            chunk = parts[i:i + ten_minutes]

            # todo consider context problems when chunking?
            chunk_file = chunk.export("good_morning_10.mp3", format="mp3")

            docs += small_file(chunk_file)
    else:
        docs = small_file(tempFile)

    return docs

def small_file(file):
    logging.info( f"Transcribing audio file: {file.filename},  file size: {file.file}")

    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        file=file,
        response_format="text",

    )

    return transcription