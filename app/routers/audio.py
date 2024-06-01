import logging
import os
import tempfile
from enum import Enum

from fastapi import UploadFile, APIRouter, Response, status, Form
from typing import Annotated
from summary.utils import summarize
from models import SUMMARIZATION_TYPE
from transcribe.utils import transcribe, LANG_CODE

VALID_AUDIO_EXTENSIONS = ('flac', 'm4a', 'mp3', 'mp4', 'mpeg', 'mpga', 'oga', 'ogg', 'wav', 'webm')

router = APIRouter(prefix="/audio", tags=["audio", "transcription", "summarization"])


@router.post("/transcribe")
def audio_trans(uploaded_file: UploadFile,
                lang: Annotated[LANG_CODE, Form()], response: Response):
    """
    request accepts audio file in request multi-part and transcribes it to text
    :param lang:  The language of the input audio. Supplying the input language in
              [ISO-639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes) format will
              improve accuracy and latency.
    :param uploaded_file: audio file
    :return: result field: transcription text
    """
    logging.info(f"audio transcribe api - file name: {uploaded_file.filename}, "
                 f" content_type: {uploaded_file.content_type}")

    if not uploaded_file.content_type.startswith("audio") and not uploaded_file.content_type.startswith("video"):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "Invalid file type. Only audio files are accepted"}

    if not uploaded_file.filename.endswith(VALID_AUDIO_EXTENSIONS):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": f"Invalid file type. Only {VALID_AUDIO_EXTENSIONS} files are accepted"}

    transcription = transcribe_uploadeded_file(uploaded_file, lang)

    logging.info("Completed processing audio file. Returning transcription.")
    return {"result": transcription}


@router.post("/summary")
def audio_summarize(uploaded_file: UploadFile,
                    type: Annotated[SUMMARIZATION_TYPE, Form()],
                    lang: Annotated[LANG_CODE, Form()],
                    response: Response):
    """
    request accepts audio file in request and summarizes it
    :param uploaded_file:
    :param type: Summary type
    :param lang: language ISO type
    :param response:
    :return:
    """
    logging.info(f"audio summarizing api - {uploaded_file}, type: {type.name}")

    # check if file is audio
    if not uploaded_file.content_type.startswith("audio") and not uploaded_file.content_type.startswith("video"):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "Invalid file type. Only audio files are accepted"}

    if not uploaded_file.filename.endswith(VALID_AUDIO_EXTENSIONS):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": f"Invalid file type. Only {VALID_AUDIO_EXTENSIONS} files are accepted"}

    transcription = transcribe_uploadeded_file(uploaded_file, lang)
    summary = summarize(transcription, type, lang)

    logging.info("Completed processing audio file. Returning transcription.")
    return {"result": summary}


def transcribe_uploadeded_file(uploaded_file: UploadFile, lang: LANG_CODE):
    suffix = os.path.splitext(uploaded_file.filename)[1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        while contents := uploaded_file.file.read(1024 * 1024):
            temp.write(contents)
        temp.seek(0)
        with open(temp.name, 'rb') as binary_file:
            transcription = transcribe(binary_file, lang)

    os.unlink(temp.name)

    return transcription
