import logging

from fastapi import APIRouter

from models import YtVideoRequest
from summary.utils import summarize
from transcribe.utils import yt_transcribe

router = APIRouter()

@router.post("/youtube/transcribe")
def yt_trans(request: YtVideoRequest):
    logging.info(f"yt transcribe - request details: {request}")

    result = yt_transcribe(request.url, "./downloads/YouTube")

    return {"result": result}


@router.post("/youtube/summarize")
def yt_summarize(request: YtVideoRequest):
    logging.info(f"yt summarize - Request details: {request}")

    transcription = yt_transcribe(request.url, "./downloads/YouTube")
    logging.debug(f"yt summarize - transcription ready")

    summarization = summarize(transcription, request.type)

    logging.debug(f"yt summarize - Result: \n{summarization}")

    return {"result": summarization}
