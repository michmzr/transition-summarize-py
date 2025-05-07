import logging

import static_ffmpeg
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

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
from app.middleware.security import RateLimitMiddleware, SecurityHeadersMiddleware
from app.scheduler import init_scheduler, add_cron_job
from app.tasks.cleanup import cleanup_downloads
from app.schema.pydantic_models import User

static_ffmpeg.add_paths()

settings = Settings()

app = FastAPI(
    title="Transition Summarize API",
    description="API for summarizing transitions",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    # Configure for long-running requests
    timeout=600,  # 10 minutes timeout
    keep_alive_timeout=600,  # 10 minutes keep-alive
)

# Security middleware
if settings.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security_config["allowed_origins"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=3600,
    )

# Trusted hosts middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.security_config["allowed_hosts"]
)

# Session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=3600,  # 1 hour
    same_site="lax",
    https_only=settings.is_production
)

# Add security middlewares
if settings.security_config["enable_rate_limiting"]:
    app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

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
    "[%(asctime)s UTC] [%(levelname)s] [%(request_id)s] %(message)s"
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
