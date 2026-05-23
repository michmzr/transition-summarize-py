from typing import Any

OPENAI_TRANSCRIPTION_MODEL = "gpt-4o-transcribe"
OPENAI_TRANSCRIPTION_RESPONSE_FORMAT_FALLBACK_MODEL = "whisper-1"

_OPENAI_TRANSCRIPTION_MODEL_RESPONSE_FORMATS = {None, "json", "text"}


def get_openai_transcription_model(response_format: str | None) -> str:
    if response_format in _OPENAI_TRANSCRIPTION_MODEL_RESPONSE_FORMATS:
        return OPENAI_TRANSCRIPTION_MODEL

    return OPENAI_TRANSCRIPTION_RESPONSE_FORMAT_FALLBACK_MODEL


def get_openai_transcription_api_response_format(
        response_format: str | None) -> str | None:
    if get_openai_transcription_model(response_format) == OPENAI_TRANSCRIPTION_MODEL:
        if response_format == "text":
            return "json"

    return response_format


def coerce_openai_transcription_response(
        transcription: Any,
        response_format: str | None) -> Any:
    if response_format == "text" and hasattr(transcription, "text"):
        return transcription.text

    return transcription
