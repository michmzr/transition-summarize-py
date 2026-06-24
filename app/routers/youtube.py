import hashlib
import logging
import os

from fastapi import APIRouter, Request, Depends, Response, status
from fastapi.responses import FileResponse
from starlette.responses import PlainTextResponse

from app.auth import get_current_active_user
from app.models import YtVideoSummarize, YTVideoTranscribe, YtVideoInfoRequest, YoutubeMetadata, SummaryResult, \
    ApiProcessingResult
from app.processing.processing import complete_process, process_failed, register_new_process, register_process_artifact, update_process_status
from app.schema.models import ProcessArtifactFormat, ProcessArtifactType, RequestStatus, RequestType
from app.schema.pydantic_models import CompletedProcess, User
from app.summary.summarization import summarize
from app.transcribe.transcription import yt_transcribe, WHISPER_RESPONSE_FORMAT
from app.youtube.metadata import get_youtube_metadata
from app.youtube.transcriptions import download_transcription
yt_router = APIRouter(
    prefix="/youtube",
    tags=["youtube", "transcription", "summarization"],
    dependencies=[Depends(get_current_active_user)]
)


@yt_router.post(
    "/transcribe",
    response_model=ApiProcessingResult,
    responses={
        200: {
            "description": "Transcription result. Content type depends on the `Accept` request header.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": True, "error": None, "transcription": "1\n00:00:01,000 --> 00:00:05,000\nHello world", "format": "srt"},
                },
                "text/plain": {
                    "schema": {"type": "string"},
                    "example": "1\n00:00:01,000 --> 00:00:05,000\nHello world",
                },
            },
        },
        500: {
            "description": "Internal server error during transcription.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": False, "error": "Internal server error: <details>", "text": None},
                }
            },
        },
    },
)
def yt_transcription(
        request: Request,
        yt_request: YTVideoTranscribe,
        response: Response,
        current_user: User = Depends(get_current_active_user)
):
    """
    Transcribe a YouTube video.

    The response format is determined by the `Accept` request header:
    - `application/json` (default): JSON object with transcription result and metadata.
    - `text/plain`: Raw transcription text.

    Args:
        yt_request (YTVideoTranscribe): YouTube video URL, language code, and desired response format.

    Raises:
        HTTP 500: If an unexpected error occurs during transcription.
    """
    process_id = None
    try:
        logging.info(f"yt transcribe - request details: {yt_request}")

        process_id = register_new_process(
            current_user,
            request_type=RequestType.YOUTUBE,
            request=request,
            request_data={
                "yt_request": yt_request.model_dump()}
        )

        yt_metadata = None
        try:
            yt_metadata = get_youtube_metadata(yt_request.url)
        except Exception as metadata_error:
            logging.warning(
                f"Could not fetch YouTube metadata for transcription: '{metadata_error}'")

        save_dir = save_dir_path(yt_request.url)
        transcription = yt_transcribe(
            yt_request.url,
            save_dir,
            yt_request.lang,
            yt_request.response_format)

        update_process_status(process_id, CompletedProcess(
            user_id=current_user.id,
            status=RequestStatus.COMPLETED,
            result=transcription,
            result_format=ProcessArtifactFormat.TEXT,
            lang=yt_request.lang,
            type=ProcessArtifactType.TRANSCRIPTION
        ))

        # Get the Accept header from the request
        accept_header = request.headers.get("Accept", "application/json")

        # If the Accept header is "text/plain", return plain text
        if accept_header == "text/plain":
            return PlainTextResponse(transcription)
        else:
            metadata_dict = yt_metadata.model_dump(exclude={"subtitles"}) if yt_metadata else None
            return ApiProcessingResult(
                result=True, error=None,
                transcription=transcription,
                format=yt_request.response_format,
                metadata=metadata_dict)
    except Exception as e:
        logging.error(f"Error processing YouTube transcription: {str(e)}")

        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            result=False,
            error=f"Internal server error: {str(e)}",
        )


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


def _trim_metadata_text(text: str, max_length: int = 2000) -> str:
    cleaned_text = " ".join(text.split())
    if len(cleaned_text) <= max_length:
        return cleaned_text

    return f"{cleaned_text[:max_length].rstrip()}..."


def build_youtube_summary_input(
        transcription: str,
        metadata: YoutubeMetadata | None
) -> str:
    if not metadata:
        return transcription

    metadata_lines = []
    if metadata.title:
        metadata_lines.append(f"Title: {metadata.title}")
    if metadata.duration_string:
        metadata_lines.append(f"Duration: {metadata.duration_string}")
    elif metadata.duration:
        metadata_lines.append(f"Duration: {metadata.duration} seconds")
    if metadata.description:
        metadata_lines.append(
            f"Description: {_trim_metadata_text(metadata.description)}")

    if not metadata_lines:
        return transcription

    return "\n".join([
        "Video metadata:",
        *metadata_lines,
        "",
        "Transcript:",
        transcription
    ])


@yt_router.post(
    "/summarize",
    response_model=SummaryResult,
    responses={
        200: {
            "description": "Summarization result. Content type depends on the `Accept` request header.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/SummaryResult"},
                    "example": {"summary": "The video covers the main highlights of the event..."},
                },
                "text/plain": {
                    "schema": {"type": "string"},
                    "example": "The video covers the main highlights of the event...",
                },
                "text/srt": {
                    "schema": {"type": "string", "format": "binary"},
                    "example": "1\n00:00:01,000 --> 00:00:05,000\nHello world",
                },
            },
        },
        500: {
            "description": "Internal server error during transcription or summarization.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": False, "error": "Error processing YouTube summarization", "text": "<error details>"},
                }
            },
        },
    },
)
def yt_summarize(
        request: Request,
        yt_request: YtVideoSummarize,
        response: Response,
        current_user: User = Depends(get_current_active_user)
):
    """
    Transcribe and summarize a YouTube video.

    The response format is determined by the `Accept` request header:
    - `application/json` (default): JSON object containing the generated summary.
    - `text/plain`: Raw summary text.
    - `text/srt`: SRT subtitle file of the video transcription used for summarization.

    Args:
        yt_request (YtVideoSummarize): YouTube video URL, summarization type, language code, and whether to use existing YT transcription.

    Raises:
        HTTP 500: If an unexpected error occurs during transcription or summarization.
    """

    try:
        logging.info(f"yt summarize - Request details: {yt_request:}")

        process_id = register_new_process(
            current_user,
            RequestType.YOUTUBE,
            request=request,
            request_data={
                "yt_request": yt_request.model_dump()}
        )

        save_dir = save_dir_path(yt_request.url)
        yt_metadata = None

        try:
            yt_metadata = get_youtube_metadata(yt_request.url)
        except Exception as metadata_error:
            logging.warning(
                f"Could not fetch YouTube metadata for summarization: '{metadata_error}'")

        transcription = None

        if yt_request.use_yt_transcription:
            logging.info(
                f" Using YT transcription: '{yt_request.url}' for language '{yt_request.lang}'")
            transcription = download_transcription(
                yt_request.url, yt_request.lang, save_dir)
            logging.debug(
                f"Downloaded transcription\n-----------------\n\n{transcription}\n-----------------\n\n")

        if not transcription:
            transcription = yt_transcribe(
                yt_request.url, save_dir, yt_request.lang,
                WHISPER_RESPONSE_FORMAT.TEXT)

        register_process_artifact(
            current_user, process_id,
            ProcessArtifactType.TRANSCRIPTION,
            transcription,
            ProcessArtifactFormat.TEXT, yt_request.lang)

        summary_input = build_youtube_summary_input(
            transcription, yt_metadata)
        summarization = summarize(
            summary_input, yt_request.type, yt_request.lang)
        register_process_artifact(
            current_user, process_id,
            ProcessArtifactType.SUMMARY,
            summarization,
            ProcessArtifactFormat.TEXT, yt_request.lang)

        logging.debug(f"yt summarize - Result: \n{summarization}")

        complete_process(process_id)

        # Get the Accept header from the request
        accept_header = request.headers.get("Accept", "application/json")

        # If the Accept header is "text/plain", return plain text
        if accept_header == "text/plain":
            return PlainTextResponse(summarization)
        elif accept_header == "text/srt":
            # return as a file
            return FileResponse(transcription, media_type="text/srt")
        else:
            metadata_dict = yt_metadata.model_dump(exclude={"subtitles"}) if yt_metadata else None
            return SummaryResult(summary=summarization, metadata=metadata_dict)
    except Exception as e:
        logging.error(f"Error processing YouTube summarization: '{str(e)}'")

        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            result=False,
            error="Error processing YouTube summarization",
            text=str(e))


@yt_router.post(
    "/details",
    response_model=YoutubeMetadata | ApiProcessingResult,
    responses={
        200: {
            "description": "YouTube video metadata.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/YoutubeMetadata"},
                    "example": {
                        "title": "Example Video",
                        "full_title": "Example Video — Full Title",
                        "filesize": None,
                        "duration": 120.0,
                        "duration_string": "2:00",
                        "description": "Video description here.",
                        "channel_url": "https://www.youtube.com/@example",
                        "language": "en",
                        "subtitles": {},
                        "available_transcriptions": ["en", "pl"],
                        "upload_date": "2024-01-15T00:00:00",
                        "thumbnail": "https://i.ytimg.com/vi/example/maxresdefault.jpg",
                    },
                }
            },
        },
        500: {
            "description": "Internal server error while fetching video metadata.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": False, "error": "Error processing YouTube details extraction: <details>", "text": "<details>"},
                }
            },
        },
    },
)
def yt_details(
        request: YtVideoInfoRequest,
        response: Response,
        current_user: User = Depends(get_current_active_user)
):
    """
    Get detailed metadata for a YouTube video.

    Returns a `YoutubeMetadata` JSON object on success, including title, duration,
    description, channel URL, available subtitles and transcription languages, upload date, and thumbnail URL.

    Args:
        request (YtVideoInfoRequest): Request body containing the YouTube video URL.

    Raises:
        HTTP 500: If an unexpected error occurs while fetching video metadata.
    """

    try:
        logging.info(f"Getting YT video details: {request.url}")

        metadata = get_youtube_metadata(request.url)

        return metadata
    except Exception as e:
        logging.error(f"Error fetching YouTube video details: {str(e)}")

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            result=False,
            error=f"Error processing YouTube details extraction: {str(e)}",
            text=str(e))
