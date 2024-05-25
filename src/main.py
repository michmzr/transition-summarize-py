import logging

from fastapi import FastAPI
import static_ffmpeg
from langchain_community.document_loaders import YoutubeAudioLoader
from langchain_community.document_loaders.generic import GenericLoader
from langchain_community.document_loaders.parsers.audio import OpenAIWhisperParserLocal, OpenAIWhisperParser
from pydantic import BaseModel

from summary.summary import summarize, SUMMARIZATON_TYPE
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
    # type is optional, default is TLDR
    type: str = "TLDR"


@app.post("/youtube/transcribe")
async def root(request: YtVideoRequest):
    logging.info(f"yt transcribe - request details: {request}")

    result = transcribe(request.url, "./downloads/YouTube")

    return {"result": result}


@app.post("/youtube/summarize")
async def root(request: YtVideoRequest):
    logging.info(f"yt summarize - Request details: {request}")

    transcription = transcribe(request.url, "./downloads/YouTube")
    logging.debug(f"yt summarize - transcription ready")

    summarization = summarize(transcription, request.type)

    logging.debug(f"yt summarize - Result: \n{summarization}")

    return {"result": summarization}
