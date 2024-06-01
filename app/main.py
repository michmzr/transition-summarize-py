import logging
from functools import lru_cache

from fastapi import FastAPI
from openai import OpenAI

from routers import audio, youtube
import static_ffmpeg
from fastapi import FastAPI
from routers import audio, youtube
import static_ffmpeg
from pydantic_settings import BaseSettings, SettingsConfigDict

static_ffmpeg.add_paths()


class Settings(BaseSettings):
    logging_level: int = logging.DEBUG
    openai_api_key: str
    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings():
    return Settings()


settings = Settings()

app = FastAPI()
app.include_router(audio.router)
app.include_router(youtube.router)

logging.basicConfig(
    level=get_settings().logging_level,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)

client = OpenAI(api_key=settings.openai_api_key)


@app.get("/url-list")
def get_all_urls():
    url_list = [{"path": route.path, "name": route.name} for route in app.routes]
    return url_list
