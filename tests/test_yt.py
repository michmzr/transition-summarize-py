import unittest
from unittest.mock import MagicMock, patch

from app.youtube.metadata import get_youtube_metadata

class YTMetadata(unittest.TestCase):
    def test_get_video_metadata(self):
        video_url = 'https://www.youtube.com/watch?v=Rg35oYuus-w'
        metadata = get_youtube_metadata(video_url)

        print(metadata)

        self.assertIsNotNone(metadata.title)
        self.assertNotEqual(metadata.title, "")

        self.assertIsNotNone(metadata.full_title)
        self.assertNotEqual(metadata.full_title, "")

        self.assertIsNotNone(metadata.subtitles)

        self.assertIsNotNone(metadata.duration)
        self.assertGreater(metadata.duration, 0)

        self.assertIn('en', metadata.subtitles)
        self.assertNotEqual(metadata.subtitles['en'], {})

        self.assertIsNotNone(metadata.upload_date)
        self.assertIsNotNone(metadata.thumbnail)


def test_normalize_vtt_transcription_returns_timestamped_text():
    from app.youtube.transcriptions import normalize_vtt_transcription

    raw_vtt = """WEBVTT

00:00:00.000 --> 00:00:03.500
First sentence.

00:00:03.500 --> 00:00:07.200
Second sentence.
"""

    transcription = normalize_vtt_transcription(raw_vtt)

    assert transcription == "[00:00] First sentence.\n[00:03] Second sentence."


@patch('app.routers.youtube.get_current_active_user')
@patch('app.routers.youtube.register_new_process')
@patch('app.routers.youtube.download_transcription')
@patch('app.routers.youtube.get_youtube_metadata')
@patch('app.routers.youtube.register_process_artifact')
@patch('app.routers.youtube.summarize')
@patch('app.routers.youtube.complete_process')
def test_youtube_summarize_passes_metadata_and_transcription_to_model(
        mock_complete,
        mock_summarize,
        mock_artifact,
        mock_metadata,
        mock_download_transcription,
        mock_register,
        mock_auth):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.auth import get_current_active_user
    from app.models import YoutubeMetadata
    from app.routers.youtube import yt_router

    mock_auth.return_value = MagicMock(
        id="00000000-0000-0000-0000-000000000001",
        username="test",
        email="t@t.com",
        is_active=True)
    mock_register.return_value = "00000000-0000-0000-0000-000000000002"
    mock_metadata.return_value = YoutubeMetadata(
        title="Research Talk",
        description="A lecture about AI research.",
        duration=120.0,
        duration_string="2:00")
    mock_download_transcription.return_value = "[00:00] Intro to research."
    mock_summarize.return_value = "Summary text."

    test_app = FastAPI()
    test_app.include_router(yt_router)
    test_app.dependency_overrides[get_current_active_user] = lambda: mock_auth.return_value
    client = TestClient(test_app)

    response = client.post(
        "/youtube/summarize",
        json={
            "url": "https://www.youtube.com/watch?v=test",
            "type": "detailed",
            "lang": "en",
            "use_yt_transcription": True
        })

    assert response.status_code == 200
    text_sent_to_model = mock_summarize.call_args.args[0]
    assert "Title: Research Talk" in text_sent_to_model
    assert "Duration: 2:00" in text_sent_to_model
    assert "Description: A lecture about AI research." in text_sent_to_model
    assert "Transcript:\n[00:00] Intro to research." in text_sent_to_model


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
        username="test",
        email="t@t.com",
        is_active=True)
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
        json={
            "url": "https://www.youtube.com/watch?v=test",
            "lang": "en",
            "response_format": "text"
        })

    assert response.status_code == 200
    data = response.json()
    assert data["metadata"] is not None
    assert data["metadata"]["title"] == "My Video"
    assert data["metadata"]["description"] == "A great description."
    assert data["metadata"]["duration"] == 300.0


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
        username="test",
        email="t@t.com",
        is_active=True)
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
        json={
            "url": "https://www.youtube.com/watch?v=test",
            "type": "detailed",
            "lang": "en",
            "use_yt_transcription": True
        })

    assert response.status_code == 200
    data = response.json()
    assert data["metadata"] is not None
    assert data["metadata"]["title"] == "Talk Title"
    assert data["metadata"]["description"] == "Some description."
    assert data["metadata"]["duration"] == 600.0


if __name__ == '__main__':
    unittest.main()
