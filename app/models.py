from datetime import datetime
from enum import Enum
from typing import Optional, List

from pydantic import UUID4, BaseModel, Field, EmailStr

from app.transcribe.transcription import LANG_CODE, WHISPER_RESPONSE_FORMAT


class SUMMARIZATION_TYPE(str, Enum):
    CONCISE = "concise"
    TLDR = "tldr"
    DETAILED = "detailed"


class YTVideoTranscribe(BaseModel):
    url: str
    lang: LANG_CODE = Field(default=LANG_CODE.POLISH,
                            title="Video language as ISO-639-1 code like PL, EN", ),
    response_format: WHISPER_RESPONSE_FORMAT = Field(
        default=WHISPER_RESPONSE_FORMAT.SRT, title="Response format")

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


class ApiProcessingResult(BaseModel):
    result: bool = Field(title="Success or error")
    error: Optional[str] = Field(default=None, title="Error description")
    text: Optional[str] = Field(default=None, title="Video transcription")
    transcription: Optional[str] = Field(default=None, title="Transcription text")
    format: Optional[WHISPER_RESPONSE_FORMAT] = Field(default=None, title="Response format")
    metadata: Optional[dict] = Field(default=None, title="Video metadata (title, description, duration, etc.)")


class YtVideoInfoRequest(BaseModel):
    """
    Request model for acquiring youtube video details like title, description, list of subtitles
    """

    url: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "https://www.youtube.com/shorts/tvPMT89eJWo",
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
    type: SUMMARIZATION_TYPE = Field(
        default=SUMMARIZATION_TYPE.TLDR, title="Type of summarization")
    lang: LANG_CODE = Field(default=LANG_CODE.POLISH,
                            title="Language code of transcription and final summarization text")
    use_yt_transcription: bool = Field(
        default=True, title="Use YT transcription or generate new one. If YT transcription is nto found then transcription will be generated")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "https://www.youtube.com/shorts/tvPMT89eJWo",
                    "type": "detailed",
                    "lang": "pl",
                    "use_yt_transcription": True
                }
            ]
        }
    }


class SummaryResult(BaseModel):
    summary: str
    metadata: Optional[dict] = Field(default=None, title="Video metadata (title, description, duration, etc.)")


class YoutubeTranscriptionMetadata(BaseModel):
    ext: str = Field(..., description="File extension of the transcription")
    url: str = Field(..., description="URL to access the transcription")
    name: str = Field(..., description="Name or language of the transcription")


class YoutubeMetadata(BaseModel):
    title: str = Field(
        default="", description="The title of the YouTube video")
    full_title: Optional[str] = Field(None,
                                      description="The full title of the YouTube video, which may include additional information")
    filesize: Optional[int] = Field(
        None, description="The size of the video file in bytes")
    duration: Optional[float] = Field(
        None, description="The duration of the video in seconds")
    duration_string: Optional[str] = Field(None,
                                           description="A human-readable string representation of the video duration")
    description: str = Field(
        default="", description="The description of the YouTube video")
    channel_url: Optional[str] = Field(
        None, description="The URL of the YouTube channel that uploaded the video")
    language: Optional[str] = Field(
        None, description="The primary language of the video content")
    subtitles: dict[str, dict[str, YoutubeTranscriptionMetadata]] = Field(default_factory=dict,
                                                                          description="A dictionary of available subtitles, organized by language code and file extension")
    available_transcriptions: List[str] = Field(default_factory=list,
                                                description="A list of available transcription languages")
    upload_date: Optional[datetime] = Field(
        None, description="The date and time when the video was uploaded")
    thumbnail: Optional[str] = Field(
        None, description="The URL of the video thumbnail image")


class VideoMetadata(BaseModel):
    title: str = Field(
        default="", description="The title of the video")
    full_title: Optional[str] = Field(None,
        description="The full title of the video")
    description: str = Field(
        default="", description="The description of the video")
    duration: Optional[float] = Field(
        None, description="The duration of the video in seconds")
    duration_string: Optional[str] = Field(None,
        description="A human-readable string representation of the video duration")
    uploader: Optional[str] = Field(
        None, description="Name of the uploader/channel")
    uploader_url: Optional[str] = Field(
        None, description="URL of the uploader/channel page")
    platform: Optional[str] = Field(
        None, description="Name of the platform (e.g. vimeo, instagram)")
    original_url: Optional[str] = Field(
        None, description="The original URL of the video")
    upload_date: Optional[datetime] = Field(
        None, description="The date when the video was uploaded")
    thumbnail: Optional[str] = Field(
        None, description="The URL of the video thumbnail image")
    language: Optional[str] = Field(
        None, description="The primary language of the video content")
    subtitles: dict[str, dict[str, YoutubeTranscriptionMetadata]] = Field(
        default_factory=dict,
        description="Available subtitles organized by language and format")
    available_transcriptions: List[str] = Field(
        default_factory=list,
        description="List of available transcription languages")


class VideoTranscribe(BaseModel):
    url: str
    lang: LANG_CODE = Field(default=LANG_CODE.POLISH,
                            title="Video language as ISO-639-1 code like PL, EN")
    response_format: WHISPER_RESPONSE_FORMAT = Field(
        default=WHISPER_RESPONSE_FORMAT.SRT, title="Response format")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "https://vimeo.com/123456789",
                    "lang": "en",
                    "response_format": "srt"
                }
            ]
        }
    }


class VideoSummarize(BaseModel):
    url: str
    type: SUMMARIZATION_TYPE = Field(
        default=SUMMARIZATION_TYPE.TLDR, title="Type of summarization")
    lang: LANG_CODE = Field(default=LANG_CODE.POLISH,
                            title="Language code of transcription and final summarization text")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "https://vimeo.com/123456789",
                    "type": "detailed",
                    "lang": "en"
                }
            ]
        }
    }


class VideoInfoRequest(BaseModel):
    url: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "https://vimeo.com/123456789"
                }
            ]
        }
    }


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class UserBase(BaseModel):
    username: str
    email: EmailStr | None = None


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserInDB(BaseModel):
    id: UUID4
    username: str
    email: EmailStr
    hashed_password: str
    is_active: bool = True

    class Config:
        from_attributes = True


class User(UserBase):
    id: UUID4
    is_active: bool

    class Config:
        from_attributes = True
