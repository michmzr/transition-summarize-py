import ast
import io
import os
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test_openai_key")
os.environ.setdefault("SECRET_KEY", "test_secret_key")

from app.transcribe.models import (
    OPENAI_TRANSCRIPTION_MODEL,
    OPENAI_TRANSCRIPTION_RESPONSE_FORMAT_FALLBACK_MODEL,
    coerce_openai_transcription_response,
    get_openai_transcription_api_response_format,
    get_openai_transcription_model,
)
from app.transcribe.OpenAIWhisperParser import OpenAIWhisperParser
from app.transcribe.transcription import (
    LANG_CODE,
    WHISPER_RESPONSE_FORMAT,
    small_file,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_openai_transcription_model_uses_gpt_4o_transcribe():
    assert OPENAI_TRANSCRIPTION_MODEL == "gpt-4o-transcribe"


def test_openai_transcription_model_selector_keeps_unsupported_formats_on_whisper():
    assert get_openai_transcription_model("text") == OPENAI_TRANSCRIPTION_MODEL
    assert get_openai_transcription_model("json") == OPENAI_TRANSCRIPTION_MODEL
    assert get_openai_transcription_model(None) == OPENAI_TRANSCRIPTION_MODEL
    assert (
        get_openai_transcription_model("srt")
        == OPENAI_TRANSCRIPTION_RESPONSE_FORMAT_FALLBACK_MODEL
    )
    assert (
        get_openai_transcription_model("vtt")
        == OPENAI_TRANSCRIPTION_RESPONSE_FORMAT_FALLBACK_MODEL
    )
    assert (
        get_openai_transcription_model("verbose_json")
        == OPENAI_TRANSCRIPTION_RESPONSE_FORMAT_FALLBACK_MODEL
    )


def test_openai_transcription_api_response_format_uses_json_for_gpt_transcription_model():
    assert get_openai_transcription_api_response_format("text") == "json"
    assert get_openai_transcription_api_response_format("json") == "json"
    assert get_openai_transcription_api_response_format(None) is None
    assert get_openai_transcription_api_response_format("srt") == "srt"


def test_openai_transcription_text_response_is_coerced_from_json_object():
    class Transcription:
        text = "transcription-result"

    assert (
        coerce_openai_transcription_response(Transcription(), "text")
        == "transcription-result"
    )
    assert (
        coerce_openai_transcription_response(Transcription(), "json").text
        == "transcription-result"
    )


def _small_file_model_for(response_format: WHISPER_RESPONSE_FORMAT):
    import app.settings as settings_module

    calls = {}

    class FakeTranscriptions:
        def create(self, **kwargs):
            calls.update(kwargs)
            if kwargs["response_format"] == "json":
                return type("Transcription", (), {"text": "transcription-result"})()

            return "transcription-result"

    class FakeAudio:
        transcriptions = FakeTranscriptions()

    class FakeClient:
        audio = FakeAudio()

    original_client = settings_module.client_openai
    settings_module.client_openai = FakeClient()

    audio_file = io.BytesIO(b"fake audio")
    audio_file.name = "sample.mp3"

    try:
        if hasattr(small_file, "cache_clear"):
            small_file.cache_clear()

        result = small_file(
            audio_file,
            lang=LANG_CODE.POLISH,
            response_format=response_format,
        )

        return calls["model"], calls["response_format"], result
    finally:
        settings_module.client_openai = original_client
        if hasattr(small_file, "cache_clear"):
            small_file.cache_clear()


def test_small_file_uses_current_openai_transcription_model_for_text():
    model, response_format, result = _small_file_model_for(
        WHISPER_RESPONSE_FORMAT.TEXT)

    assert model == OPENAI_TRANSCRIPTION_MODEL
    assert response_format == "json"
    assert result == "transcription-result"


def test_small_file_keeps_srt_on_whisper_fallback_model():
    model, response_format, result = _small_file_model_for(
        WHISPER_RESPONSE_FORMAT.SRT)

    assert model == OPENAI_TRANSCRIPTION_RESPONSE_FORMAT_FALLBACK_MODEL
    assert response_format == "srt"
    assert result == "transcription-result"


def test_openai_whisper_parser_defaults_to_shared_transcription_model():
    parser = OpenAIWhisperParser()

    assert parser.model == OPENAI_TRANSCRIPTION_MODEL


def test_openai_whisper_parser_keeps_srt_on_whisper_fallback_model():
    parser = OpenAIWhisperParser(response_format="srt")

    assert parser.model == OPENAI_TRANSCRIPTION_RESPONSE_FORMAT_FALLBACK_MODEL
    assert parser.response_format == "srt"


def test_openai_whisper_parser_uses_json_response_format_for_text_with_gpt_model():
    parser = OpenAIWhisperParser(response_format="text")

    assert parser.model == OPENAI_TRANSCRIPTION_MODEL
    assert parser.response_format == "json"


def _function_def(module_path: str, function_name: str) -> ast.FunctionDef:
    tree = ast.parse((PROJECT_ROOT / module_path).read_text())

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return node

    raise AssertionError(f"Function {function_name} not found in {module_path}")


def _has_call_with_response_format(
        function_def: ast.FunctionDef,
        call_name: str,
        format_name: str) -> bool:
    for node in ast.walk(function_def):
        if not isinstance(node, ast.Call):
            continue

        if getattr(node.func, "id", None) != call_name:
            continue

        for arg in node.args:
            if (
                isinstance(arg, ast.Attribute)
                and isinstance(arg.value, ast.Name)
                and arg.value.id == "WHISPER_RESPONSE_FORMAT"
                and arg.attr == format_name
            ):
                return True

    return False


def test_audio_summary_requests_text_transcription_for_summarization_input():
    audio_summarize = _function_def("app/routers/audio.py", "audio_summarize")

    assert _has_call_with_response_format(
        audio_summarize,
        "transcribe_uploaded_file",
        "TEXT",
    )


def test_youtube_summary_requests_text_transcription_when_openai_transcription_is_needed():
    yt_summarize = _function_def("app/routers/youtube.py", "yt_summarize")

    assert _has_call_with_response_format(
        yt_summarize,
        "yt_transcribe",
        "TEXT",
    )


if __name__ == "__main__":
    test_openai_transcription_model_uses_gpt_4o_transcribe()
    test_openai_transcription_model_selector_keeps_unsupported_formats_on_whisper()
    test_openai_transcription_api_response_format_uses_json_for_gpt_transcription_model()
    test_openai_transcription_text_response_is_coerced_from_json_object()
    test_small_file_uses_current_openai_transcription_model_for_text()
    test_small_file_keeps_srt_on_whisper_fallback_model()
    test_openai_whisper_parser_defaults_to_shared_transcription_model()
    test_openai_whisper_parser_keeps_srt_on_whisper_fallback_model()
    test_openai_whisper_parser_uses_json_response_format_for_text_with_gpt_model()
    test_audio_summary_requests_text_transcription_for_summarization_input()
    test_youtube_summary_requests_text_transcription_when_openai_transcription_is_needed()
