
from langchain_community.document_loaders import YoutubeAudioLoader
from langchain_community.document_loaders.generic import GenericLoader
from langchain_community.document_loaders.parsers.audio import OpenAIWhisperParserLocal, OpenAIWhisperParser
from pydantic import BaseModel
import logging

def transcribe(url, save_dir, local=False):
    """
    Transcribe the videos to text

    inspiration: https://python.langchain.com/docs/integrations/document_loaders/youtube_audio/
    :param url: yt video url
    :param save_dir:
    :param local: set a flag to switch between local and remote parsing change this to True if you want to use local parsing
    :return: transcribed text without timestamps
    """
    logging.info(f"Processing url: {url}, save_dir: {save_dir}, local: {local}")

    # Transcribe the videos to text
    if local:
        loader = GenericLoader(
            YoutubeAudioLoader([url], save_dir), OpenAIWhisperParserLocal()
        )
    else:
        loader = GenericLoader(YoutubeAudioLoader([url], save_dir), OpenAIWhisperParser())
    docs = loader.load()

    logging.info("Ready!!!")

    # read all docs, get page_content and concanate
    result = [doc.page_content for doc in docs]

    return result