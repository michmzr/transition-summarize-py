import os
import shutil

import httpx
import pytest
from fastapi.testclient import TestClient

from main import app

BASE_URL = "http://127.0.0.1:8000/"
SHORT_YT_VIDEO = "https://www.youtube.com/watch?v=WuciqTSbewY"

client = TestClient(app)


# Given
@pytest.fixture
def audio_file():
    with open('tests/resources/audio_short.mp3', 'rb') as f:
        yield f


@pytest.mark.unit
@pytest.mark.integration_no_yt
def test_audio_transcribe_valid_file(audio_file):
    # When
    response = client.post(
        "/audio/transcribe",
        files={"uploaded_file": audio_file},
        data={"lang": "pl"})
    # Then
    assert "result" in response.json()
    assert response.status_code == 200


@pytest.mark.unit
@pytest.mark.integration_no_yt
def test_audio_transcribe_invalid_file():
    # Given
    with open('tests/resources/test_file.txt', 'rb') as f:
        invalid_file = f

        # When
        response = client.post("/audio/transcribe",
                               files={"uploaded_file": invalid_file},
                               data={"lang": "pl"})
        # Then
        assert response.status_code == 400

        assert "error" in response.json()

        error = response.json()["error"]
        assert "Only audio files are accepted" in error


@pytest.mark.asyncio
@pytest.mark.integration_no_yt
async def test_given_audio_file_expect_non_empty_summary():
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as ac:
        with open('tests/resources/audio_short.mp3', 'rb') as f:
            response = await ac.post("/audio/summary",
                                     files={"uploaded_file": f},
                                     data={"type": "tldr", "lang": "pl"})

            assert response.status_code == 200
            assert "result" in response.json()
            assert "Fallout 4" in response.json()["result"]

@pytest.mark.asyncio
async def test_given_url_expect_non_empty_transcription():
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as ac:
        response = await ac.post("/youtube/transcribe", json={"url": SHORT_YT_VIDEO})

        assert response.status_code == 200
        assert "result" in response.json()

        result = response.json()["result"][0]
        assert "liberal" in result
        assert "chains" in result

@pytest.mark.asyncio
async def test_given_url_expect_non_empty_summary():
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as ac:
        response = await ac.post("/youtube/summarize",
                                 json={"url": SHORT_YT_VIDEO, "type": "tldr", "lang": "pl"})
        assert response.status_code == 200
        assert "result" in response.json()
        assert response.json()["result"] != ""


def teardown_module(module):
    """
    This method is called once for each module after all tests in it are run.
    We are using it to clean up the downloads directory after tests are run.
    """
    downloads_dir = 'tests/downloads'
    if os.path.exists(downloads_dir):
        shutil.rmtree(downloads_dir)