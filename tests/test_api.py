import os
import shutil

import httpx
import pytest
from fastapi.testclient import TestClient

from app import database
from app.auth import get_password_hash
from app.main import app
from app.schema.models import UserDB

BASE_URL = "http://127.0.0.1:8000/"
SHORT_YT_VIDEO = "https://www.youtube.com/watch?v=WuciqTSbewY"

client = TestClient(app)


@pytest.fixture
def test_db():
    # Create test user
    db = database.SessionLocal()
    hashed_password = get_password_hash("testpass123")
    test_user = UserDB(
        username="testuser",
        email="test@example.com",
        hashed_password=hashed_password,
        is_active=True
    )
    db.add(test_user)
    db.commit()

    yield db

    # Cleanup
    db.query(UserDB).filter(UserDB.username == "testuser").delete()
    db.commit()
    db.close()


@pytest.fixture
async def auth_token(test_db):
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as ac:
        response = await ac.post(
            "/auth/token",
            data={"username": "testuser", "password": "testpass123"}
        )
        token = response.json()["access_token"]
        return token


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}

@pytest.fixture
def audio_file():
    with open('tests/resources/audio_short.mp3', 'rb') as f:
        yield f

@pytest.mark.unit
@pytest.mark.integration_no_yt
async def test_audio_transcribe_valid_file(audio_file, auth_headers):
    response = client.post(
        "/api/audio/transcribe",
        files={"uploaded_file": audio_file},
        data={"lang": "pl"},
        headers=auth_headers
    )
    
    json = response.json()
    assert response.status_code == 200
    assert json["result"]
    assert "transcription" in json
    assert "format" in json

@pytest.mark.unit
@pytest.mark.integration_no_yt
async def test_audio_transcribe_invalid_file(auth_headers):
    with open('tests/resources/test_file.txt', 'rb') as f:
        response = client.post(
            "/api/audio/transcribe",
            files={"uploaded_file": f},
            data={"lang": "pl"},
            headers=auth_headers
        )
        
        json = response.json()
        assert response.status_code == 400
        assert "error" in json
        assert json["result"] == False
        assert "Invalid file type. Only audio files are accepted" in json["error"]

@pytest.mark.asyncio
@pytest.mark.integration_no_yt
async def test_given_audio_file_expect_non_empty_summary(auth_token):
    token = await auth_token
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as ac:
        with open('tests/resources/audio_short.mp3', 'rb') as f:
            response = await ac.post(
                "/api/audio/summary",
                files={"uploaded_file": f},
                data={"type": "tldr", "lang": "pl"},
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 200
            assert "summary" in response.json()
            assert "Fallout 4" in response.json()["summary"]

@pytest.mark.asyncio
async def test_given_url_expect_non_empty_transcription(auth_token):
    token = await auth_token
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as ac:
        response = await ac.post(
            "/api/youtube/transcribe",
            json={"url": SHORT_YT_VIDEO, "lang": "en"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert "transcription" in response.json()
        result = response.json()["transcription"]
        assert "liberal" in result
        assert "chains" in result

@pytest.mark.asyncio
async def test_given_url_expect_non_empty_summary(auth_token):
    async with httpx.AsyncClient(app=app, base_url=BASE_URL) as ac:
        response = await ac.post(
            "/api/youtube/summarize",
            json={"url": SHORT_YT_VIDEO, "type": "tldr", "lang": "pl"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        assert "summary" in response.json()
        assert response.json()["summary"] != ""

def teardown_module(module):
    """
    This method is called once for each module after all tests in it are run.
    We are using it to clean up the downloads directory after tests are run.
    """
    downloads_dir = 'tests/downloads'
    if os.path.exists(downloads_dir):
        shutil.rmtree(downloads_dir)
