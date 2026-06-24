import hashlib
import logging

from fastapi import APIRouter, Request, Depends, Response, status
from fastapi.responses import FileResponse
from starlette.responses import PlainTextResponse

from app.auth import get_current_active_user
from app.models import (
    VideoTranscribe, VideoSummarize, VideoInfoRequest,
    VideoMetadata, SummaryResult, ApiProcessingResult,
)
from app.processing.processing import (
    complete_process, process_failed, register_new_process,
    register_process_artifact, update_process_status,
)
from app.schema.models import ProcessArtifactFormat, ProcessArtifactType, RequestStatus, RequestType
from app.schema.pydantic_models import CompletedProcess, User
from app.summary.summarization import summarize
from app.transcribe.transcription import WHISPER_RESPONSE_FORMAT
from app.video.metadata import get_video_metadata
from app.video.transcription import video_transcribe

video_router = APIRouter(
    prefix="/video",
    tags=["video", "transcription", "summarization"],
    dependencies=[Depends(get_current_active_user)]
)


def save_dir_path(url: str) -> str:
    hash_object = hashlib.md5(url.encode())
    hash_hex = hash_object.hexdigest()
    return f"./downloads/video/{hash_hex}/"


def _trim_metadata_text(text: str, max_length: int = 2000) -> str:
    cleaned_text = " ".join(text.split())
    if len(cleaned_text) <= max_length:
        return cleaned_text

    return f"{cleaned_text[:max_length].rstrip()}..."


def build_video_summary_input(
        transcription: str,
        metadata: VideoMetadata | None
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


@video_router.post(
    "/transcribe",
    response_model=ApiProcessingResult,
    responses={
        200: {
            "description": "Transcription result. Content type depends on the `Accept` request header.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": True, "error": None, "transcription": "Hello world", "format": "srt"},
                },
                "text/plain": {
                    "schema": {"type": "string"},
                    "example": "Hello world",
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
def video_transcription(
        request: Request,
        video_request: VideoTranscribe,
        response: Response,
        current_user: User = Depends(get_current_active_user)
):
    process_id = None
    try:
        logging.info(f"video transcribe - request details: {video_request}")

        process_id = register_new_process(
            current_user,
            request_type=RequestType.VIDEO,
            request=request,
            request_data={"video_request": video_request.model_dump()}
        )

        video_metadata = None
        try:
            video_metadata = get_video_metadata(video_request.url)
        except Exception as metadata_error:
            logging.warning(
                f"Could not fetch video metadata for transcription: '{metadata_error}'")

        save_dir = save_dir_path(video_request.url)
        transcription = video_transcribe(
            video_request.url,
            save_dir,
            video_request.lang,
            video_request.response_format)

        update_process_status(process_id, CompletedProcess(
            user_id=current_user.id,
            status=RequestStatus.COMPLETED,
            result=transcription,
            result_format=ProcessArtifactFormat.TEXT,
            lang=video_request.lang,
            type=ProcessArtifactType.TRANSCRIPTION
        ))

        accept_header = request.headers.get("Accept", "application/json")
        if accept_header == "text/plain":
            return PlainTextResponse(transcription)
        else:
            metadata_dict = video_metadata.model_dump(exclude={"subtitles"}) if video_metadata else None
            return ApiProcessingResult(
                result=True, error=None,
                transcription=transcription,
                format=video_request.response_format,
                metadata=metadata_dict)
    except Exception as e:
        logging.error(f"Error processing video transcription: {str(e)}")

        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            result=False,
            error=f"Internal server error: {str(e)}",
        )


@video_router.post(
    "/summarize",
    response_model=SummaryResult | ApiProcessingResult,
    responses={
        200: {
            "description": "Summarization result. Content type depends on the `Accept` request header.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/SummaryResult"},
                    "example": {"summary": "The video covers the main highlights..."},
                },
                "text/plain": {
                    "schema": {"type": "string"},
                    "example": "The video covers the main highlights...",
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
                    "example": {"result": False, "error": "Error processing video summarization", "text": "<details>"},
                }
            },
        },
    },
)
def video_summarize(
        request: Request,
        video_request: VideoSummarize,
        response: Response,
        current_user: User = Depends(get_current_active_user)
):
    process_id = None
    try:
        logging.info(f"video summarize - Request details: {video_request}")

        process_id = register_new_process(
            current_user,
            RequestType.VIDEO,
            request=request,
            request_data={"video_request": video_request.model_dump()}
        )

        save_dir = save_dir_path(video_request.url)

        video_metadata = None
        try:
            video_metadata = get_video_metadata(video_request.url)
        except Exception as metadata_error:
            logging.warning(
                f"Could not fetch video metadata for summarization: '{metadata_error}'")

        transcription = video_transcribe(
            video_request.url, save_dir, video_request.lang,
            WHISPER_RESPONSE_FORMAT.TEXT)

        if not transcription.strip():
            raise ValueError(
                "No transcription generated from video audio. The source may have no detectable speech.")

        register_process_artifact(
            current_user, process_id,
            ProcessArtifactType.TRANSCRIPTION,
            transcription,
            ProcessArtifactFormat.TEXT, video_request.lang)

        summary_input = build_video_summary_input(transcription, video_metadata)
        summarization = summarize(
            summary_input, video_request.type, video_request.lang)
        register_process_artifact(
            current_user, process_id,
            ProcessArtifactType.SUMMARY,
            summarization,
            ProcessArtifactFormat.TEXT, video_request.lang)

        logging.debug(f"video summarize - Result: \n{summarization}")

        complete_process(process_id)

        accept_header = request.headers.get("Accept", "application/json")
        if accept_header == "text/plain":
            return PlainTextResponse(summarization)
        elif accept_header == "text/srt":
            return FileResponse(transcription, media_type="text/srt")
        else:
            metadata_dict = video_metadata.model_dump(exclude={"subtitles"}) if video_metadata else None
            return SummaryResult(summary=summarization, metadata=metadata_dict)
    except Exception as e:
        logging.error(f"Error processing video summarization: '{str(e)}'")

        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            result=False,
            error="Error processing video summarization",
            text=str(e))


@video_router.post(
    "/details",
    response_model=VideoMetadata | ApiProcessingResult,
    responses={
        200: {
            "description": "Video metadata.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/VideoMetadata"},
                    "example": {
                        "title": "Example Video",
                        "duration": 120.0,
                        "duration_string": "2:00",
                        "description": "Video description here.",
                        "platform": "Vimeo",
                        "uploader": "Example User",
                    },
                }
            },
        },
        500: {
            "description": "Internal server error while fetching video metadata.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": False, "error": "Error extracting video details: <details>", "text": "<details>"},
                }
            },
        },
    },
)
def video_details(
        request: VideoInfoRequest,
        response: Response,
        current_user: User = Depends(get_current_active_user)
):
    try:
        logging.info(f"Getting video details: {request.url}")

        metadata = get_video_metadata(request.url)

        return metadata
    except Exception as e:
        logging.error(f"Error fetching video details: {str(e)}")

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            result=False,
            error=f"Error extracting video details: {str(e)}",
            text=str(e))
