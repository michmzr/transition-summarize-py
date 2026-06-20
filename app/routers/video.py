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
            return ApiProcessingResult(
                result=True, error=None,
                transcription=transcription,
                format=video_request.response_format)
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
    response_model=SummaryResult,
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

        transcription = video_transcribe(
            video_request.url, save_dir, video_request.lang,
            WHISPER_RESPONSE_FORMAT.TEXT)

        register_process_artifact(
            current_user, process_id,
            ProcessArtifactType.TRANSCRIPTION,
            transcription,
            ProcessArtifactFormat.TEXT, video_request.lang)

        summarization = summarize(
            transcription, video_request.type, video_request.lang)
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
            return SummaryResult(summary=summarization)
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
