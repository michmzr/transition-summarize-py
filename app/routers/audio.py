import logging
import os
import tempfile
from typing import Annotated
from uuid import UUID

from fastapi import UploadFile, APIRouter, Response, status, Form, Request, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.responses import PlainTextResponse

from app.auth import get_current_active_user
from app.models import SUMMARIZATION_TYPE, SummaryResult, ApiProcessingResult
from app.processing.processing import complete_process, process_failed, register_new_process, register_process_artifact, update_process_status
from app.schema.models import ProcessArtifactType, RequestStatus, RequestType, ProcessArtifactFormat
from app.schema.pydantic_models import CompletedProcess, User
from app.settings import get_settings
from app.summary.summarization import summarize
from app.transcribe.transcription import LANG_CODE, WHISPER_RESPONSE_FORMAT, transcribe

VALID_AUDIO_EXTENSIONS = ('flac', 'm4a', 'mp3', 'mp4', 'mpeg', 'mpga', 'oga', 'ogg', 'wav', 'webm')

a_router = APIRouter(
    prefix="/audio",
    tags=["audio", "transcription", "summarization"],
    dependencies=[Depends(get_current_active_user)]
)


class RecursiveAudioTranscriptionRequest(BaseModel):
    directory_path: str
    lang: LANG_CODE = LANG_CODE.POLISH

@a_router.post(
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
                "text/srt": {
                    "schema": {"type": "string", "format": "binary"},
                    "description": "SRT file download. Returned when `Accept: text/srt` and `transcription_response_format=srt`. The filename in `Content-Disposition` is derived from the uploaded file name (e.g. `nagranie.mp3` → `nagranie.srt`).",
                    "example": "1\n00:00:01,000 --> 00:00:05,000\nHello world",
                },
            },
        },
        400: {
            "description": "Invalid file type or extension.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": False, "error": "Invalid file type. Only audio files are accepted", "text": None},
                }
            },
        },
        500: {
            "description": "Internal server error during transcription.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": False, "error": "An error occurred while processing the audio file", "text": None},
                }
            },
        },
    },
)
def audio_trans(
        uploaded_file: UploadFile,
        lang: Annotated[LANG_CODE, Form()],
        request: Request,
        response: Response,
        current_user: User = Depends(get_current_active_user),
        transcription_response_format: Annotated[
            WHISPER_RESPONSE_FORMAT, Form()] = WHISPER_RESPONSE_FORMAT.SRT
):
    """
    Transcribe an uploaded audio file to text.

    The response format is determined by the `Accept` request header:
    - `application/json` (default): JSON object with transcription result and metadata.
    - `text/plain`: Raw transcription text.
    - `text/srt`: SRT file download. The `Content-Disposition` filename is derived from the
      uploaded file name (e.g. `nagranie.mp3` → `nagranie.srt`).
      Requires `transcription_response_format=srt` in the form data.

    Parameters:
    - uploaded_file (UploadFile): The audio file to be transcribed.
    - lang (LANG_CODE): The language of the input audio in ISO-639-1 format.
    - transcription_response_format (WHISPER_RESPONSE_FORMAT): The desired format of the transcription response (default: SRT).

    Raises:
    - HTTP 400: If the uploaded file is not a valid audio file or has an unsupported extension.
    - HTTP 500: If an unexpected error occurs during transcription.
    """
    logging.info(f"audio transcribe api - file name: {uploaded_file.filename}, "
        f" content_type: {uploaded_file.content_type}, transcription response format: ${transcription_response_format}")

    process_id = None
    try:
        if not uploaded_file.content_type.startswith("audio") and not uploaded_file.content_type.startswith("video"):
            response.status_code = status.HTTP_400_BAD_REQUEST
            return ApiProcessingResult(
                result=False,
                error="Invalid file type. Only audio files are accepted",
            )

        if not uploaded_file.filename.endswith(VALID_AUDIO_EXTENSIONS):
            response.status_code = status.HTTP_400_BAD_REQUEST
            return ApiProcessingResult(result=False,
                                    error=f"Invalid file type. Only {VALID_AUDIO_EXTENSIONS} files are accepted",
                                    )

        process_id = register_new_process(
            current_user,
            RequestType.AUDIO,
            request=request,
            request_data={
                "file_name": uploaded_file.filename,
                "file_type": uploaded_file.content_type,
                "lang": lang,
                "format": transcription_response_format}
        )

        transcription = transcribe_uploaded_file(uploaded_file, lang, transcription_response_format)

        update_process_status(process_id, CompletedProcess(
            user_id=current_user.id,
            status=RequestStatus.COMPLETED,
            result=transcription,
            result_format=transcription_response_format.value,
            lang=lang,
            type=ProcessArtifactType.TRANSCRIPTION
        ))

        logging.info("Completed processing audio file. Returning transcription.")

        accept_header = request.headers.get("Accept", "application/json")
        logging.info(f"Accept header: {accept_header}")
        if accept_header == "text/plain":
            return PlainTextResponse(transcription)
        elif accept_header == "text/srt":
            # return as a file
            file_name = os.path.splitext(uploaded_file.filename)[0] + ".srt"
            logging.info(f"File name: {file_name}")
            return FileResponse(transcription, media_type="text/srt", filename=file_name)
        else:
            return ApiProcessingResult(result=True, error=None, transcription=transcription,
                                    format=transcription_response_format)
    except Exception as e:
        logging.error(f"Error in audio transcribe endpoint: {str(e)}", exc_info=True)

        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            result=False,
            error="An error occurred while processing the audio file",
        )

@a_router.post(
    "/summary",
    response_model=SummaryResult,
    responses={
        200: {
            "description": "Summary result. Content type depends on the `Accept` request header.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/SummaryResult"},
                    "example": {"summary": "The speaker discusses the key points of the meeting..."},
                },
                "text/plain": {
                    "schema": {"type": "string"},
                    "example": "The speaker discusses the key points of the meeting...",
                },
            },
        },
        400: {
            "description": "Invalid file type or extension.",
            "content": {
                "application/json": {
                    "schema": {"type": "object", "properties": {"error": {"type": "string"}}},
                    "example": {"error": "Invalid file type. Only audio files are accepted"},
                }
            },
        },
        500: {
            "description": "Internal server error during transcription or summarization.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/SummaryResult"},
                    "example": {"result": False, "error": "An error occurred while processing the audio file", "summary": None},
                }
            },
        },
    },
)
def audio_summarize(
        uploaded_file: UploadFile,
        type: Annotated[SUMMARIZATION_TYPE, Form()],
        lang: Annotated[LANG_CODE, Form()],
        request: Request,
        response: Response,
        current_user: User = Depends(get_current_active_user)
):
    """
    Transcribe and summarize an uploaded audio file.

    The response format is determined by the `Accept` request header:
    - `application/json` (default): JSON object containing the generated summary.
    - `text/plain`: Raw summary text.

    Parameters:
    - uploaded_file (UploadFile): The audio file to be summarized.
    - type (SUMMARIZATION_TYPE): The type of summary to generate (concise, tldr, detailed).
    - lang (LANG_CODE): The language of the input audio and desired summary in ISO-639-1 format.

    Raises:
    - HTTP 400: If the uploaded file is not a valid audio file or has an unsupported extension.
    - HTTP 500: If an unexpected error occurs during transcription or summarization.
    """
    process_id = None

    try:
        logging.info(f"audio summarizing api - {uploaded_file}, type: {type.name}")

        try:
            # check if file is audio
            if not uploaded_file.content_type.startswith("audio") and not uploaded_file.content_type.startswith("video"):
                response.status_code = status.HTTP_400_BAD_REQUEST
                return {"error": "Invalid file type. Only audio files are accepted"}

            if not uploaded_file.filename.endswith(VALID_AUDIO_EXTENSIONS):
                response.status_code = status.HTTP_400_BAD_REQUEST
                return {"error": f"Invalid file type. Only {VALID_AUDIO_EXTENSIONS} files are accepted"}

            # Register new audio processing job
            process_id = register_new_process(
                current_user,
                RequestType.AUDIO,
                request=request,
                request_data={
                    "file_name": uploaded_file.filename,
                    "file_type": uploaded_file.content_type,
                    "lang": lang,
                    "format": type.name}
            )

            # Update status before transcription
            transcription = transcribe_uploaded_file(uploaded_file, lang, WHISPER_RESPONSE_FORMAT.SRT)
            register_process_artifact(
                current_user, process_id, ProcessArtifactType.TRANSCRIPTION, transcription, ProcessArtifactFormat.TEXT, lang)

            # Update status before summarization
            summary = summarize(transcription, type, lang)
            register_process_artifact(
                current_user, process_id, ProcessArtifactType.SUMMARY, summary, ProcessArtifactFormat.TEXT, lang)

            # Mark process as completed
            complete_process(process_id)

            logging.info("Completed processing audio file. Returning summary.")

            accept_header = request.headers.get("Accept", "application/json")
            # If the Accept header is "text/plain", return plain text
            if accept_header == "text/plain":
                return PlainTextResponse(summary)
            else:
                return SummaryResult(summary=summary)
        except Exception as e:
            if process_id:
                process_failed(process_id, str(e))
            raise
    except Exception as e:
        logging.error(f"Error in audio summarize endpoint: {str(e)}", exc_info=True)
        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return SummaryResult(
            result=False,
            error="An error occurred while processing the audio file",
            summary=None
        )

def transcribe_uploaded_file(uploaded_file: UploadFile,
                             lang: LANG_CODE,
                             response_format: WHISPER_RESPONSE_FORMAT):
    try:
        suffix = os.path.splitext(uploaded_file.filename)[1]
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
            while contents := uploaded_file.file.read(1024 * 1024):
                temp.write(contents)
            temp.seek(0)
            with open(temp.name, 'rb') as binary_file:
                transcription = transcribe(binary_file, lang, response_format)
                return transcription
    except Exception as e:
        logging.error(f"Error transcribing file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while transcribing the audio file"
        )

def list_files_with_file_extension(directory, file_extension):
    try:
        files = [f for f in os.listdir(directory) if f.endswith(file_extension)]
        logging.debug(f"Found {len(files)} files with extension {file_extension}")
        return files
    except Exception as e:
        logging.error(f"Error listing files in directory {directory}: {str(e)}")
        raise

def transcribe_file(save_path: str, file: str):
    try:
        logging.info(f"Starting transcription for file '{file}'")

        logging.debug(f"Reading audio file '{file}'...")
        with open(file, 'rb') as audio_file:
            try:
                transcription = transcribe(audio_file, LANG_CODE.POLISH, WHISPER_RESPONSE_FORMAT.SRT)
            except Exception as e:
                logging.error(f"Transcription failed for {file}: {str(e)}")
                raise

        output = os.path.splitext(os.path.basename(file))[0] + ".txt"
        logging.info(f"Saving transcription to {output}")
        file_name = os.path.join(save_path, output)

        try:
            with open(file_name, "x") as f:
                f.write(transcription)
        except FileExistsError:
            logging.warning(f"File {file_name} already exists, skipping save")
            raise
        except Exception as e:
            logging.error(f"Error saving transcription to {file_name}: {str(e)}")
            raise

        logging.info(f"Successfully transcribed and saved {file}")
        return True

    except Exception as e:
        logging.error(f"Failed to process {file}: {str(e)}")
        raise


@a_router.post(
    "/recursive",
    response_model=ApiProcessingResult,
    responses={
        200: {
            "description": "Batch transcription result for all audio files found in the directory.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": True, "error": None, "text": "Processed 5 audio files. Successful: 5. Failed: 0."},
                }
            },
        },
        207: {
            "description": "Partial success — some files failed to transcribe.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": False, "error": "Some files failed to transcribe", "text": "Processed 5 audio files. Successful: 3. Failed: 2. Failed files: /path/a.mp3, /path/b.wav"},
                }
            },
        },
        400: {
            "description": "Directory does not exist or path is not a directory.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": False, "error": "Directory does not exist: /some/path", "text": None},
                }
            },
        },
        403: {
            "description": "Endpoint not available in non-local mode.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": False, "error": "Endpoint not available.", "text": None},
                }
            },
        },
        500: {
            "description": "Internal server error during recursive transcription.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": False, "error": "An error occurred while processing the directory", "text": None},
                }
            },
        },
    },
)
def audio_recursive_transcribe(
        request: Request,
        recursive_request: RecursiveAudioTranscriptionRequest,
        response: Response,
        current_user: User = Depends(get_current_active_user)
):
    process_id = None
    settings = get_settings()
    if not settings.is_local:
        logging.warning(
            "Rejected /audio/recursive request because IS_LOCAL is disabled")
        response.status_code = status.HTTP_403_FORBIDDEN
        return ApiProcessingResult(result=False, error="Endpoint not available.")

    directory_path = os.path.abspath(recursive_request.directory_path)
    logging.info(
        f"audio recursive transcribe api - directory_path: {directory_path}, lang: {recursive_request.lang}")

    try:
        if not os.path.exists(directory_path):
            response.status_code = status.HTTP_400_BAD_REQUEST
            return ApiProcessingResult(result=False, error=f"Directory does not exist: {directory_path}")

        if not os.path.isdir(directory_path):
            response.status_code = status.HTTP_400_BAD_REQUEST
            return ApiProcessingResult(result=False, error=f"Path is not a directory: {directory_path}")

        process_id = register_new_process(
            current_user,
            RequestType.AUDIO,
            request=request,
            request_data={
                "directory_path": directory_path,
                "lang": recursive_request.lang.value,
                "mode": "recursive"}
        )

        audio_files: list[str] = []
        for root, _, files in os.walk(directory_path):
            for filename in files:
                if filename.lower().endswith(VALID_AUDIO_EXTENSIONS):
                    audio_files.append(os.path.join(root, filename))

        if not audio_files:
            update_process_status(process_id, CompletedProcess(
                user_id=current_user.id,
                status=RequestStatus.COMPLETED,
                result=f"No audio files found in: {directory_path}",
                result_format=ProcessArtifactFormat.TEXT,
                lang=recursive_request.lang,
                type=ProcessArtifactType.TRANSCRIPTION
            ))
            return ApiProcessingResult(result=True, error=None, text=f"No audio files found in: {directory_path}")

        success_count = 0
        failed_files: list[str] = []

        for audio_path in audio_files:
            output_path = f"{os.path.splitext(audio_path)[0]}.srt"
            logging.info(f"Transcribing local audio file: {audio_path}")
            try:
                with open(audio_path, "rb") as audio_file:
                    transcription = transcribe(
                        audio_file, recursive_request.lang, WHISPER_RESPONSE_FORMAT.SRT)
                with open(output_path, "w", encoding="utf-8") as output_file:
                    output_file.write(transcription)
                logging.info(f"Saved transcription file: {output_path}")
                success_count += 1
            except Exception as file_error:
                logging.error(
                    f"Failed recursive transcription for {audio_path}: {str(file_error)}")
                failed_files.append(audio_path)

        result_text = f"Processed {len(audio_files)} audio files. Successful: {success_count}. Failed: {len(failed_files)}."
        if failed_files:
            result_text += f" Failed files: {', '.join(failed_files)}"

        update_process_status(process_id, CompletedProcess(
            user_id=current_user.id,
            status=RequestStatus.COMPLETED if not failed_files else RequestStatus.FAILED,
            result=result_text,
            result_format=ProcessArtifactFormat.TEXT,
            lang=recursive_request.lang,
            type=ProcessArtifactType.TRANSCRIPTION
        ))

        if failed_files:
            response.status_code = status.HTTP_207_MULTI_STATUS
            return ApiProcessingResult(result=False, error="Some files failed to transcribe", text=result_text)

        return ApiProcessingResult(result=True, error=None, text=result_text)
    except Exception as e:
        logging.error(
            f"Error in audio recursive transcribe endpoint: {str(e)}", exc_info=True)

        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            result=False,
            error="An error occurred while processing the directory",
        )
