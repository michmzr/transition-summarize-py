import logging
import os
import tempfile
from enum import Enum

from fastapi import UploadFile, APIRouter, Response, status, Form
from typing import Annotated
from summary.utils import summarize, SUMMARIZATION_TYPE
from transcribe.utils import transcribe

VALID_AUDIO_EXTENSIONS = ('flac', 'm4a', 'mp3', 'mp4', 'mpeg', 'mpga', 'oga', 'ogg', 'wav', 'webm')

router = APIRouter()


@router.post("/audio/transcribe")
def audio_trans(uploaded_file: UploadFile, response: Response):
    """
    request accepts audio file in request multi-part and transcribes it to text
    :param uploaded_file:
    :return: transcription
    """
    logging.info(f"audio transcribe api - file name: {uploaded_file.filename}, "
                 f" content_type: {uploaded_file.content_type}")

    # check if file is audio
    if not uploaded_file.content_type.startswith("audio"):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "Invalid file type. Only audio files are accepted"}

    if not uploaded_file.filename.endswith(VALID_AUDIO_EXTENSIONS):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": f"Invalid file type. Only {VALID_AUDIO_EXTENSIONS} files are accepted"}

    transcription = transcribe_uploadeded_file(uploaded_file)

    logging.info("Completed processing audio file. Returning transcription.")
    return {"result": transcription}


@router.post("/audio/summary")
def audio_summarize(uploaded_file: UploadFile,
                    type: Annotated[SUMMARIZATION_TYPE, Form()],
                    language: Annotated[str, Form()],
                    response: Response):
    """

    :param uploaded_file:
    :param type:
    :param language: language ISO type
    :param response:
    :return:
    """
    logging.info(f"audio summarizing api - {uploaded_file}, type: {type.name}")

    # language is not defined, then set it english
    if not language:
        language = "en"

    # check if file is audio
    if not uploaded_file.content_type.startswith("audio"):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "Invalid file type. Only audio files are accepted"}

    if not uploaded_file.filename.endswith(VALID_AUDIO_EXTENSIONS):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": f"Invalid file type. Only {VALID_AUDIO_EXTENSIONS} files are accepted"}

    transcription = transcribe_uploadeded_file(uploaded_file)
    summary = summarize(transcription, type, language)

    logging.info("Completed processing audio file. Returning transcription.")
    return {"result": summary}


def transcribe_uploadeded_file(uploaded_file: UploadFile):
    suffix = os.path.splitext(uploaded_file.filename)[1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        while contents := uploaded_file.file.read(1024 * 1024):
            temp.write(contents)
        temp.seek(0)
        with open(temp.name, 'rb') as binary_file:
            transcription = transcribe(binary_file)

    os.unlink(temp.name)

    return transcription
