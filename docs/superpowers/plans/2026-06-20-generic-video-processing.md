# Generic Video Processing Endpoints (Vimeo, Instagram, etc.)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/video` endpoint group that processes URLs from any yt-dlp-supported platform (Vimeo, Instagram, TikTok, Dailymotion, etc.) with the same transcription, summarization, logging, and artifact-saving logic already used for YouTube and audio.

**Architecture:** A new `app/video/` module mirrors `app/youtube/` with a generic `VideoAudioLoader` (yt-dlp without YouTube-specific options) and a `get_video_metadata()` function. A new `app/routers/video.py` router exposes `/video/transcribe`, `/video/summarize`, and `/video/details` endpoints. The existing `transcribe()`, `summarize()`, `register_new_process()`, `register_process_artifact()` infrastructure is reused as-is.

**Tech Stack:** FastAPI, yt-dlp, Pydantic v2, SQLAlchemy, OpenAI Whisper API, LangChain, Alembic

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `app/video/__init__.py` | Package marker |
| Create | `app/video/loader.py` | `VideoAudioLoader` – yt-dlp download for generic URLs |
| Create | `app/video/metadata.py` | `get_video_metadata()` – extract metadata via yt-dlp |
| Create | `app/routers/video.py` | FastAPI router: `/video/transcribe`, `/video/summarize`, `/video/details` |
| Modify | `app/models.py` | Add `VideoTranscribe`, `VideoSummarize`, `VideoInfoRequest`, `VideoMetadata` Pydantic models |
| Modify | `app/schema/models.py` | Add `RequestType.VIDEO` enum value |
| Modify | `app/processing/processing.py` | Handle `RequestType.VIDEO` in `register_new_process()` |
| Modify | `app/main.py` | Register `video_router` |
| Create | `alembic/versions/add_video_request_type.py` | DB migration for `RequestType.VIDEO` |
| Create | `tests/test_video.py` | Unit tests for video endpoints |

---

### Task 1: Add `RequestType.VIDEO` to schema enums

**Files:**
- Modify: `app/schema/models.py:23-27`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_video.py
from app.schema.models import RequestType


def test_video_request_type_exists():
    assert RequestType.VIDEO.value == "video"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_video.py::test_video_request_type_exists -v`
Expected: FAIL with `AttributeError: 'VIDEO' is not a member of 'RequestType'`

- [ ] **Step 3: Add VIDEO to RequestType enum**

In `app/schema/models.py`, change:

```python
class RequestType(enum.Enum):
    AUDIO = "audio"
    TEXT = "text"
    FILE = "file"
    YOUTUBE = "youtube"
```

to:

```python
class RequestType(enum.Enum):
    AUDIO = "audio"
    TEXT = "text"
    FILE = "file"
    YOUTUBE = "youtube"
    VIDEO = "video"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_video.py::test_video_request_type_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schema/models.py tests/test_video.py
git commit -m "feat: add VIDEO request type to schema enums"
```

---

### Task 2: Handle `RequestType.VIDEO` in processing module

**Files:**
- Modify: `app/processing/processing.py:17-26`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_video.py  (append to existing file)
from unittest.mock import patch, MagicMock
from app.processing.processing import register_new_process
from app.schema.models import RequestType, UserProcessSourceType


def test_register_new_process_video_type():
    mock_user = MagicMock()
    mock_user.id = "00000000-0000-0000-0000-000000000001"

    mock_request = MagicMock()
    mock_request.url = "http://test"
    mock_request.method = "POST"

    mock_db = MagicMock()
    mock_process = MagicMock()
    mock_process.id = "00000000-0000-0000-0000-000000000002"
    mock_db.return_value = mock_db
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.refresh = MagicMock(side_effect=lambda p: setattr(p, 'id', mock_process.id))
    mock_db.close = MagicMock()

    with patch('app.processing.processing.get_session_maker', return_value=lambda: mock_db):
        result = register_new_process(
            mock_user,
            RequestType.VIDEO,
            request=mock_request,
            request_data={"url": "https://vimeo.com/123"}
        )

    call_args = mock_db.add.call_args[0][0]
    assert call_args.source_type == UserProcessSourceType.URL
    assert call_args.type == RequestType.VIDEO
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_video.py::test_register_new_process_video_type -v`
Expected: FAIL with `ValueError: Invalid request type: RequestType.VIDEO`

- [ ] **Step 3: Add VIDEO case to register_new_process**

In `app/processing/processing.py`, change the match statement:

```python
        match(request_type):
            case RequestType.AUDIO:
                source_type = UserProcessSourceType.FILE
            case RequestType.TEXT:
                source_type = UserProcessSourceType.URL
            case RequestType.YOUTUBE:
                source_type = UserProcessSourceType.URL
            case _:
                raise ValueError(f"Invalid request type: {request_type}")
```

to:

```python
        match(request_type):
            case RequestType.AUDIO:
                source_type = UserProcessSourceType.FILE
            case RequestType.TEXT:
                source_type = UserProcessSourceType.URL
            case RequestType.YOUTUBE:
                source_type = UserProcessSourceType.URL
            case RequestType.VIDEO:
                source_type = UserProcessSourceType.URL
            case _:
                raise ValueError(f"Invalid request type: {request_type}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_video.py::test_register_new_process_video_type -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/processing/processing.py tests/test_video.py
git commit -m "feat: handle VIDEO request type in process registration"
```

---

### Task 3: Create `VideoAudioLoader`

**Files:**
- Create: `app/video/__init__.py`
- Create: `app/video/loader.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_video.py  (append to existing file)
from unittest.mock import patch, MagicMock
from app.video.loader import VideoAudioLoader


def test_video_audio_loader_init():
    loader = VideoAudioLoader(["https://vimeo.com/123456"], "/tmp/test_save")
    assert loader.urls == ["https://vimeo.com/123456"]
    assert loader.save_dir == "/tmp/test_save"
    assert loader.proxy_servers is None


def test_video_audio_loader_init_with_proxy():
    loader = VideoAudioLoader(
        ["https://vimeo.com/123456"],
        "/tmp/test_save",
        proxy_servers=["http://proxy1:8080"]
    )
    assert loader.proxy_servers == ["http://proxy1:8080"]


def test_video_audio_loader_urls_must_be_list():
    try:
        VideoAudioLoader("https://vimeo.com/123456", "/tmp/test_save")
        assert False, "Should have raised TypeError"
    except TypeError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_video.py::test_video_audio_loader_init -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.video'`

- [ ] **Step 3: Create the video package and loader**

Create `app/video/__init__.py` (empty file).

Create `app/video/loader.py`:

```python
import logging
import random
from typing import Iterable, List

from langchain_community.document_loaders.blob_loaders import FileSystemBlobLoader
from langchain_community.document_loaders.blob_loaders.schema import Blob, BlobLoader


class VideoAudioLoader(BlobLoader):
    """Load video URLs from any yt-dlp-supported platform as audio file(s)."""

    def __init__(self, urls: List[str], save_dir: str, proxy_servers: List[str] = None):
        if not isinstance(urls, list):
            raise TypeError("urls must be a list")

        self.urls = urls
        self.save_dir = save_dir
        self.proxy_servers = proxy_servers

    def random_proxy(self):
        return random.choice(self.proxy_servers)

    def yield_blobs(self) -> Iterable[Blob]:
        """Yield audio blobs for each url."""

        try:
            import yt_dlp
        except ImportError:
            raise ImportError(
                "yt_dlp package not found, please install it with "
                "`pip install yt_dlp`"
            )

        ydl_opts = {
            "format": "m4a/bestaudio/best",
            "noplaylist": True,
            "outtmpl": self.save_dir + "/%(title)s.%(ext)s",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                }
            ],
            "verbose": True,
        }

        trial = 1
        max_trials = 3

        def contains_keywords(exception: Exception, keywords: list) -> bool:
            return any(keyword in str(exception).lower() for keyword in keywords)

        while trial < max_trials:
            logging.debug(f"Download video {self.urls}, trial {trial}/{max_trials}")
            if self.proxy_servers:
                ydl_opts["proxy"] = self.random_proxy()

            retcode = None
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    retcode = ydl.download(self.urls)

                break
            except Exception as e:
                logging.warning(
                    f"Got exception: {e} code={retcode}, trying to download again (trial: {trial}/{max_trials})")

                keywords = ["sign in", "login", "login_required", "bot", "429", "rate limit", "forbidden"]
                if contains_keywords(e, keywords):
                    trial += 1
                    if trial == max_trials:
                        raise e
                else:
                    logging.warning(f"Exception '{e}' does not contain retryable keywords, raising exception higher")
                    raise e

        loader = FileSystemBlobLoader(self.save_dir, glob="*.m4a")
        for blob in loader.yield_blobs():
            yield blob
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_video.py::test_video_audio_loader_init tests/test_video.py::test_video_audio_loader_init_with_proxy tests/test_video.py::test_video_audio_loader_urls_must_be_list -v`
Expected: PASS (all 3)

- [ ] **Step 5: Commit**

```bash
git add app/video/__init__.py app/video/loader.py tests/test_video.py
git commit -m "feat: add VideoAudioLoader for generic yt-dlp video download"
```

---

### Task 4: Create video metadata extraction

**Files:**
- Create: `app/video/metadata.py`
- Modify: `app/models.py` (add `VideoMetadata` model)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_video.py  (append to existing file)
from app.models import VideoMetadata


def test_video_metadata_model():
    metadata = VideoMetadata(
        title="Test Video",
        description="A test video",
        duration=120.5,
        duration_string="2:00",
        platform="vimeo",
        original_url="https://vimeo.com/123456",
    )
    assert metadata.title == "Test Video"
    assert metadata.platform == "vimeo"
    assert metadata.duration == 120.5
    assert metadata.thumbnail is None
    assert metadata.uploader is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_video.py::test_video_metadata_model -v`
Expected: FAIL with `ImportError: cannot import name 'VideoMetadata' from 'app.models'`

- [ ] **Step 3: Add VideoMetadata model to app/models.py**

Append to `app/models.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_video.py::test_video_metadata_model -v`
Expected: PASS

- [ ] **Step 5: Create `app/video/metadata.py`**

```python
import logging
import random

import yt_dlp

from app.cache import conditional_lru_cache
from app.models import VideoMetadata, YoutubeTranscriptionMetadata
from app.settings import get_settings
from app.youtube.proxy import proxy_servers


@conditional_lru_cache
def get_video_metadata(video_url: str) -> VideoMetadata:
    info = extract_video_info(video_url)

    video_all_subtitles = info.get('subtitles', {})
    subtitles_metadata = {}
    if video_all_subtitles:
        for lang_code in video_all_subtitles:
            sub_lang_versions = {}

            for subtitle_version in video_all_subtitles[lang_code]:
                name = ""
                if hasattr(subtitle_version, "name"):
                    name = subtitle_version["name"]
                else:
                    name = subtitle_version.get("protocol", "N/A")

                sub_lang_versions[subtitle_version["ext"]] = YoutubeTranscriptionMetadata(
                    ext=subtitle_version["ext"],
                    url=subtitle_version["url"],
                    name=name
                )

            subtitles_metadata[lang_code] = sub_lang_versions

    metadata = VideoMetadata(
        title=info.get('title', ''),
        full_title=info.get('fulltitle', None),
        description=info.get('description', ''),
        duration=info.get('duration'),
        duration_string=info.get('duration_string'),
        uploader=info.get('uploader', None),
        uploader_url=info.get('uploader_url', None) or info.get('channel_url', None),
        platform=info.get('extractor_key', None) or info.get('extractor', None),
        original_url=info.get('original_url', video_url),
        upload_date=info.get('upload_date'),
        thumbnail=info.get('thumbnail', None),
        language=info.get('language', None),
        subtitles=subtitles_metadata,
        available_transcriptions=list(subtitles_metadata.keys()),
    )

    return metadata


def extract_video_info(video_url: str):
    logging.info(f"Extracting video info for {video_url}...")

    ydl_opts = {
        'skip_download': True,
        'quiet': True,
    }

    proxys = proxy_servers()
    if get_settings().use_proxy and proxys:
        proxy = random.choice(proxys)
        ydl_opts["proxy"] = proxy
        logging.debug(f"Using '{proxy}' to get video details.")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)

    return info
```

- [ ] **Step 6: Run all video tests**

Run: `pytest tests/test_video.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/models.py app/video/metadata.py tests/test_video.py
git commit -m "feat: add VideoMetadata model and metadata extraction"
```

---

### Task 5: Add Pydantic request models for video endpoints

**Files:**
- Modify: `app/models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_video.py  (append to existing file)
from app.models import VideoTranscribe, VideoSummarize, VideoInfoRequest
from app.transcribe.transcription import LANG_CODE, WHISPER_RESPONSE_FORMAT
from app.models import SUMMARIZATION_TYPE


def test_video_transcribe_model_defaults():
    req = VideoTranscribe(url="https://vimeo.com/123456")
    assert req.url == "https://vimeo.com/123456"
    assert req.lang == LANG_CODE.POLISH
    assert req.response_format == WHISPER_RESPONSE_FORMAT.SRT


def test_video_summarize_model_defaults():
    req = VideoSummarize(url="https://vimeo.com/123456")
    assert req.url == "https://vimeo.com/123456"
    assert req.type == SUMMARIZATION_TYPE.TLDR
    assert req.lang == LANG_CODE.POLISH


def test_video_info_request_model():
    req = VideoInfoRequest(url="https://www.instagram.com/reel/abc123")
    assert req.url == "https://www.instagram.com/reel/abc123"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_video.py::test_video_transcribe_model_defaults tests/test_video.py::test_video_summarize_model_defaults tests/test_video.py::test_video_info_request_model -v`
Expected: FAIL with `ImportError: cannot import name 'VideoTranscribe' from 'app.models'`

- [ ] **Step 3: Add video request models to app/models.py**

Append to `app/models.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_video.py::test_video_transcribe_model_defaults tests/test_video.py::test_video_summarize_model_defaults tests/test_video.py::test_video_info_request_model -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_video.py
git commit -m "feat: add Pydantic request models for video endpoints"
```

---

### Task 6: Create video transcription function

**Files:**
- Create: `app/video/transcription.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_video.py  (append to existing file)
from unittest.mock import patch, MagicMock
from app.video.transcription import video_transcribe
from app.transcribe.transcription import LANG_CODE, WHISPER_RESPONSE_FORMAT


@patch('app.video.transcription.GenericLoader')
@patch('app.video.transcription.get_settings')
def test_video_transcribe_returns_text(mock_settings, mock_generic_loader):
    mock_settings_obj = MagicMock()
    mock_settings_obj.openai_api_key = "test-key"
    mock_settings_obj.proxy_servers = ""
    mock_settings_obj.use_proxy = False
    mock_settings.return_value = mock_settings_obj

    mock_doc = MagicMock()
    mock_doc.page_content = "Hello, this is a test transcription."
    mock_generic_loader.return_value.load.return_value = [mock_doc]

    result = video_transcribe(
        "https://vimeo.com/123",
        "/tmp/test",
        LANG_CODE.ENGLISH,
        WHISPER_RESPONSE_FORMAT.TEXT
    )

    assert result == "Hello, this is a test transcription."
    mock_generic_loader.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_video.py::test_video_transcribe_returns_text -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.video.transcription'`

- [ ] **Step 3: Create `app/video/transcription.py`**

```python
import logging

import langsmith as ls
from langchain_community.document_loaders.generic import GenericLoader

from app.cache import conditional_lru_cache
from app.settings import get_settings
from app.transcribe.transcription import LANG_CODE, WHISPER_RESPONSE_FORMAT, convert_response_format
from app.transcribe.OpenAIWhisperParser import OpenAIWhisperParser
from app.video.loader import VideoAudioLoader


@ls.traceable(
    run_type="llm",
    name="Video Transcription",
    tags=["video", "transcription"],
    metadata={"flow": "transcription"}
)
@conditional_lru_cache
def video_transcribe(url: str,
                     save_dir: str,
                     lang: LANG_CODE,
                     response_format: WHISPER_RESPONSE_FORMAT):
    logging.info(
        f"Processing video url: {url}, save_dir: {save_dir}, lang: {lang}, response_format: {response_format}")

    settings = get_settings()
    proxy_servers = settings.proxy_servers.split(
        ",") if settings.proxy_servers and settings.use_proxy else None

    logging.debug(
        f"Proxy servers: {proxy_servers} - using proxy: {settings.use_proxy}")

    loader = GenericLoader(VideoAudioLoader([url], save_dir, proxy_servers),
                           OpenAIWhisperParser(api_key=settings.openai_api_key,
                                               language=lang.value,
                                               response_format=convert_response_format(
                                                   response_format),
                                               temperature=0
                                               ))
    docs = loader.load()

    return " ".join([doc.page_content for doc in docs])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_video.py::test_video_transcribe_returns_text -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/video/transcription.py tests/test_video.py
git commit -m "feat: add video_transcribe function for generic video URLs"
```

---

### Task 7: Create video router

**Files:**
- Create: `app/routers/video.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_video.py  (append to existing file)
import importlib


def test_video_router_module_loads():
    mod = importlib.import_module("app.routers.video")
    assert hasattr(mod, "video_router")


def test_video_router_has_transcribe_endpoint():
    mod = importlib.import_module("app.routers.video")
    router = mod.video_router
    paths = [route.path for route in router.routes]
    assert "/transcribe" in paths


def test_video_router_has_summarize_endpoint():
    mod = importlib.import_module("app.routers.video")
    router = mod.video_router
    paths = [route.path for route in router.routes]
    assert "/summarize" in paths


def test_video_router_has_details_endpoint():
    mod = importlib.import_module("app.routers.video")
    router = mod.video_router
    paths = [route.path for route in router.routes]
    assert "/details" in paths
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_video.py::test_video_router_module_loads -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create `app/routers/video.py`**

```python
import hashlib
import logging

from fastapi import APIRouter, Request, Depends, Response, status
from fastapi.responses import FileResponse
from starlette.responses import PlainTextResponse

from app.auth import get_current_active_user
from app.models import (
    VideoTranscribe, VideoSummarize, VideoInfoRequest,
    VideoMetadata, SummaryResult, ApiProcessingResult,
)
from app.processing.processing import (
    complete_process, process_failed, register_new_process,
    register_process_artifact, update_process_status,
)
from app.schema.models import ProcessArtifactFormat, ProcessArtifactType, RequestStatus, RequestType
from app.schema.pydantic_models import CompletedProcess, User
from app.summary.summarization import summarize
from app.transcribe.transcription import WHISPER_RESPONSE_FORMAT
from app.video.metadata import get_video_metadata
from app.video.transcription import video_transcribe

video_router = APIRouter(
    prefix="/video",
    tags=["video", "transcription", "summarization"],
    dependencies=[Depends(get_current_active_user)]
)


def save_dir_path(url: str) -> str:
    hash_object = hashlib.md5(url.encode())
    hash_hex = hash_object.hexdigest()
    return f"./downloads/video/{hash_hex}/"


@video_router.post(
    "/transcribe",
    response_model=ApiProcessingResult,
    responses={
        200: {
            "description": "Transcription result. Content type depends on the `Accept` request header.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": True, "error": None, "transcription": "Hello world", "format": "srt"},
                },
                "text/plain": {
                    "schema": {"type": "string"},
                    "example": "Hello world",
                },
            },
        },
        500: {
            "description": "Internal server error during transcription.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": False, "error": "Internal server error: <details>", "text": None},
                }
            },
        },
    },
)
def video_transcription(
        request: Request,
        video_request: VideoTranscribe,
        response: Response,
        current_user: User = Depends(get_current_active_user)
):
    process_id = None
    try:
        logging.info(f"video transcribe - request details: {video_request}")

        process_id = register_new_process(
            current_user,
            request_type=RequestType.VIDEO,
            request=request,
            request_data={"video_request": video_request.model_dump()}
        )

        save_dir = save_dir_path(video_request.url)
        transcription = video_transcribe(
            video_request.url,
            save_dir,
            video_request.lang,
            video_request.response_format)

        update_process_status(process_id, CompletedProcess(
            user_id=current_user.id,
            status=RequestStatus.COMPLETED,
            result=transcription,
            result_format=ProcessArtifactFormat.TEXT,
            lang=video_request.lang,
            type=ProcessArtifactType.TRANSCRIPTION
        ))

        accept_header = request.headers.get("Accept", "application/json")
        if accept_header == "text/plain":
            return PlainTextResponse(transcription)
        else:
            return ApiProcessingResult(
                result=True, error=None,
                transcription=transcription,
                format=video_request.response_format)
    except Exception as e:
        logging.error(f"Error processing video transcription: {str(e)}")

        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            result=False,
            error=f"Internal server error: {str(e)}",
        )


@video_router.post(
    "/summarize",
    response_model=SummaryResult,
    responses={
        200: {
            "description": "Summarization result. Content type depends on the `Accept` request header.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/SummaryResult"},
                    "example": {"summary": "The video covers the main highlights..."},
                },
                "text/plain": {
                    "schema": {"type": "string"},
                    "example": "The video covers the main highlights...",
                },
                "text/srt": {
                    "schema": {"type": "string", "format": "binary"},
                    "example": "1\n00:00:01,000 --> 00:00:05,000\nHello world",
                },
            },
        },
        500: {
            "description": "Internal server error during transcription or summarization.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": False, "error": "Error processing video summarization", "text": "<details>"},
                }
            },
        },
    },
)
def video_summarize(
        request: Request,
        video_request: VideoSummarize,
        response: Response,
        current_user: User = Depends(get_current_active_user)
):
    process_id = None
    try:
        logging.info(f"video summarize - Request details: {video_request}")

        process_id = register_new_process(
            current_user,
            RequestType.VIDEO,
            request=request,
            request_data={"video_request": video_request.model_dump()}
        )

        save_dir = save_dir_path(video_request.url)

        transcription = video_transcribe(
            video_request.url, save_dir, video_request.lang,
            WHISPER_RESPONSE_FORMAT.TEXT)

        register_process_artifact(
            current_user, process_id,
            ProcessArtifactType.TRANSCRIPTION,
            transcription,
            ProcessArtifactFormat.TEXT, video_request.lang)

        summarization = summarize(
            transcription, video_request.type, video_request.lang)
        register_process_artifact(
            current_user, process_id,
            ProcessArtifactType.SUMMARY,
            summarization,
            ProcessArtifactFormat.TEXT, video_request.lang)

        logging.debug(f"video summarize - Result: \n{summarization}")

        complete_process(process_id)

        accept_header = request.headers.get("Accept", "application/json")
        if accept_header == "text/plain":
            return PlainTextResponse(summarization)
        elif accept_header == "text/srt":
            return FileResponse(transcription, media_type="text/srt")
        else:
            return SummaryResult(summary=summarization)
    except Exception as e:
        logging.error(f"Error processing video summarization: '{str(e)}'")

        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            result=False,
            error="Error processing video summarization",
            text=str(e))


@video_router.post(
    "/details",
    response_model=VideoMetadata | ApiProcessingResult,
    responses={
        200: {
            "description": "Video metadata.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/VideoMetadata"},
                    "example": {
                        "title": "Example Video",
                        "duration": 120.0,
                        "duration_string": "2:00",
                        "description": "Video description here.",
                        "platform": "Vimeo",
                        "uploader": "Example User",
                    },
                }
            },
        },
        500: {
            "description": "Internal server error while fetching video metadata.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ApiProcessingResult"},
                    "example": {"result": False, "error": "Error extracting video details: <details>", "text": "<details>"},
                }
            },
        },
    },
)
def video_details(
        request: VideoInfoRequest,
        response: Response,
        current_user: User = Depends(get_current_active_user)
):
    try:
        logging.info(f"Getting video details: {request.url}")

        metadata = get_video_metadata(request.url)

        return metadata
    except Exception as e:
        logging.error(f"Error fetching video details: {str(e)}")

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            result=False,
            error=f"Error extracting video details: {str(e)}",
            text=str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_video.py::test_video_router_module_loads tests/test_video.py::test_video_router_has_transcribe_endpoint tests/test_video.py::test_video_router_has_summarize_endpoint tests/test_video.py::test_video_router_has_details_endpoint -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routers/video.py tests/test_video.py
git commit -m "feat: add video router with transcribe, summarize, and details endpoints"
```

---

### Task 8: Register video router in main.py

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_video.py  (append to existing file)

def test_video_router_prefix():
    from app.routers.video import video_router
    assert video_router.prefix == "/video"
    assert "video" in video_router.tags
```

- [ ] **Step 2: Add video router imports and registration to main.py**

In `app/main.py`, add the import after the existing router imports:

```python
from app.routers.video import video_router
```

Add the router to the protected app (after `protected_app.include_router(artifacts_router)`):

```python
protected_app.include_router(video_router)
```

Add the router to the main app (after `app.include_router(artifacts_router)`):

```python
app.include_router(video_router)
```

The full relevant section of `app/main.py` after changes:

```python
from app.routers.audio import a_router
from app.routers.auth import auth_router
from app.routers.youtube import yt_router
from app.routers.artifacts import router as artifacts_router
from app.routers.video import video_router

# ... (existing code) ...

# Include routers in the protected app
protected_app.include_router(a_router)
protected_app.include_router(yt_router)
protected_app.include_router(artifacts_router)
protected_app.include_router(artifacts_router)
protected_app.include_router(video_router)

# Include the protected app and auth router in the main app
app.mount("/api", protected_app)
app.include_router(auth_router)
app.include_router(yt_router)
app.include_router(a_router)
app.include_router(artifacts_router)
app.include_router(video_router)
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_video.py::test_video_router_prefix -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/main.py tests/test_video.py
git commit -m "feat: register video router in main app"
```

---

### Task 9: Create Alembic migration for VIDEO request type

**Files:**
- Create: `alembic/versions/add_video_request_type.py`

- [ ] **Step 1: Generate the migration**

Run: `cd /Users/michmzr/1.Projects/transition-summarize-py && alembic revision --autogenerate -m "add_video_request_type"`

- [ ] **Step 2: Edit the generated migration file**

Replace the auto-generated `upgrade()` and `downgrade()` functions with:

```python
from alembic import op


def upgrade() -> None:
    op.execute("ALTER TYPE requesttype ADD VALUE IF NOT EXISTS 'video'")


def downgrade() -> None:
    pass
```

Note: PostgreSQL does not support removing values from enum types, so downgrade is a no-op. This is standard practice.

- [ ] **Step 3: Verify migration syntax**

Run: `cd /Users/michmzr/1.Projects/transition-summarize-py && python -c "import importlib; m = importlib.import_module('alembic.versions'); print('OK')"`

This just checks the file is importable without errors.

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/*add_video_request_type*.py
git commit -m "migration: add 'video' value to requesttype enum"
```

---

### Task 10: Integration-style tests for video router

**Files:**
- Modify: `tests/test_video.py`

- [ ] **Step 1: Add integration-level tests with mocked dependencies**

```python
# tests/test_video.py  (append to existing file)
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from app.routers.video import video_router


def _create_test_app():
    test_app = FastAPI()
    test_app.include_router(video_router)
    return test_app


@patch('app.routers.video.get_current_active_user')
@patch('app.routers.video.register_new_process')
@patch('app.routers.video.video_transcribe')
@patch('app.routers.video.update_process_status')
def test_video_transcribe_endpoint_success(
    mock_update, mock_transcribe, mock_register, mock_auth
):
    mock_auth.return_value = MagicMock(id="user-1", username="test", email="t@t.com", is_active=True)
    mock_register.return_value = "process-uuid-1"
    mock_transcribe.return_value = "Transcribed text from Vimeo video."

    app = _create_test_app()
    app.dependency_overrides[get_current_active_user] = lambda: mock_auth.return_value
    client = TestClient(app)

    resp = client.post(
        "/video/transcribe",
        json={"url": "https://vimeo.com/123456", "lang": "en", "response_format": "text"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] is True
    assert data["transcription"] == "Transcribed text from Vimeo video."


@patch('app.routers.video.get_current_active_user')
@patch('app.routers.video.register_new_process')
@patch('app.routers.video.video_transcribe')
@patch('app.routers.video.register_process_artifact')
@patch('app.routers.video.summarize')
@patch('app.routers.video.complete_process')
def test_video_summarize_endpoint_success(
    mock_complete, mock_summarize, mock_artifact,
    mock_transcribe, mock_register, mock_auth
):
    mock_auth.return_value = MagicMock(id="user-1", username="test", email="t@t.com", is_active=True)
    mock_register.return_value = "process-uuid-1"
    mock_transcribe.return_value = "Transcribed text."
    mock_summarize.return_value = "This is a summary of the video."

    app = _create_test_app()
    app.dependency_overrides[get_current_active_user] = lambda: mock_auth.return_value
    client = TestClient(app)

    resp = client.post(
        "/video/summarize",
        json={"url": "https://vimeo.com/123456", "type": "tldr", "lang": "en"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"] == "This is a summary of the video."


@patch('app.routers.video.get_current_active_user')
@patch('app.routers.video.get_video_metadata')
def test_video_details_endpoint_success(mock_metadata, mock_auth):
    from app.models import VideoMetadata
    from app.auth import get_current_active_user

    mock_auth.return_value = MagicMock(id="user-1", username="test", email="t@t.com", is_active=True)
    mock_metadata.return_value = VideoMetadata(
        title="Vimeo Video",
        description="A cool video",
        duration=60.0,
        duration_string="1:00",
        platform="Vimeo",
        original_url="https://vimeo.com/123456",
    )

    app = _create_test_app()
    app.dependency_overrides[get_current_active_user] = lambda: mock_auth.return_value
    client = TestClient(app)

    resp = client.post(
        "/video/details",
        json={"url": "https://vimeo.com/123456"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Vimeo Video"
    assert data["platform"] == "Vimeo"


@patch('app.routers.video.get_current_active_user')
@patch('app.routers.video.register_new_process')
@patch('app.routers.video.video_transcribe')
def test_video_transcribe_endpoint_error(mock_transcribe, mock_register, mock_auth):
    from app.auth import get_current_active_user

    mock_auth.return_value = MagicMock(id="user-1", username="test", email="t@t.com", is_active=True)
    mock_register.return_value = "process-uuid-1"
    mock_transcribe.side_effect = Exception("yt-dlp download failed")

    app = _create_test_app()
    app.dependency_overrides[get_current_active_user] = lambda: mock_auth.return_value
    client = TestClient(app)

    resp = client.post(
        "/video/transcribe",
        json={"url": "https://invalid-site.com/video", "lang": "en", "response_format": "text"},
    )
    assert resp.status_code == 500
    data = resp.json()
    assert data["result"] is False
    assert "yt-dlp download failed" in data["error"]
```

- [ ] **Step 2: Run all tests**

Run: `pytest tests/test_video.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_video.py
git commit -m "test: add integration tests for video router endpoints"
```

---

### Task 11: Final verification

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: ALL existing tests PASS, all new tests PASS

- [ ] **Step 2: Check linting**

Run: `python -m py_compile app/routers/video.py && python -m py_compile app/video/loader.py && python -m py_compile app/video/metadata.py && python -m py_compile app/video/transcription.py && echo "All files compile OK"`
Expected: "All files compile OK"

- [ ] **Step 3: Start the server and verify endpoints appear**

Run: `cd /Users/michmzr/1.Projects/transition-summarize-py && timeout 10 python -m uvicorn app.main:app --host 0.0.0.0 --port 8099 2>&1 | head -20 || true`

Then check: `curl -s http://localhost:8099/url-list | python -m json.tool | grep video`
Expected: `/video/transcribe`, `/video/summarize`, `/video/details` appear in the URL list

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete generic video processing endpoints for non-YouTube platforms"
```
