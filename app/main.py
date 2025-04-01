import logging

import static_ffmpeg
from fastapi import FastAPI, Depends

import app.database
from app import database  # Import database directly
from app.auth import get_current_active_user
from app.routers.audio import a_router
from app.routers.auth import auth_router
from app.routers.youtube import yt_router
from app.routers.artifacts import router as artifacts_router
from app.schema import models
from app.settings import Settings, get_settings
from app.database import init_db
from app.middleware.request_id import RequestIDMiddleware, RequestIDFilter
from app.scheduler import init_scheduler, add_cron_job
from app.tasks.cleanup import cleanup_downloads
from app.schema.pydantic_models import User

static_ffmpeg.add_paths()

settings = Settings()

app = FastAPI()

# Initialize scheduler
init_scheduler(app)

# Register cleanup job
settings = get_settings()
if settings.cleanup_downloads_enabled:
    add_cron_job(
        cleanup_downloads,
        settings.cleanup_downloads_time,
        id="cleanup_downloads"
    )

# Add request ID middleware
app.add_middleware(RequestIDMiddleware)

# Create a new router for protected routes
protected_app = FastAPI(dependencies=[Depends(get_current_active_user)])

# Include routers in the protected app
protected_app.include_router(a_router)
protected_app.include_router(yt_router)
protected_app.include_router(artifacts_router)
protected_app.include_router(artifacts_router)

# Include the protected app and auth router in the main app
app.mount("/api", protected_app)
app.include_router(auth_router)
app.include_router(yt_router)
app.include_router(a_router)
app.include_router(artifacts_router)

# Configure logging with request ID
logger = logging.getLogger()
logger.setLevel(get_settings().logging_level)

# Create formatters and handlers with simplified format
formatter = logging.Formatter(
    "[%(levelname)s] [%(request_id)s] %(message)s"
)

file_handler = logging.FileHandler("debug.log")
file_handler.setFormatter(formatter)
file_handler.addFilter(RequestIDFilter())

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.addFilter(RequestIDFilter())

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Initialize database (only in non-test environment)
init_db()

# Health api
@app.get("/health")
def health_check():
    return "OK"

@app.get("/url-list")
def get_all_urls(current_user: User = Depends(get_current_active_user)):
    url_list = [{"path": route.path, "name": route.name} for route in app.routes]
    url_list += [{"path": f"/api{route.path}", "name": route.name} for route in protected_app.routes]
    return url_list
