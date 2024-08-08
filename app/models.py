from enum import Enum

from pydantic import BaseModel, Field

from transcribe.utils import LANG_CODE, WHISPER_RESPONSE_FORMAT


class SUMMARIZATION_TYPE(str, Enum):
    CONCISE = "concise"
    TLDR = "tldr"
    DETAILED = "detailed"


class YTVideoTranscribe(BaseModel):
    url: str
    lang: LANG_CODE = Field(default=LANG_CODE.POLISH, title="Video language as ISO-639-1 code like PL, EN", ),
    response_format: WHISPER_RESPONSE_FORMAT = Field(default=WHISPER_RESPONSE_FORMAT.SRT, title="Response format")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "https://www.youtube.com/shorts/tvPMT89eJWo",
                    "lang": "pl",
                    "response_format": "srt"
                }
            ]
        }
    }


class YtVideoSummarize(BaseModel):
    """
    Request model for summarizing YouTube video

    lang: The language of the input audio. Supplying the input language in
              [ISO-639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes) format will
              improve accuracy and latency.
    """
    url: str
    type: SUMMARIZATION_TYPE = Field(default=SUMMARIZATION_TYPE.TLDR, title="Type of summarization")
    lang: LANG_CODE = Field(default=LANG_CODE.POLISH,
                            title="Language code of transcription and final summarization text")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "https://www.youtube.com/shorts/tvPMT89eJWo",
                    "type": "detailed",
                    "lang": "pl"
                }
            ]
        }
    }
