import logging
from fastapi import  UploadFile
from main import app
from transcribe.utils import transcribe


@app.post("/audio/transcribe")
def audio_trans(file: UploadFile):
    """
    request accepts audio file in request multi-part and transcribes it to text
    :param file:
    :return: transcription
    """
    logging.info(f"audio transcribe api - file name: {file.filename}, "
                 f" content_type: {file.content_type} - file size: {file.file}")

    # check if file is audio
    if not file.content_type.startswith("audio"):
        return {"error": "Invalid file type. Only audio files are accepted"}

    # file ending with mp3/wav/omg
    if file.filename.endswith((".mp3", ".wav", ".ogg")):
        return {"error": "Invalid file type. Only mp3, wav, ogg files are accepted"}

    text = transcribe(file)
    return {"transcription": text}
