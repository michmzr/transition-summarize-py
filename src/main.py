import logging

from fastapi import FastAPI
import static_ffmpeg
from langchain_community.document_loaders import YoutubeAudioLoader
from langchain_community.document_loaders.generic import GenericLoader
from langchain_community.document_loaders.parsers.audio import OpenAIWhisperParserLocal, OpenAIWhisperParser
from pydantic import BaseModel

app = FastAPI()

static_ffmpeg.add_paths()


class YtVideoRequest(BaseModel):
    url: str

@app.post("/youtube/transcribe")
async def root(request: YtVideoRequest):
    print("downloading...")

    # accept in json body video ur in FastAPI
    logging.info(f"Request details: {request.url}")

    # inspiration: https://python.langchain.com/docs/integrations/document_loaders/youtube_audio/
    urls = [request.url]

    # Directory to save audio files
    save_dir = "./downloads/YouTube"

    # set a flag to switch between local and remote parsing
    # change this to True if you want to use local parsing
    local = False

    # Transcribe the videos to text
    if local:
        loader = GenericLoader(
            YoutubeAudioLoader(urls, save_dir), OpenAIWhisperParserLocal()
        )
    else:
        loader = GenericLoader(YoutubeAudioLoader(urls, save_dir), OpenAIWhisperParser())
    docs = loader.load()

    # read all docs, get page_content and concanate
    result = [doc.page_content for doc in docs]
    print("Ready!!!")

    return {"result": result}