import logging
from functools import lru_cache

import static_ffmpeg
from fastapi import FastAPI
from openai import OpenAI
from pydantic_settings import BaseSettings, SettingsConfigDict

from routers.audio import a_router
from routers.youtube import yt_router

static_ffmpeg.add_paths()

class Settings(BaseSettings):
    logging_level: int = logging.DEBUG
    openai_api_key: str
    # list of proxy servers, comma separated
    proxy_servers: str = None
    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings():
    return Settings()


settings = Settings()

app = FastAPI()
app.include_router(a_router)
app.include_router(yt_router)

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


@app.get("/health")
def get_all_urls():
    return "OK"
