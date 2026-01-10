"""API middleware for rate limiting and input sanitization"""
import re
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


# ==============================================================================
# Input Sanitization
# ==============================================================================

def sanitize_id(id_value: str, id_type: str = "ID") -> str:
    """
    Sanitize game/team/player IDs to prevent injection attacks.

    Args:
        id_value: The ID to sanitize
        id_type: Type of ID for error messages (e.g., "game_id", "team_id")

    Returns:
        Sanitized ID value

    Raises:
        HTTPException: If the ID contains invalid characters
    """
    if not re.match(r'^[a-zA-Z0-9_-]+$', id_value):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {id_type} format. Use only alphanumeric characters, dash, and underscore."
        )
    return id_value


# ==============================================================================
# Rate Limiting
# ==============================================================================

class RateLimiter:
    """
    Simple in-memory rate limiter to prevent abuse.

    Tracks calls per key within a time window and blocks excessive requests.
    """
    def __init__(self, max_calls: int, window: timedelta):
        self.max_calls = max_calls
        self.window = window
        self.calls = defaultdict(list)

    def check(self, key: str) -> None:
        """
        Check if a request should be allowed.

        Args:
            key: Unique key to rate limit on (e.g., "execute_action:game123:player1")

        Raises:
            HTTPException: If rate limit is exceeded
        """
        now = datetime.now()

        # Clean old calls outside the window
        self.calls[key] = [
            call_time for call_time in self.calls[key]
            if now - call_time < self.window
        ]

        if len(self.calls[key]) >= self.max_calls:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {self.max_calls} calls per {self.window.total_seconds()}s. Please wait."
            )

        self.calls[key].append(now)

    async def __call__(self, request: Request, call_next):
        """
        Middleware to apply rate limiting to requests.

        Uses path and client IP as rate limit key.
        """
        # Extract client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Create rate limit key
        key = f"{client_ip}:{request.url.path}"
        
        try:
            self.check(key)
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )
        
        # Process request
        response = await call_next(request)
        return response


# Global rate limiter: 100 calls per minute per endpoint per IP
rate_limiter = RateLimiter(max_calls=100, window=timedelta(minutes=1))
