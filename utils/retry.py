"""
Retry Utilities for Portin

Tenacity-based retry decorators for API calls.
Handles:
- Rate limits (429 errors)
- Timeouts
- Transient failures
"""

from functools import wraps
from typing import Callable, Type, Tuple, Any
import time

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryError
)

import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# RETRY DECORATORS
# ─────────────────────────────────────────────────────────────

def retry_api_call(
    max_attempts: int = 3,
    min_wait: float = 1,
    max_wait: float = 30,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator for retrying API calls with exponential backoff.
    
    Usage:
        @retry_api_call(max_attempts=3)
        def call_gemini(prompt):
            ...
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )


def retry_with_jitter(
    max_attempts: int = 3,
    min_wait: float = 1,
    max_wait: float = 60
):
    """
    Retry with random exponential backoff (jitter).
    Better for avoiding thundering herd on rate limits.
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_random_exponential(multiplier=1, min=min_wait, max=max_wait),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )


# ─────────────────────────────────────────────────────────────
# RATE LIMIT HELPERS
# ─────────────────────────────────────────────────────────────

class RateLimiter:
    """
    Simple rate limiter for API calls.
    
    Usage:
        limiter = RateLimiter(calls_per_minute=10)
        limiter.wait()  # Call before each API request
        response = api.call()
    """
    
    def __init__(self, calls_per_minute: int = 10):
        self.min_interval = 60.0 / calls_per_minute
        self.last_call = 0.0
    
    def wait(self):
        """Wait if needed to respect rate limit."""
        now = time.time()
        elapsed = now - self.last_call
        
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            time.sleep(sleep_time)
        
        self.last_call = time.time()


# Pre-configured limiters for common APIs
GEMINI_LIMITER = RateLimiter(calls_per_minute=10)  # ~6 sec between calls
SERPER_LIMITER = RateLimiter(calls_per_minute=30)  # ~2 sec between calls
FIRECRAWL_LIMITER = RateLimiter(calls_per_minute=20)  # ~3 sec between calls


# ─────────────────────────────────────────────────────────────
# FALLBACK DECORATOR
# ─────────────────────────────────────────────────────────────

def with_fallback(fallback_func: Callable, log_error: bool = True):
    """
    Decorator that calls a fallback function on failure.
    
    Usage:
        @with_fallback(fallback_search)
        def primary_search(query):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    logger.warning(f"{func.__name__} failed: {e}, trying fallback")
                return fallback_func(*args, **kwargs)
        return wrapper
    return decorator
