import logging

from fastapi import FastAPI
import static_ffmpeg
from langchain_community.document_loaders import YoutubeAudioLoader
from langchain_community.document_loaders.generic import GenericLoader
from langchain_community.document_loaders.parsers.audio import OpenAIWhisperParserLocal, OpenAIWhisperParser
from pydantic import BaseModel

from yt.transcription import transcribe

app = FastAPI()

static_ffmpeg.add_paths()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)


class YtVideoRequest(BaseModel):
    url: str


@app.post("/youtube/transcribe")
async def root(request: YtVideoRequest):
    logging.info(f"Request details: {request.url}")

    result = transcribe(request.url, "./downloads/YouTube")

    return {"result": result}
