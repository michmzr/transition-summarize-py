import httpx
import pytest

from main import app

BASE_URL = "http://127.0.0.1:8000/"
SHORT_YT_VIDEO = "https://www.youtube.com/watch?v=WuciqTSbewY"

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