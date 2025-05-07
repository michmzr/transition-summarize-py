import hashlib
import logging
import os
import tempfile

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
from app.utils.files import string_to_filename
from app.youtube.metadata import get_youtube_metadata
from app.youtube.transcriptions import download_transcription
yt_router = APIRouter(
    prefix="/youtube",
    tags=["youtube", "transcription", "summarization"],
    dependencies=[Depends(get_current_active_user)]
)


@yt_router.post("/transcribe", response_model=ApiProcessingResult)
def yt_transcription(
        request: Request,
        yt_request: YTVideoTranscribe,
        response: Response,
        current_user: User = Depends(get_current_active_user)
):
    """
    Transcribe a YouTube video.

    Args:
        request (Request): The FastAPI request object.
        yt_request (YTVideoTranscribe): The request body containing YouTube video details.

    Returns:
        ApiProcessingResult: The transcription result.
    Description:
        This endpoint transcribes a YouTube video based on the provided URL, language, and response format.
        It can return the result as plain text or JSON based on the Accept header.

    Raises:
        HTTPException: If there's an error during transcription.
    """
    process_id = None
    try:
        logging.info(f"yt transcribe - request details: {yt_request}")

        details = get_youtube_metadata(yt_request.url)
        logging.info(f"YT details: {details}")

        process_id = register_new_process(
            current_user,
            request_type=RequestType.YOUTUBE,
            request=request,
            request_data={
                "yt_request": yt_request.model_dump(),
                "yt_details": {"name": details.title, "channel": details.channel_url, "description": details.description}}
        )

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
        logging.info(f"Accept header: {accept_header}")
        ext = yt_request.response_format.value

        if accept_header == "text/plain":
            return PlainTextResponse(transcription)
        elif accept_header == "text/"+ext:
            # return as a file - encode name to be safe as filename
            video_name = details.title.replace(" ", "_")[:10]
            file_name = string_to_filename(video_name) + "." + ext
            logging.info(f"File name: {file_name}")

            # Save transcription as a temporary file
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp:
                temp.write(transcription.encode('utf-8'))
                temp.flush()
                return FileResponse(temp.name, media_type="text/"+ext, filename=file_name)
        else:
            return ApiProcessingResult(result=True, text=transcription)
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


@yt_router.post("/summarize", response_model=ApiProcessingResult)
def yt_summarize(
        request: Request,
        yt_request: YtVideoSummarize,
        response: Response,
        current_user: User = Depends(get_current_active_user)
):
    """
    Summarize a YouTube video.

    Args:
        request (Request): The FastAPI request object.
        yt_request (YtVideoSummarize): The request body containing YouTube video details and summarization options.

    Returns:
        ApiProcessingResult: The summarization result.

    Description:
        This endpoint transcribes a YouTube video and then summarizes the transcription.
        It can return the result as plain text or JSON based on the Accept header.

    Raises:
        HTTPException: If there's an error during transcription or summarization.
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
                yt_request.url, save_dir, yt_request.lang, WHISPER_RESPONSE_FORMAT.SRT)

        register_process_artifact(
            current_user, process_id,
            ProcessArtifactType.TRANSCRIPTION,
            transcription,
            ProcessArtifactFormat.TEXT, yt_request.lang)

        summarization = summarize(
            transcription, yt_request.type, yt_request.lang)
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
            return SummaryResult(summary=summarization)
    except Exception as e:
        logging.error(f"Error processing YouTube summarization: '{str(e)}'")

        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            result=False,
            error="Error processing YouTube summarization",
            text=str(e))


@yt_router.post("/details", response_model=YoutubeMetadata | ApiProcessingResult)
def yt_details(
        request: YtVideoInfoRequest,
        response: Response,
        current_user: User = Depends(get_current_active_user)
):
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
