# Video Metadata in API Responses — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Return fetched video metadata (title, description, duration, etc.) in the response bodies of transcription and summarization endpoints. Additionally, use metadata as context for the generic `/video/summarize` endpoint (matching existing YouTube behavior).

**Architecture:** yt-dlp already extracts descriptions and metadata for both YouTube and generic video URLs. The YouTube `/summarize` already uses metadata as LLM context via `build_youtube_summary_input()`, but no endpoint currently returns metadata in its response. We extend the response models with an optional `metadata` field and populate it in all relevant endpoints. For `/video/summarize`, we also add metadata-enriched summarization context (mirroring YouTube).

**Tech Stack:** Python, FastAPI, Pydantic v2, yt-dlp

---

### Task 1: Add `metadata` field to response models

**Files:**
- Modify: `app/models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models_metadata.py
def test_summary_result_accepts_metadata():
    from app.models import SummaryResult
    result = SummaryResult(summary="Test summary", metadata={"title": "Video", "description": "Desc"})
    assert result.metadata == {"title": "Video", "description": "Desc"}


def test_summary_result_metadata_defaults_to_none():
    from app.models import SummaryResult
    result = SummaryResult(summary="Test summary")
    assert result.metadata is None


def test_api_processing_result_accepts_metadata():
    from app.models import ApiProcessingResult
    result = ApiProcessingResult(result=True, metadata={"title": "Video"})
    assert result.metadata == {"title": "Video"}


def test_api_processing_result_metadata_defaults_to_none():
    from app.models import ApiProcessingResult
    result = ApiProcessingResult(result=True)
    assert result.metadata is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models_metadata.py -v`
Expected: FAIL with validation error (metadata field not recognized)

- [ ] **Step 3: Add metadata field to SummaryResult and ApiProcessingResult**

In `app/models.py`, add `metadata` to both models:

```python
class ApiProcessingResult(BaseModel):
    result: bool = Field(title="Success or error")
    error: Optional[str] = Field(default=None, title="Error description")
    text: Optional[str] = Field(default=None, title="Video transcription")
    transcription: Optional[str] = Field(default=None, title="Transcription text")
    format: Optional[WHISPER_RESPONSE_FORMAT] = Field(default=None, title="Response format")
    metadata: Optional[dict] = Field(default=None, title="Video metadata (title, description, duration, etc.)")


class SummaryResult(BaseModel):
    summary: str
    metadata: Optional[dict] = Field(default=None, title="Video metadata (title, description, duration, etc.)")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models_metadata.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models_metadata.py
git commit -m "feat: add optional metadata field to API response models"
```

---

### Task 2: Return metadata in YouTube `/transcribe` response

**Files:**
- Modify: `app/routers/youtube.py`
- Test: `tests/test_yt.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_yt.py`:

```python
@patch('app.routers.youtube.get_current_active_user')
@patch('app.routers.youtube.register_new_process')
@patch('app.routers.youtube.yt_transcribe')
@patch('app.routers.youtube.get_youtube_metadata')
@patch('app.routers.youtube.update_process_status')
def test_youtube_transcribe_returns_metadata_in_response(
        mock_update, mock_metadata, mock_transcribe, mock_register, mock_auth):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth import get_current_active_user
    from app.models import YoutubeMetadata
    from app.routers.youtube import yt_router

    mock_auth.return_value = MagicMock(
        id="00000000-0000-0000-0000-000000000001",
        username="test", email="t@t.com", is_active=True)
    mock_register.return_value = "00000000-0000-0000-0000-000000000002"
    mock_metadata.return_value = YoutubeMetadata(
        title="My Video",
        description="A great description.",
        duration=300.0,
        duration_string="5:00")
    mock_transcribe.return_value = "Hello world transcription."

    test_app = FastAPI()
    test_app.include_router(yt_router)
    test_app.dependency_overrides[get_current_active_user] = lambda: mock_auth.return_value
    client = TestClient(test_app)

    response = client.post(
        "/youtube/transcribe",
        json={"url": "https://www.youtube.com/watch?v=test", "lang": "en", "response_format": "text"})

    assert response.status_code == 200
    data = response.json()
    assert data["metadata"] is not None
    assert data["metadata"]["title"] == "My Video"
    assert data["metadata"]["description"] == "A great description."
    assert data["metadata"]["duration"] == 300.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_yt.py::test_youtube_transcribe_returns_metadata_in_response -v`
Expected: FAIL (metadata not in response or `get_youtube_metadata` not called)

- [ ] **Step 3: Modify YouTube transcribe endpoint to fetch and return metadata**

In `app/routers/youtube.py`, update `yt_transcription()`:

```python
def yt_transcription(
        request: Request,
        yt_request: YTVideoTranscribe,
        response: Response,
        current_user: User = Depends(get_current_active_user)
):
    process_id = None
    try:
        logging.info(f"yt transcribe - request details: {yt_request}")

        process_id = register_new_process(
            current_user,
            request_type=RequestType.YOUTUBE,
            request=request,
            request_data={
                "yt_request": yt_request.model_dump()}
        )

        yt_metadata = None
        try:
            yt_metadata = get_youtube_metadata(yt_request.url)
        except Exception as metadata_error:
            logging.warning(
                f"Could not fetch YouTube metadata for transcription: '{metadata_error}'")

        save_dir = save_dir_path(yt_request.url)
        transcription = yt_transcribe(
            yt_request.url,
            save_dir,
            yt_request.lang,
            yt_request.response_format)

        update_process_status(process_id, CompletedProcess(
            user_id=current_user.id,
            status=RequestStatus.COMPLETED,
            result=transcription,
            result_format=ProcessArtifactFormat.TEXT,
            lang=yt_request.lang,
            type=ProcessArtifactType.TRANSCRIPTION
        ))

        accept_header = request.headers.get("Accept", "application/json")
        if accept_header == "text/plain":
            return PlainTextResponse(transcription)
        else:
            metadata_dict = yt_metadata.model_dump(exclude={"subtitles"}) if yt_metadata else None
            return ApiProcessingResult(
                result=True, error=None,
                transcription=transcription,
                format=yt_request.response_format,
                metadata=metadata_dict)
    except Exception as e:
        logging.error(f"Error processing YouTube transcription: {str(e)}")

        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            result=False,
            error=f"Internal server error: {str(e)}",
        )
```

Key change: fetch `get_youtube_metadata` before transcription (it's cached, so reused if summarize is called next), serialize to dict excluding `subtitles` (large nested structures with URLs not useful in this context), pass to response.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_yt.py::test_youtube_transcribe_returns_metadata_in_response -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routers/youtube.py tests/test_yt.py
git commit -m "feat: return video metadata in YouTube transcribe response"
```

---

### Task 3: Return metadata in YouTube `/summarize` response

**Files:**
- Modify: `app/routers/youtube.py`
- Test: `tests/test_yt.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_yt.py`:

```python
@patch('app.routers.youtube.get_current_active_user')
@patch('app.routers.youtube.register_new_process')
@patch('app.routers.youtube.download_transcription')
@patch('app.routers.youtube.get_youtube_metadata')
@patch('app.routers.youtube.register_process_artifact')
@patch('app.routers.youtube.summarize')
@patch('app.routers.youtube.complete_process')
def test_youtube_summarize_returns_metadata_in_response(
        mock_complete, mock_summarize, mock_artifact, mock_metadata,
        mock_download_transcription, mock_register, mock_auth):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth import get_current_active_user
    from app.models import YoutubeMetadata
    from app.routers.youtube import yt_router

    mock_auth.return_value = MagicMock(
        id="00000000-0000-0000-0000-000000000001",
        username="test", email="t@t.com", is_active=True)
    mock_register.return_value = "00000000-0000-0000-0000-000000000002"
    mock_metadata.return_value = YoutubeMetadata(
        title="Talk Title",
        description="Some description.",
        duration=600.0,
        duration_string="10:00")
    mock_download_transcription.return_value = "[00:00] Hello."
    mock_summarize.return_value = "Summary of the talk."

    test_app = FastAPI()
    test_app.include_router(yt_router)
    test_app.dependency_overrides[get_current_active_user] = lambda: mock_auth.return_value
    client = TestClient(test_app)

    response = client.post(
        "/youtube/summarize",
        json={"url": "https://www.youtube.com/watch?v=test", "type": "detailed", "lang": "en", "use_yt_transcription": True})

    assert response.status_code == 200
    data = response.json()
    assert data["metadata"] is not None
    assert data["metadata"]["title"] == "Talk Title"
    assert data["metadata"]["description"] == "Some description."
    assert data["metadata"]["duration"] == 600.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_yt.py::test_youtube_summarize_returns_metadata_in_response -v`
Expected: FAIL (metadata not in response)

- [ ] **Step 3: Modify YouTube summarize endpoint to include metadata in response**

In `app/routers/youtube.py`, update the return statement in `yt_summarize()`:

Change:
```python
return SummaryResult(summary=summarization)
```

To:
```python
metadata_dict = yt_metadata.model_dump(exclude={"subtitles"}) if yt_metadata else None
return SummaryResult(summary=summarization, metadata=metadata_dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_yt.py::test_youtube_summarize_returns_metadata_in_response -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routers/youtube.py tests/test_yt.py
git commit -m "feat: return video metadata in YouTube summarize response"
```

---

### Task 4: Add metadata context to `/video/summarize` and return in response

**Files:**
- Modify: `app/routers/video.py`
- Test: `tests/test_video.py`

The `/video/summarize` currently sends raw transcription to `summarize()` without any metadata context. The YouTube equivalent already enriches the prompt with title/duration/description via `build_youtube_summary_input()`. We reuse the same pattern here with a `build_video_summary_input()` function and return metadata in the response.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_video.py`:

```python
@patch('app.routers.video.get_current_active_user')
@patch('app.routers.video.register_new_process')
@patch('app.routers.video.video_transcribe')
@patch('app.routers.video.get_video_metadata')
@patch('app.routers.video.register_process_artifact')
@patch('app.routers.video.summarize')
@patch('app.routers.video.complete_process')
def test_video_summarize_passes_metadata_context_and_returns_it(
        mock_complete, mock_summarize, mock_artifact,
        mock_metadata, mock_transcribe, mock_register, mock_auth):
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.models import VideoMetadata
    from app.routers.video import video_router
    from app.auth import get_current_active_user

    user_id = "00000000-0000-0000-0000-000000000001"
    process_id = "00000000-0000-0000-0000-000000000002"
    mock_auth.return_value = MagicMock(id=user_id, username="test", email="t@t.com", is_active=True)
    mock_register.return_value = process_id
    mock_metadata.return_value = VideoMetadata(
        title="Vimeo Talk",
        description="An insightful presentation about testing.",
        duration=900.0,
        duration_string="15:00",
        platform="Vimeo",
        original_url="https://vimeo.com/789")
    mock_transcribe.return_value = "This is the transcribed text."
    mock_summarize.return_value = "Summary of the vimeo talk."

    test_app = FastAPI()
    test_app.include_router(video_router)
    test_app.dependency_overrides[get_current_active_user] = lambda: mock_auth.return_value
    client = TestClient(test_app)

    resp = client.post(
        "/video/summarize",
        json={"url": "https://vimeo.com/789", "type": "detailed", "lang": "en"})

    assert resp.status_code == 200
    data = resp.json()

    # Verify metadata is in response
    assert data["metadata"] is not None
    assert data["metadata"]["title"] == "Vimeo Talk"
    assert data["metadata"]["description"] == "An insightful presentation about testing."

    # Verify metadata was used as context for summarization
    text_sent_to_model = mock_summarize.call_args.args[0]
    assert "Title: Vimeo Talk" in text_sent_to_model
    assert "Duration: 15:00" in text_sent_to_model
    assert "Description: An insightful presentation about testing." in text_sent_to_model
    assert "Transcript:" in text_sent_to_model
    assert "This is the transcribed text." in text_sent_to_model
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_video.py::test_video_summarize_passes_metadata_context_and_returns_it -v`
Expected: FAIL (get_video_metadata not patched/called in summarize, metadata not in response)

- [ ] **Step 3: Add `build_video_summary_input` and update video summarize endpoint**

In `app/routers/video.py`:

1. Add import for the `_trim_metadata_text` helper (extract to shared util or duplicate):

```python
from app.models import (
    VideoTranscribe, VideoSummarize, VideoInfoRequest,
    VideoMetadata, SummaryResult, ApiProcessingResult,
)
```

2. Add `build_video_summary_input` function:

```python
def _trim_metadata_text(text: str, max_length: int = 2000) -> str:
    cleaned_text = " ".join(text.split())
    if len(cleaned_text) <= max_length:
        return cleaned_text
    return f"{cleaned_text[:max_length].rstrip()}..."


def build_video_summary_input(
        transcription: str,
        metadata: VideoMetadata | None
) -> str:
    if not metadata:
        return transcription

    metadata_lines = []
    if metadata.title:
        metadata_lines.append(f"Title: {metadata.title}")
    if metadata.duration_string:
        metadata_lines.append(f"Duration: {metadata.duration_string}")
    elif metadata.duration:
        metadata_lines.append(f"Duration: {metadata.duration} seconds")
    if metadata.description:
        metadata_lines.append(
            f"Description: {_trim_metadata_text(metadata.description)}")

    if not metadata_lines:
        return transcription

    return "\n".join([
        "Video metadata:",
        *metadata_lines,
        "",
        "Transcript:",
        transcription
    ])
```

3. Update `video_summarize()` endpoint to fetch metadata, use as context, and return in response:

```python
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

        video_metadata = None
        try:
            video_metadata = get_video_metadata(video_request.url)
        except Exception as metadata_error:
            logging.warning(
                f"Could not fetch video metadata for summarization: '{metadata_error}'")

        transcription = video_transcribe(
            video_request.url, save_dir, video_request.lang,
            WHISPER_RESPONSE_FORMAT.TEXT)

        if not transcription.strip():
            raise ValueError(
                "No transcription generated from video audio. The source may have no detectable speech.")

        register_process_artifact(
            current_user, process_id,
            ProcessArtifactType.TRANSCRIPTION,
            transcription,
            ProcessArtifactFormat.TEXT, video_request.lang)

        summary_input = build_video_summary_input(transcription, video_metadata)
        summarization = summarize(
            summary_input, video_request.type, video_request.lang)
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
            metadata_dict = video_metadata.model_dump(exclude={"subtitles"}) if video_metadata else None
            return SummaryResult(summary=summarization, metadata=metadata_dict)
    except Exception as e:
        logging.error(f"Error processing video summarization: '{str(e)}'")

        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            result=False,
            error="Error processing video summarization",
            text=str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_video.py::test_video_summarize_passes_metadata_context_and_returns_it -v`
Expected: PASS

- [ ] **Step 5: Run existing video tests to verify no regressions**

Run: `uv run pytest tests/test_video.py -v`
Expected: All existing tests PASS (the existing `test_video_summarize_endpoint_success` test does not mock `get_video_metadata` — it needs updating since the function is now called. Add patch for it.)

- [ ] **Step 6: Fix existing test for video summarize**

Update `test_video_summarize_endpoint_success` in `tests/test_video.py` to also mock `get_video_metadata`:

```python
@patch('app.routers.video.get_current_active_user')
@patch('app.routers.video.register_new_process')
@patch('app.routers.video.video_transcribe')
@patch('app.routers.video.get_video_metadata')
@patch('app.routers.video.register_process_artifact')
@patch('app.routers.video.summarize')
@patch('app.routers.video.complete_process')
def test_video_summarize_endpoint_success(
    mock_complete, mock_summarize, mock_artifact,
    mock_metadata, mock_transcribe, mock_register, mock_auth
):
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.routers.video import video_router
    from app.auth import get_current_active_user

    user_id = "00000000-0000-0000-0000-000000000001"
    process_id = "00000000-0000-0000-0000-000000000002"
    mock_auth.return_value = MagicMock(id=user_id, username="test", email="t@t.com", is_active=True)
    mock_register.return_value = process_id
    mock_metadata.return_value = None
    mock_transcribe.return_value = "Transcribed text."
    mock_summarize.return_value = "This is a summary of the video."

    test_app = FastAPI()
    test_app.include_router(video_router)
    test_app.dependency_overrides[get_current_active_user] = lambda: mock_auth.return_value
    client = TestClient(test_app)

    resp = client.post(
        "/video/summarize",
        json={"url": "https://vimeo.com/123456", "type": "tldr", "lang": "en"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"] == "This is a summary of the video."
```

Also update `test_video_summarize_endpoint_rejects_empty_transcription` similarly with the `get_video_metadata` patch.

- [ ] **Step 7: Commit**

```bash
git add app/routers/video.py tests/test_video.py
git commit -m "feat: fetch metadata for video summarization context and return in response"
```

---

### Task 5: Return metadata in `/video/transcribe` response

**Files:**
- Modify: `app/routers/video.py`
- Test: `tests/test_video.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_video.py`:

```python
@patch('app.routers.video.get_current_active_user')
@patch('app.routers.video.register_new_process')
@patch('app.routers.video.video_transcribe')
@patch('app.routers.video.get_video_metadata')
@patch('app.routers.video.update_process_status')
def test_video_transcribe_returns_metadata_in_response(
    mock_update, mock_metadata, mock_transcribe, mock_register, mock_auth
):
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.models import VideoMetadata
    from app.routers.video import video_router
    from app.auth import get_current_active_user

    user_id = "00000000-0000-0000-0000-000000000001"
    process_id = "00000000-0000-0000-0000-000000000002"
    mock_auth.return_value = MagicMock(id=user_id, username="test", email="t@t.com", is_active=True)
    mock_register.return_value = process_id
    mock_metadata.return_value = VideoMetadata(
        title="Instagram Reel",
        description="Short video about cooking.",
        duration=30.0,
        duration_string="0:30",
        platform="Instagram")
    mock_transcribe.return_value = "Today we cook pasta."

    test_app = FastAPI()
    test_app.include_router(video_router)
    test_app.dependency_overrides[get_current_active_user] = lambda: mock_auth.return_value
    client = TestClient(test_app)

    resp = client.post(
        "/video/transcribe",
        json={"url": "https://www.instagram.com/reel/abc", "lang": "en", "response_format": "text"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["metadata"] is not None
    assert data["metadata"]["title"] == "Instagram Reel"
    assert data["metadata"]["description"] == "Short video about cooking."
    assert data["metadata"]["platform"] == "Instagram"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_video.py::test_video_transcribe_returns_metadata_in_response -v`
Expected: FAIL

- [ ] **Step 3: Modify video transcribe endpoint to fetch and return metadata**

In `app/routers/video.py`, update `video_transcription()`:

```python
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

        video_metadata = None
        try:
            video_metadata = get_video_metadata(video_request.url)
        except Exception as metadata_error:
            logging.warning(
                f"Could not fetch video metadata for transcription: '{metadata_error}'")

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
            metadata_dict = video_metadata.model_dump(exclude={"subtitles"}) if video_metadata else None
            return ApiProcessingResult(
                result=True, error=None,
                transcription=transcription,
                format=video_request.response_format,
                metadata=metadata_dict)
    except Exception as e:
        logging.error(f"Error processing video transcription: {str(e)}")

        if process_id:
            process_failed(process_id, str(e))

        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiProcessingResult(
            result=False,
            error=f"Internal server error: {str(e)}",
        )
```

- [ ] **Step 4: Update existing transcribe test to patch metadata**

Update `test_video_transcribe_endpoint_success` in `tests/test_video.py` to add `get_video_metadata` patch:

```python
@patch('app.routers.video.get_current_active_user')
@patch('app.routers.video.register_new_process')
@patch('app.routers.video.video_transcribe')
@patch('app.routers.video.get_video_metadata')
@patch('app.routers.video.update_process_status')
def test_video_transcribe_endpoint_success(
    mock_update, mock_metadata, mock_transcribe, mock_register, mock_auth
):
    # ... same body but add:
    mock_metadata.return_value = None
    # rest stays the same
```

Also update `test_video_transcribe_endpoint_error` to add the `get_video_metadata` patch.

- [ ] **Step 5: Run all video tests**

Run: `uv run pytest tests/test_video.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add app/routers/video.py tests/test_video.py
git commit -m "feat: return video metadata in video transcribe response"
```

---

### Task 6: Run full test suite and verify

- [ ] **Step 1: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Start the app and verify no import errors**

Run: `uv run -m app`
Expected: FastAPI starts without errors

- [ ] **Step 3: Final commit if any cleanup needed**

```bash
git add -A
git commit -m "chore: cleanup after metadata-in-responses feature"
```
