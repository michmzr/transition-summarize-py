import uuid
import logging
from contextvars import ContextVar
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable to store the request ID
request_id_context: ContextVar[Optional[str] ] = ContextVar("request_id", default=None)

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate a new request ID
        request_id = str(uuid.uuid4())

        # Store the request ID in the context
        token = request_id_context.set(request_id)

        # Add request ID to response headers
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        # Reset the context
        request_id_context.reset(token)

        return response


def get_request_id() -> Optional[str]:
    """Get the current request ID from the context."""
    return request_id_context.get()


class RequestIDFilter(logging.Filter):
    """Filter that adds request ID to log records."""

    def filter(self, record):
        request_id = get_request_id()
        record.request_id = request_id if request_id else "no-request-id"
        return True
