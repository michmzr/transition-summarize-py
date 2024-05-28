import logging

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
                 f" content_type: {uploadedFile.content_type} - file size: {uploadedFile.file}")

    # check if file is audio
    if not uploadedFile.content_type.startswith("audio"):
        return {"error": "Invalid file type. Only audio files are accepted"}

    # file ending with mp3/wav/omg
    if uploadedFile.filename.endswith((".mp3", ".wav", ".ogg")):
        return {"error": "Invalid file type. Only mp3, wav, ogg files are accepted"}

    text = transcribe(uploadedFile)
    return {"transcription": text}
