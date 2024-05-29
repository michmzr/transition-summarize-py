import logging
import os
import tempfile

from fastapi import UploadFile, APIRouter

from transcribe.utils import transcribe

router = APIRouter()


@router.post("/audio/transcribe")
def audio_trans(uploadedFile: UploadFile):
    """
    request accepts audio file in request multi-part and transcribes it to text
    :param uploadedFile:
    :return: transcription
    """
    logging.info(f"audio transcribe api - file name: {uploadedFile.filename}, "
                 f" content_type: {uploadedFile.content_type}")

    # check if file is audio
    if not uploadedFile.content_type.startswith("audio"):
        return {"error": "Invalid file type. Only audio files are accepted"}

    # file ending with mp3/wav/omg
    if not uploadedFile.filename.endswith(('flac', 'm4a', 'mp3', 'mp4', 'mpeg', 'mpga', 'oga', 'ogg', 'wav', 'webm')):
        return {"error":
                    "Invalid file type. Only 'flac', 'm4a', 'mp3', 'mp4', 'mpeg', 'mpga', 'oga', 'ogg', 'wav', "
                    "'webm' files are accepted"}

    suffix = os.path.splitext(uploadedFile.filename)[1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        while contents := uploadedFile.file.read(1024 * 1024):
            temp.write(contents)
        temp.seek(0)
        with open(temp.name, 'rb') as binary_file:
            transcription = transcribe(binary_file)

    os.unlink(temp.name)

    logging.info("Completed processing audio file. Returning transcription.")
    return {"transcription": transcription}
