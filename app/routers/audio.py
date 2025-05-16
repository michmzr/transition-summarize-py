import logging
import os
import tempfile
from typing import Annotated
from uuid import UUID

from fastapi import UploadFile, APIRouter, Response, status, Form, Request, Depends, HTTPException
from fastapi.responses import FileResponse
from starlette.responses import PlainTextResponse

from app.auth import get_current_active_user
from app.models import SUMMARIZATION_TYPE, SummaryResult, ApiProcessingResult
from app.processing.processing import complete_process, process_failed, register_new_process, register_process_artifact, update_process_status
from app.schema.models import ProcessArtifactType, RequestStatus, RequestType, ProcessArtifactFormat
from app.schema.pydantic_models import CompletedProcess, User
from app.summary.summarization import summarize
from app.transcribe.transcription import LANG_CODE, WHISPER_RESPONSE_FORMAT, transcribe
from app.utils.files import string_to_filename

VALID_AUDIO_EXTENSIONS = ('flac', 'm4a', 'mp3', 'mp4', 'mpeg', 'mpga', 'oga', 'ogg', 'wav', 'webm')

a_router = APIRouter(
    prefix="/audio",
    tags=["audio", "transcription", "summarization"],
    dependencies=[Depends(get_current_active_user)]
)

@a_router.post("/transcribe", response_model=ApiProcessingResult)
async def audio_trans(
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

    Parameters:
    - uploaded_file (UploadFile): The audio file to be transcribed.
    - lang (LANG_CODE): The language of the input audio in ISO-639-1 format.
    - transcription_response_format (WHISPER_RESPONSE_FORMAT): The desired format of the transcription response (default: SRT).

    Returns:
    - TranscriptionResult: The transcription result, including the transcribed text and format.

    Raises:
    - HTTPException 400: If the uploaded file is not a valid audio file.

    Description:
    This endpoint accepts an audio file via multipart form-data, transcribes it to text, and returns the result.
    The transcription can be returned as plain text or JSON based on the Accept header in the request.
    """
    logging.info(f"audio transcribe api - file name: {uploaded_file.filename}, "
        f" content_type: {uploaded_file.content_type}, transcription response format: ${transcription_response_format}")

    process_id = None
    try:
        if not uploaded_file.content_type.startswith("audio") and not uploaded_file.content_type.startswith("video"):
            response.status_code = status.HTTP_400_BAD_REQUEST
            return ApiProcessingResult(
                error="Invalid file type. Only audio files are accepted"
            )

        if not uploaded_file.filename.endswith(VALID_AUDIO_EXTENSIONS):
            response.status_code = status.HTTP_400_BAD_REQUEST
            return ApiProcessingResult(
                error=f"Invalid file type. Only {VALID_AUDIO_EXTENSIONS} files are accepted"
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

        transcription = await transcribe_uploaded_file(uploaded_file, lang, transcription_response_format)

        update_process_status(process_id, CompletedProcess(
            user_id=current_user.id,
            status=RequestStatus.COMPLETED,
            result=transcription,
            result_format=transcription_response_format.value,
            lang=lang,
            type=ProcessArtifactType.TRANSCRIPTION
        ))

        logging.info(
            f"Completed processing audio file. Returning transcription with length: {len(transcription)}")

        accept_header = request.headers.get("Accept", "application/json")
        logging.info(f"Accept header: {accept_header}")
        ext = transcription_response_format.value

        if accept_header == "text/plain":
            return PlainTextResponse(transcription)
        elif accept_header == "text/"+ext:
            # return as a file
            file_name = os.path.splitext(uploaded_file.filename)[0]
            file_name = string_to_filename(file_name) + "." + ext
            logging.info(f"File name: {file_name}")

            # Save transcription as a temporary file
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp:
                temp.write(transcription.encode('utf-8'))
                temp.flush()
                return FileResponse(temp.name, media_type="text/"+ext, filename=file_name)
        else:
            return ApiProcessingResult(result=transcription)
    except Exception as e:
        logging.error(f"Error in audio transcribe endpoint: {str(e)}", exc_info=True)

        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            error="Error in audio transcribtion ",
        )

@a_router.post("/summary", response_model=SummaryResult)
async def audio_summarize(
        uploaded_file: UploadFile,
        type: Annotated[SUMMARIZATION_TYPE, Form()],
        lang: Annotated[LANG_CODE, Form()],
        request: Request,
        response: Response,
        current_user: User = Depends(get_current_active_user)
):
    """
    Summarize an uploaded audio file.

    Parameters:
    - uploaded_file (UploadFile): The audio file to be summarized.
    - type (SUMMARIZATION_TYPE): The type of summary to generate.
    - lang (LANG_CODE): The language of the input audio and desired summary in ISO-639-1 format.

    Returns:
    - SummaryResult: The generated summary of the audio content.

    Raises:
    - HTTPException 400: If the uploaded file is not a valid audio file.

    Description:
    This endpoint accepts an audio file via multipart form-data, transcribes it, and then generates a summary of the content.
    The summary can be returned as plain text or JSON based on the Accept header in the request.
    """
    process_id = None

    try:
        logging.info(f"audio summarizing api - {uploaded_file}, type: {type.name}")

        # Register new audio processing job first to get process_id
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

        # Then check if file is audio
        if not uploaded_file.content_type.startswith("audio") and not uploaded_file.content_type.startswith("video") and not uploaded_file.filename.endswith(VALID_AUDIO_EXTENSIONS):
            update_process_status(process_id, CompletedProcess(
                user_id=current_user.id,
                status=RequestStatus.FAILED,
                error=f"Invalid file type '{uploaded_file.content_type}'. Only audio files are accepted",
                type=ProcessArtifactType.SUMMARY,
                result="",
                result_format=ProcessArtifactFormat.TEXT,
                lang=lang
            ))
            response.status_code = status.HTTP_400_BAD_REQUEST
            return SummaryResult(summary=None)

        # Update status before transcription
        transcription = await transcribe_uploaded_file(uploaded_file, lang, WHISPER_RESPONSE_FORMAT.SRT)
        register_process_artifact(
            current_user, process_id, ProcessArtifactType.TRANSCRIPTION, transcription, ProcessArtifactFormat.TEXT, lang)

        # Update status before summarization
        summary = await summarize(transcription, type, lang)
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
        logging.error(f"Error in audio summarize endpoint: {str(e)}", exc_info=True)
        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return SummaryResult(summary=None)


async def transcribe_uploaded_file(uploaded_file: UploadFile,
                                   lang: LANG_CODE,
                                   response_format: WHISPER_RESPONSE_FORMAT):
    logging.info(
        f"Transcribing uploaded file: {uploaded_file.filename}, lang: {lang}, response_format: {response_format}")
    try:
        suffix = os.path.splitext(uploaded_file.filename)[1]

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
            while contents := await uploaded_file.read(1024 * 1024):
                temp.write(contents)
            temp.seek(0)
            file_size = os.path.getsize(temp.name)
            with open(temp.name, 'rb') as binary_file:
                sample = binary_file.read(32)
                logging.info(
                    f"Temp file size: {file_size}, first 32 bytes: {sample}")
                binary_file.seek(0)
                transcription = await transcribe(binary_file, lang, response_format)
                logging.info(
                    f"Transcription generated with  length: {len(transcription)} and format: {response_format}")
                return transcription
    except Exception as e:
        logging.error(f"Error transcribing file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while transcribing the audio file"
        )
