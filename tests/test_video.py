import importlib
from unittest.mock import patch, MagicMock

from app.schema.models import RequestType


def test_video_request_type_exists():
    assert RequestType.VIDEO.value == "video"


def test_register_new_process_video_type():
    from app.processing.processing import register_new_process
    from app.schema.models import RequestType, UserProcessSourceType

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


def test_video_audio_loader_init():
    from app.video.loader import VideoAudioLoader
    loader = VideoAudioLoader(["https://vimeo.com/123456"], "/tmp/test_save")
    assert loader.urls == ["https://vimeo.com/123456"]
    assert loader.save_dir == "/tmp/test_save"
    assert loader.proxy_servers is None


def test_video_audio_loader_init_with_proxy():
    from app.video.loader import VideoAudioLoader
    loader = VideoAudioLoader(
        ["https://vimeo.com/123456"],
        "/tmp/test_save",
        proxy_servers=["http://proxy1:8080"]
    )
    assert loader.proxy_servers == ["http://proxy1:8080"]


def test_video_audio_loader_urls_must_be_list():
    from app.video.loader import VideoAudioLoader
    try:
        VideoAudioLoader("https://vimeo.com/123456", "/tmp/test_save")
        assert False, "Should have raised TypeError"
    except TypeError:
        pass


def test_video_metadata_model():
    from app.models import VideoMetadata
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


def test_video_transcribe_model_defaults():
    from app.models import VideoTranscribe
    from app.transcribe.transcription import LANG_CODE, WHISPER_RESPONSE_FORMAT
    req = VideoTranscribe(url="https://vimeo.com/123456")
    assert req.url == "https://vimeo.com/123456"
    assert req.lang == LANG_CODE.POLISH
    assert req.response_format == WHISPER_RESPONSE_FORMAT.SRT


def test_video_summarize_model_defaults():
    from app.models import VideoSummarize, SUMMARIZATION_TYPE
    from app.transcribe.transcription import LANG_CODE
    req = VideoSummarize(url="https://vimeo.com/123456")
    assert req.url == "https://vimeo.com/123456"
    assert req.type == SUMMARIZATION_TYPE.TLDR
    assert req.lang == LANG_CODE.POLISH


def test_video_info_request_model():
    from app.models import VideoInfoRequest
    req = VideoInfoRequest(url="https://www.instagram.com/reel/abc123")
    assert req.url == "https://www.instagram.com/reel/abc123"


@patch('app.video.transcription.GenericLoader')
@patch('app.video.transcription.get_settings')
def test_video_transcribe_returns_text(mock_settings, mock_generic_loader):
    from app.video.transcription import video_transcribe
    from app.transcribe.transcription import LANG_CODE, WHISPER_RESPONSE_FORMAT

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


def test_video_router_module_loads():
    mod = importlib.import_module("app.routers.video")
    assert hasattr(mod, "video_router")


def test_video_router_has_transcribe_endpoint():
    mod = importlib.import_module("app.routers.video")
    router = mod.video_router
    paths = [route.path for route in router.routes]
    assert "/video/transcribe" in paths


def test_video_router_has_summarize_endpoint():
    mod = importlib.import_module("app.routers.video")
    router = mod.video_router
    paths = [route.path for route in router.routes]
    assert "/video/summarize" in paths


def test_video_router_has_details_endpoint():
    mod = importlib.import_module("app.routers.video")
    router = mod.video_router
    paths = [route.path for route in router.routes]
    assert "/video/details" in paths


def test_video_router_prefix():
    from app.routers.video import video_router
    assert video_router.prefix == "/video"
    assert "video" in video_router.tags


@patch('app.routers.video.get_current_active_user')
@patch('app.routers.video.register_new_process')
@patch('app.routers.video.video_transcribe')
@patch('app.routers.video.update_process_status')
def test_video_transcribe_endpoint_success(
    mock_update, mock_transcribe, mock_register, mock_auth
):
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.routers.video import video_router
    from app.auth import get_current_active_user

    user_id = "00000000-0000-0000-0000-000000000001"
    process_id = "00000000-0000-0000-0000-000000000002"
    mock_auth.return_value = MagicMock(id=user_id, username="test", email="t@t.com", is_active=True)
    mock_register.return_value = process_id
    mock_transcribe.return_value = "Transcribed text from Vimeo video."

    test_app = FastAPI()
    test_app.include_router(video_router)
    test_app.dependency_overrides[get_current_active_user] = lambda: mock_auth.return_value
    client = TestClient(test_app)

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
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.routers.video import video_router
    from app.auth import get_current_active_user

    user_id = "00000000-0000-0000-0000-000000000001"
    process_id = "00000000-0000-0000-0000-000000000002"
    mock_auth.return_value = MagicMock(id=user_id, username="test", email="t@t.com", is_active=True)
    mock_register.return_value = process_id
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


@patch('app.routers.video.get_current_active_user')
@patch('app.routers.video.register_new_process')
@patch('app.routers.video.video_transcribe')
@patch('app.routers.video.register_process_artifact')
@patch('app.routers.video.process_failed')
@patch('app.routers.video.summarize')
@patch('app.routers.video.complete_process')
def test_video_summarize_endpoint_rejects_empty_transcription(
    mock_complete, mock_summarize, mock_process_failed,
    mock_artifact, mock_transcribe, mock_register, mock_auth
):
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.routers.video import video_router
    from app.auth import get_current_active_user

    user_id = "00000000-0000-0000-0000-000000000001"
    process_id = "00000000-0000-0000-0000-000000000002"
    mock_auth.return_value = MagicMock(id=user_id, username="test", email="t@t.com", is_active=True)
    mock_register.return_value = process_id
    mock_transcribe.return_value = ""
    mock_summarize.return_value = ""

    test_app = FastAPI()
    test_app.include_router(video_router)
    test_app.dependency_overrides[get_current_active_user] = lambda: mock_auth.return_value
    client = TestClient(test_app)

    resp = client.post(
        "/video/summarize",
        json={"url": "https://www.instagram.com/p/test", "type": "tldr", "lang": "pl"},
    )

    assert resp.status_code == 500
    data = resp.json()
    assert data["error"] == "Error processing video summarization"
    assert "No transcription generated" in data["text"]
    mock_summarize.assert_not_called()
    mock_complete.assert_not_called()
    mock_process_failed.assert_called_once()


@patch('app.routers.video.get_current_active_user')
@patch('app.routers.video.get_video_metadata')
def test_video_details_endpoint_success(mock_metadata, mock_auth):
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.models import VideoMetadata
    from app.routers.video import video_router
    from app.auth import get_current_active_user

    user_id = "00000000-0000-0000-0000-000000000001"
    mock_auth.return_value = MagicMock(id=user_id, username="test", email="t@t.com", is_active=True)
    mock_metadata.return_value = VideoMetadata(
        title="Vimeo Video",
        description="A cool video",
        duration=60.0,
        duration_string="1:00",
        platform="Vimeo",
        original_url="https://vimeo.com/123456",
    )

    test_app = FastAPI()
    test_app.include_router(video_router)
    test_app.dependency_overrides[get_current_active_user] = lambda: mock_auth.return_value
    client = TestClient(test_app)

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
@patch('app.routers.video.process_failed')
def test_video_transcribe_endpoint_error(mock_process_failed, mock_transcribe, mock_register, mock_auth):
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.routers.video import video_router
    from app.auth import get_current_active_user

    user_id = "00000000-0000-0000-0000-000000000001"
    process_id = "00000000-0000-0000-0000-000000000002"
    mock_auth.return_value = MagicMock(id=user_id, username="test", email="t@t.com", is_active=True)
    mock_register.return_value = process_id
    mock_transcribe.side_effect = Exception("yt-dlp download failed")

    test_app = FastAPI()
    test_app.include_router(video_router)
    test_app.dependency_overrides[get_current_active_user] = lambda: mock_auth.return_value
    client = TestClient(test_app)

    resp = client.post(
        "/video/transcribe",
        json={"url": "https://invalid-site.com/video", "lang": "en", "response_format": "text"},
    )
    assert resp.status_code == 500
    data = resp.json()
    assert data["result"] is False
    assert "yt-dlp download failed" in data["error"]
