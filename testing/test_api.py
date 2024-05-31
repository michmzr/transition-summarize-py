import os
import shutil
import httpx
import pytest
from fastapi.testclient import TestClient
from main import app
from summary.utils import SUMMARIZATION_TYPE

BASE_URL = "http://127.0.0.1:8000/"
SHORT_YT_VIDEO = "https://www.youtube.com/watch?v=WuciqTSbewY"

client = TestClient(app)

def test_audio_transcribe_valid_file():
    with open('resources/audio_short.mp3', 'rb') as f:
        response = client.post("/audio/transcribe", files={"uploaded_file": f})
    assert response.status_code == 200
    assert "result" in response.json()

def test_audio_transcribe_invalid_file():
    with open('resources/test_file.txt', 'rb') as f:
        response = client.post("/audio/transcribe", files={"uploaded_file": f})
    assert response.status_code == 400
    assert "error" in response.json()


def test_audio_summary():
    with open('resources/audio_short.mp3', 'rb') as f:
        response = client.post("/audio/summary",
                               files={"uploaded_file": f},
                               data={"type": SUMMARIZATION_TYPE.TLDR, "language": "pl"})
    assert response.status_code == 200
    assert "result" in response.json()

@pytest.mark.asyncio
async def test_youtube_transcribe():
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as ac:
        response = await ac.post("/youtube/transcribe", json={"url": SHORT_YT_VIDEO})
    assert response.status_code == 200
    assert "result" in response.json()
    assert response.json()["result"] != ""

@pytest.mark.asyncio
async def test_youtube_summarize():
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as ac:
        response = await ac.post("/youtube/summarize",
                                 json={"url":  SHORT_YT_VIDEO, "type": "TLDR"})
    assert response.status_code == 200
    assert "result" in response.json()
    assert response.json()["result"] != ""


def teardown_module(module):
    """
    This method is called once for each module after all tests in it are run.
    We are using it to clean up the downloads directory after tests are run.
    """
    downloads_dir = './downloads'
    if os.path.exists(downloads_dir):
        shutil.rmtree(downloads_dir)