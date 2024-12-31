import logging
import os
import tempfile
from typing import Annotated
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import UploadFile, APIRouter, Response, status, Form, Request, Depends
from starlette.responses import PlainTextResponse

from app.auth import get_current_active_user
from app.models import SUMMARIZATION_TYPE, SummaryResult, TranscriptionResult
from app.schema.pydantic_models import User
from app.summary.summarization import summarize
from app.transcribe.transcription import LANG_CODE, WHISPER_RESPONSE_FORMAT, transcribe

VALID_AUDIO_EXTENSIONS = ('flac', 'm4a', 'mp3', 'mp4', 'mpeg', 'mpga', 'oga', 'ogg', 'wav', 'webm')

a_router = APIRouter(
    prefix="/audio",
    tags=["audio", "transcription", "summarization"],
    dependencies=[Depends(get_current_active_user)]
)

@a_router.post("/transcribe", response_model=TranscriptionResult)
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

    if not uploaded_file.content_type.startswith("audio") and not uploaded_file.content_type.startswith("video"):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return TranscriptionResult(
            result=False,
            error="Invalid file type. Only audio files are accepted",
            transcription=None,
            format=None
        )

    if not uploaded_file.filename.endswith(VALID_AUDIO_EXTENSIONS):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return TranscriptionResult(result=False,
                                   error=f"Invalid file type. Only {VALID_AUDIO_EXTENSIONS} files are accepted",
                                   transcription=None,
                                   format=None
                                   )

    transcription = transcribe_uploaded_file(uploaded_file, lang, transcription_response_format)

    logging.info("Completed processing audio file. Returning transcription.")

    # Get the Accept header from the request
    accept_header = request.headers.get("Accept", "application/json")

    # If the Accept header is "text/plain", return plain text
    if accept_header == "text/plain":
        return PlainTextResponse(transcription)
    else:
        return TranscriptionResult(result=True, error=None, transcription=transcription,
                                   format=transcription_response_format)


@a_router.post("/summary", response_model=SummaryResult)
def audio_summarize(
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
    logging.info(f"audio summarizing api - {uploaded_file}, type: {type.name}")

    # check if file is audio
    if not uploaded_file.content_type.startswith("audio") and not uploaded_file.content_type.startswith("video"):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "Invalid file type. Only audio files are accepted"}

    if not uploaded_file.filename.endswith(VALID_AUDIO_EXTENSIONS):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": f"Invalid file type. Only {VALID_AUDIO_EXTENSIONS} files are accepted"}

    transcription = transcribe_uploaded_file(uploaded_file, lang, WHISPER_RESPONSE_FORMAT.SRT)
    summary = summarize(transcription, type, lang)

    logging.info("Completed processing audio file. Returning summary.")

    accept_header = request.headers.get("Accept", "application/json")
    # If the Accept header is "text/plain", return plain text
    if accept_header == "text/plain":
        return PlainTextResponse(summary)
    else:
        return SummaryResult(summary=summary)


def transcribe_uploaded_file(uploaded_file: UploadFile,
                             lang: LANG_CODE,
                             response_format: WHISPER_RESPONSE_FORMAT):
    suffix = os.path.splitext(uploaded_file.filename)[1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        while contents := uploaded_file.file.read(1024 * 1024):
            temp.write(contents)
        temp.seek(0)
        with open(temp.name, 'rb') as binary_file:
            transcription = transcribe(binary_file, lang, response_format)

    os.unlink(temp.name)

    return transcription

def list_files_with_file_extension(directory, file_extension):
    return [f for f in os.listdir(directory) if f.endswith(file_extension)]

def transcribe_file(save_path: str, file: str):
    print(f"Transcribing file '{file}'.....")

    # Open the file in binary mode
    logging.debug(f"Reading audio file '{file}'...")
    with open(file, 'rb') as audio_file:
        transcription = transcribe(audio_file, LANG_CODE.POLISH, WHISPER_RESPONSE_FORMAT.SRT)  # Pass the file object

    output = os.path.splitext(os.path.basename(file))[0] + ".txt"  # Get filename without extension
    logging.info(f"Saving ${output}....")
    file_name = os.path.join(save_path, output)  # Use os.path.join for better path handling
    with open(file_name, "x") as f:
        f.write(transcription)

    return True


# @a_router.get("/mentoring")
# def get_transcribe_mentoringfiles():
#     directory = "/Users/michmzr/Library/CloudStorage/OneDrive-Osobisty/4.Archives/Mentoring/09\'22/"
#
#     files = list_files_with_file_extension(directory, ".wav")
#     logging.debug(files)
#
#     results = []  # List to store transcription results
#
#     with ThreadPoolExecutor() as executor:
#         futures = {executor.submit(transcribe_file, directory, directory + file): file for file in files}
#
#         for future in as_completed(futures):
#             file = futures[future]
#             try:
#                 result = future.result()  # Get the result of the transcribe_file function
#                 results.append({"file": file, "transcription": result})  # Store result
#                 print(f"Transcribed {file}: {result}")
#             except Exception as e:
#                 print(f"Error transcribing {file}: {e}")
#                 results.append({"file": file, "error": str(e)})  # Store error
#
#     logging.info("Completed processing audio file. Returning summary.")
#
#     return {"status": "success", "files": results}  # Return results in JSON format