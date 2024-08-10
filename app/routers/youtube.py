import hashlib
import logging

from fastapi import APIRouter

from models import YtVideoSummarize, YTVideoTranscribe
from summary.summarization import summarize
from transcribe.transcription import yt_transcribe, WHISPER_RESPONSE_FORMAT

yt_router = APIRouter(prefix="/youtube", tags=["youtube", "transcription", "summarization"])


@yt_router.post("/transcribe")
def yt_transcription(request: YTVideoTranscribe):
    logging.info(f"yt transcribe - request details: {request}")

    save_dir = save_dir_path(request.url)
    result = yt_transcribe(
        request.url,
        save_dir,
        request.lang,
        request.response_format)

    return {"result": result}


def save_dir_path(url):
    hash_object = hashlib.md5(url.encode())
    hash_hex = hash_object.hexdigest()
    save_dir = f"./downloads/yt/{hash_hex}/"
    return save_dir


@yt_router.post("/summarize")
def yt_summarize(request: YtVideoSummarize):
    logging.info(f"yt summarize - Request details: {request}")

    save_dir = save_dir_path(request.url)
    transcription = yt_transcribe(request.url,
                                  save_dir,
                                  request.lang,
                                  WHISPER_RESPONSE_FORMAT.SRT)

    summarization = summarize(transcription, request.type, request.lang)

    logging.debug(f"yt summarize - Result: \n{summarization}")

    return {"result": summarization}
