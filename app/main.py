import logging

import static_ffmpeg
from fastapi import FastAPI
from openai import OpenAI

import database
from app.settings import Settings, get_settings
from routers.audio import a_router
from routers.auth import auth_router
from routers.youtube import yt_router
from schema import models

static_ffmpeg.add_paths()

settings = Settings()

app = FastAPI()
app.include_router(a_router)
app.include_router(yt_router)
app.include_router(auth_router)


logging.basicConfig(
    level=get_settings().logging_level,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)

# Create tables
models.Base.metadata.create_all(bind=database.engine)


client = OpenAI(api_key=settings.openai_api_key)

@app.get("/url-list")
def get_all_urls():
    url_list = [{"path": route.path, "name": route.name} for route in app.routes]
    return url_list


@app.get("/health")
def get_all_urls():
    return "OK"
