import logging

import static_ffmpeg
from fastapi import FastAPI, Depends
from openai import OpenAI

import app.database
from app import database  # Import database directly
from app.auth import get_current_active_user
from app.routers.audio import a_router
from app.routers.auth import auth_router
from app.routers.youtube import yt_router
from app.schema import models
from app.settings import Settings, get_settings

static_ffmpeg.add_paths()

settings = Settings()

app = FastAPI()

# Create a new router for protected routes
protected_app = FastAPI(dependencies=[Depends(get_current_active_user)])

# Include routers in the protected app
protected_app.include_router(a_router)
protected_app.include_router(yt_router)

# Include the protected app and auth router in the main app
app.mount("/api", protected_app)
app.include_router(auth_router, prefix="/auth")

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


@app.get("/health")
def health_check():
    return "OK"

@app.get("/url-list")
def get_all_urls():
    url_list = [{"path": route.path, "name": route.name} for route in app.routes]
    url_list += [{"path": f"/api{route.path}", "name": route.name} for route in protected_app.routes]
    return url_list
