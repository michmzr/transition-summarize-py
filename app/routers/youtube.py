import hashlib
import logging

from fastapi import APIRouter, Request
from starlette.responses import PlainTextResponse

from models import YtVideoSummarize, YTVideoTranscribe, YtVideoInfoRequest, YoutubeMetadata, SummaryResult, \
    TranscriptionResult
from summary.summarization import summarize
from transcribe.transcription import yt_transcribe, WHISPER_RESPONSE_FORMAT
from youtube.metadata import get_youtube_metadata

yt_router = APIRouter(prefix="/youtube", tags=["youtube", "transcription", "summarization"])


@yt_router.post("/transcribe", response_model=TranscriptionResult)
def yt_transcription(request: Request, yt_request: YTVideoTranscribe):
    """
    Transcribe a YouTube video.

    Args:
        request (Request): The FastAPI request object.
        yt_request (YTVideoTranscribe): The request body containing YouTube video details.

    Returns:
        TranscriptionResult: The transcription result.
        
    Description:
        This endpoint transcribes a YouTube video based on the provided URL, language, and response format.
        It can return the result as plain text or JSON based on the Accept header.

    Raises:
        HTTPException: If there's an error during transcription.
    """
    logging.info(f"yt transcribe - request details: {yt_request}")

    save_dir = save_dir_path(yt_request.url)
    result = yt_transcribe(
        yt_request.url,
        save_dir,
        yt_request.lang,
        yt_request.response_format)

    # Get the Accept header from the request
    accept_header = request.headers.get("Accept", "application/json")

    # If the Accept header is "text/plain", return plain text
    if accept_header == "text/plain":
        return PlainTextResponse(result)
    else:
        return TranscriptionResult(result=True, error=None, transcription=result, format=yt_request.response_format)


def save_dir_path(url):
    """
    Generate a save directory path based on the URL's MD5 hash.

    Args:
        url (str): The URL to hash.

    Returns:
        str: The generated save directory path.
    """
    hash_object = hashlib.md5(url.encode())
    hash_hex = hash_object.hexdigest()
    save_dir = f"./downloads/yt/{hash_hex}/"
    return save_dir


@yt_router.post("/summarize", response_model=SummaryResult)
def yt_summarize(request: Request, yt_request: YtVideoSummarize):
    """
    Summarize a YouTube video.

    Args:
        request (Request): The FastAPI request object.
        yt_request (YtVideoSummarize): The request body containing YouTube video details and summarization options.

    Returns:
        SummaryResult: The summarization result.
        
    Description:
        This endpoint transcribes a YouTube video and then summarizes the transcription.
        It can return the result as plain text or JSON based on the Accept header.

    Raises:
        HTTPException: If there's an error during transcription or summarization.
    """
    logging.info(f"yt summarize - Request details: {yt_request:}")

    save_dir = save_dir_path(yt_request.url)
    transcription = yt_transcribe(yt_request.url,
                                  save_dir,
                                  yt_request.lang,
                                  WHISPER_RESPONSE_FORMAT.SRT)

    summarization = summarize(transcription, yt_request.type, yt_request.lang)

    logging.debug(f"yt summarize - Result: \n{summarization}")

    # Get the Accept header from the request
    accept_header = request.headers.get("Accept", "application/json")

    # If the Accept header is "text/plain", return plain text
    if accept_header == "text/plain":
        return PlainTextResponse(summarization)
    else:
        return SummaryResult(summary=summarization)


@yt_router.post("/details", response_model=YoutubeMetadata)
def yt_details(request: YtVideoInfoRequest):
    """
    Get detailed metadata for a YouTube video.

    Args:
        request (YtVideoInfoRequest): The request object containing the YouTube video URL.

    Returns:
        YoutubeMetadata: Detailed metadata of the YouTube video, including:
            - title: The title of the video.
            - full_title: The full title of the video.
            - filesize: The size of the video file (if available).
            - duration: The duration of the video in seconds.
            - duration_string: The duration of the video as a formatted string.
            - description: The description of the video.
            - channel_url: The URL of the channel that uploaded the video.
            - language: The primary language of the video (if available).
            - subtitles: A dictionary of available subtitles, keyed by language code.
            - available_transcriptions: A list of available transcription language codes.
            - upload_date: The date the video was uploaded.
            - thumbnail: The URL of the video thumbnail.
    
    Description:
        This endpoint retrieves detailed metadata for a YouTube video using the provided URL.

    Raises:
        HTTPException: If there's an error fetching the video metadata.
    """
    logging.info(f"YT video details: {request.url}")

    return get_youtube_metadata(request.url)
