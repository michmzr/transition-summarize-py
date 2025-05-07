import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.settings import get_settings

settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.requests = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.enable_rate_limiting:
            return await call_next(request)

        client_ip = request.client.host
        current_time = time.time()

        # Clean up old requests
        self.requests = {
            ip: timestamps for ip, timestamps in self.requests.items()
            if current_time - timestamps[-1] < settings.rate_limit_period
        }

        # Check rate limit
        if client_ip in self.requests:
            timestamps = self.requests[client_ip]
            if len(timestamps) >= settings.rate_limit_requests:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"}
                )
            timestamps.append(current_time)
        else:
            self.requests[client_ip] = [current_time]

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        if settings.enable_security_headers:
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = "default-src 'self'"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        return response
