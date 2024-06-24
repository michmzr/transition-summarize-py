import logging

from fastapi import APIRouter

from models import YtVideoSummarize, YTVideoTranscribe
from summary.utils import summarize
from transcribe.utils import yt_transcribe

yt_router = APIRouter(prefix="/youtube", tags=["youtube", "transcription", "summarization"])


@yt_router.post("/transcribe")
def yt_transcription(request: YTVideoTranscribe):
    logging.info(f"yt transcribe - request details: {request}")

    result = yt_transcribe(request.url, "./downloads/YouTube")

    return {"result": result}


@yt_router.post("/summarize")
def yt_summarize(request: YtVideoSummarize):
    logging.info(f"yt summarize - Request details: {request}")

    transcription = yt_transcribe(request.url, "./downloads/YouTube")
    logging.debug(f"yt summarize - transcription ready")

    summarization = summarize(transcription, request.type, request.lang)

    logging.debug(f"yt summarize - Result: \n{summarization}")

    return {"result": summarization}
