import hashlib
import logging
import os
import tempfile

from fastapi import APIRouter, HTTPException, Request, Depends, Response, status, UploadFile
from fastapi.responses import FileResponse
from starlette.responses import PlainTextResponse
from tempfile import SpooledTemporaryFile

from app.auth import get_current_active_user
from app.models import YtVideoSummarize, YTVideoTranscribe, YtVideoInfoRequest, YoutubeMetadata, SummaryResult, \
    ApiProcessingResult
from app.processing.processing import complete_process, process_failed, register_new_process, register_process_artifact, update_process_status
from app.routers.audio import transcribe_uploaded_file
from app.schema.models import ProcessArtifactFormat, ProcessArtifactType, RequestStatus, RequestType
from app.schema.pydantic_models import CompletedProcess, User
from app.summary.summarization import summarize
from app.transcribe.transcription import download_and_extract_audio_from_link, transcribe
from app.utils.files import string_to_filename
from app.youtube.metadata import get_youtube_metadata
from app.youtube.transcriptions import download_transcription_from_yt

yt_router = APIRouter(
    prefix="/youtube",
    tags=["youtube", "transcription", "summarization"],
    dependencies=[Depends(get_current_active_user)]
)


@yt_router.post("/transcribe")
async def yt_transcription(
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
        Various responses based on Accept header:
        - PlainTextResponse: If Accept header is "text/plain"
        - FileResponse: If Accept header is "text/<format>"
        - ApiProcessingResult: For other Accept headers and error cases
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
        logging.debug(f"YT details: {details}")

        process_id = register_new_process(
            current_user,
            request_type=RequestType.YOUTUBE,
            request=request,
            request_data={
                "yt_request": yt_request.model_dump(),
                "yt_details": {"name": details.title, "channel": details.channel_url, "description": details.description}}
        )

        save_dir = save_dir_path(yt_request.url)

        transcription = None
        if yt_request.use_yt_transcription:
            logging.info(f"Using YT transcription: {yt_request.url}")

            transcription = download_transcription_from_yt(
                yt_request.url, yt_request.lang)

        if not transcription:
            logging.info(f"Using Whisper transcription: {yt_request.url}")

            transcription = await download_audio_and_transcribe(
                yt_request.url, save_dir, process_id, yt_request.lang, yt_request.response_format)

        if not transcription:
            process_failed(
                process_id, "Failed to obtain transcription from both YouTube and Whisper")
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return ApiProcessingResult(
                error="Failed to obtain transcription from both YouTube and Whisper",
            )

        logging.info(
            f"Transcription generated with length: {len(transcription)}")

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
            file_name = filename_from_yt_details(details) + "." + ext
            logging.info(f"File name: {file_name}")

            # Save transcription as a temporary file
            return create_temp_for_response(file_name, ext, transcription)
        else:
            return ApiProcessingResult(result=transcription)
    except Exception as e:
        logging.error(f"Error processing YouTube transcription: {str(e)}")

        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            error=f"Internal server error: {str(e)}",
        )


def filename_from_yt_details(details: YoutubeMetadata):
    video_name = details.title.replace(" ", "_")[:10]
    file_name = string_to_filename(video_name)
    return file_name


def create_temp_for_response(name: str, ext: str, content: str):
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp:
        temp.write(content.encode('utf-8'))
        temp.flush()
        # Map extension to proper MIME type
        media_type = "text/plain"
        if ext == "md":
            media_type = "text/markdown"
        elif ext == "srt":
            media_type = "text/srt"
        else:
            media_type = f"text/{ext}"
        # Ensure the filename is correct, without duplicate extension
        filename = name if name.endswith(f".{ext}") else f"{name}.{ext}"
        return FileResponse(temp.name, media_type=media_type, filename=filename)


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


async def download_audio_and_transcribe(url: str, save_dir: str, process_id: str, lang: str, response_format):
    """
    Download audio from YouTube URL and transcribe it using Whisper.

    Args:
        url (str): YouTube URL to download audio from
        save_dir (str): Directory to save the downloaded audio
        process_id (str): Process ID for error handling
        lang (str): Language code for transcription
        response_format: Response format for transcription

    Returns:
        str: The transcription text

    Raises:
        HTTPException: If audio download or transcription fails
    """
    audio_file = download_and_extract_audio_from_link(url, save_dir)

    if not audio_file:
        process_failed(
            process_id, f"Failed to download audio from the YouTube video - url: {url}")
        raise HTTPException(
            status_code=500, detail=f"Failed to download audio from the YouTube video - url: {url}")

    # Create a temporary file and prepare a UploadFile from it
    temp_file = SpooledTemporaryFile()
    with open(audio_file, 'rb') as f:
        temp_file.write(f.read())
    temp_file.seek(0)

    # Create UploadFile with the correct filename
    filename = os.path.basename(str(audio_file))
    mock_upload_file = UploadFile(
        file=temp_file,
        filename=filename
    )

    try:
        transcription = await transcribe_uploaded_file(
            mock_upload_file, lang, response_format)
        return transcription
    finally:
        # Clean up resources
        await mock_upload_file.close()
        temp_file.close()
        os.remove(audio_file)


@yt_router.post("/summarize", response_model=SummaryResult | ApiProcessingResult)
async def yt_summarize(
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
        Various responses based on Accept header:
        - PlainTextResponse: If Accept header is "text/plain"
        - FileResponse: If Accept header is "text/srt"
        - SummaryResult: For other Accept headers
        - ApiProcessingResult: For error cases

    Description:
        This endpoint transcribes a YouTube video and then summarizes the transcription.
        It can return the result as plain text or JSON based on the Accept header.

    Raises:
        HTTPException: If there's an error during transcription or summarization.
    """

    try:
        logging.info(f"yt summarize - Request details: {yt_request:}")

        details = get_youtube_metadata(yt_request.url)

        process_id = register_new_process(
            current_user,
            RequestType.YOUTUBE,
            request=request,
            request_data={
                "yt_request": yt_request.model_dump(),
                "yt_details": {"name": details.title, "channel": details.channel_url, "description": details.description}}
        )

        save_dir = save_dir_path(yt_request.url)

        transcription = None

        if yt_request.use_yt_transcription:
            logging.info(
                f" Using YT transcription: '{yt_request.url}' for language '{yt_request.lang}'")
            transcription = download_transcription_from_yt(
                yt_request.url, yt_request.lang)
            if transcription:
                logging.debug(
                    f"Downloaded transcription with length: {len(transcription)}")

        if not transcription:
            logging.info(
                f"Using Whisper transcription: '{yt_request.url}' for language '{yt_request.lang}'")
            transcription = await download_audio_and_transcribe(
                yt_request.url, save_dir, process_id, yt_request.lang, yt_request.response_format)

        if not transcription:
            process_failed(
                process_id, "Failed to obtain transcription from both YouTube and Whisper")
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return ApiProcessingResult(
                error="Failed to obtain transcription from both YouTube and Whisper",
            )

        register_process_artifact(
            current_user, process_id,
            ProcessArtifactType.TRANSCRIPTION,
            transcription,
            ProcessArtifactFormat.TEXT, yt_request.lang)

        summarization = await summarize(
            transcription, yt_request.type, yt_request.lang)
        register_process_artifact(
            current_user, process_id,
            ProcessArtifactType.SUMMARY,
            summarization,
            ProcessArtifactFormat.TEXT, yt_request.lang)

        if not summarization:
            raise HTTPException(
                status_code=500, detail="Summarization not found or empty")

        logging.info(
            f"Summarization generated with length: {len(summarization)}")
        logging.debug(
            f"yt summarize - Result: \n{summarization}\n")

        complete_process(process_id)

        # Get the Accept header from the request
        accept_header = request.headers.get("Accept", "application/json")

        if accept_header == "text/plain":
            return PlainTextResponse(summarization)
        elif accept_header == "text/markdown":
            file_name = filename_from_yt_details(details) + ".md"
            logging.info(f"File name: {file_name}")

            return create_temp_for_response(file_name, "md", summarization)
        else:
            return SummaryResult(summary=summarization)
    except Exception as e:
        e.with_traceback
        logging.error(f"Error processing YouTube summarization: '{str(e)}'")

        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            error=f"Error summarizing YouTube video: {str(e)}",
        )


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
            error=f"Error fetching YouTube details: {str(e)}",
        )
