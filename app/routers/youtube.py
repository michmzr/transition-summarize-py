from pydantic import BaseModel
import logging

from main import app
from summary.utils import summarize
from transcribe.utils import yt_transcribe


class YtVideoRequest(BaseModel):
    url: str
    # type is optional, default is TLDR
    type: str = "TLDR"


@app.post("/youtube/transcribe")
def yt_trans(request: YtVideoRequest):
    logging.info(f"yt transcribe - request details: {request}")

    result = yt_transcribe(request.url, "./downloads/YouTube")

    return {"result": result}


@app.post("/youtube/summarize")
def yt_summarize(request: YtVideoRequest):
    logging.info(f"yt summarize - Request details: {request}")

    transcription = yt_transcribe(request.url, "./downloads/YouTube")
    logging.debug(f"yt summarize - transcription ready")

    summarization = summarize(transcription, request.type)

    logging.debug(f"yt summarize - Result: \n{summarization}")

    return {"result": summarization}
