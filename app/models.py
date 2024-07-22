from enum import Enum

from pydantic import BaseModel

from transcribe.utils import LANG_CODE, WHISPER_RESPONSE_FORMAT


class SUMMARIZATION_TYPE(str, Enum):
    CONCISE = "concise"
    TLDR = "tldr"
    DETAILED = "detailed"


class YTVideoTranscribe(BaseModel):
    url: str
    lang: LANG_CODE = LANG_CODE.ENGLISH,
    response_format: WHISPER_RESPONSE_FORMAT = WHISPER_RESPONSE_FORMAT.SRT


class YtVideoSummarize(BaseModel):
    """
    Request model for summarizing YouTube video

    lang: The language of the input audio. Supplying the input language in
              [ISO-639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes) format will
              improve accuracy and latency.
    """
    url: str
    type: SUMMARIZATION_TYPE = SUMMARIZATION_TYPE.TLDR
    lang: LANG_CODE = LANG_CODE.ENGLISH
