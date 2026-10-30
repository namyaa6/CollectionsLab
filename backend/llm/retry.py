"""Rate limiting and retry helpers for the LLM client."""
import random
import re
import time
from collections import deque
from typing import Callable, Optional

import httpx
from google.genai import errors

RETRYABLE_CODES = {429, 500, 503, 504}
MAX_DELAY_S = 60.0


class RateLimiter:
    """Sliding-window limiter: at most `rpm` calls in any 60 second window."""

    def __init__(self, rpm: int, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.rpm, self._clock, self._sleep = rpm, clock, sleep
        self._stamps: deque[float] = deque()

    def wait(self) -> None:
        now = self._clock()
        while self._stamps and now - self._stamps[0] >= 60:
            self._stamps.popleft()
        if len(self._stamps) >= self.rpm:
            self._sleep(60 - (now - self._stamps[0]))
            now = self._clock()
            while self._stamps and now - self._stamps[0] >= 60:
                self._stamps.popleft()
        self._stamps.append(now)


def _details(exc: errors.APIError) -> list[dict]:
    body = exc.details if isinstance(exc.details, dict) else {}
    found = body.get("error", body).get("details", [])
    return [d for d in found if isinstance(d, dict)]


def is_retryable(exc: Exception) -> bool:
    if isinstance(exc, errors.APIError):
        return exc.code in RETRYABLE_CODES
    return isinstance(exc, (httpx.TransportError, TimeoutError))  # timeouts are subclasses


def is_daily_quota(exc: Exception) -> bool:
    """True for a 429 saying the per-day quota is gone (waiting a minute won't help)."""
    if not isinstance(exc, errors.APIError) or exc.code != 429:
        return False
    for detail in _details(exc):
        for violation in detail.get("violations", []):
            if "perday" in str(violation.get("quotaId", "")).replace("_", "").lower():
                return True
    return bool(re.search(r"per day|daily", str(exc.message or ""), re.IGNORECASE))


def server_retry_delay(exc: Exception) -> Optional[float]:
    """Delay the API asked for (RetryInfo '7s' or 'retry in 7.5s'), else None."""
    if not isinstance(exc, errors.APIError):
        return None
    for detail in _details(exc):
        match = re.fullmatch(r"([\d.]+)s", str(detail.get("retryDelay", "")))
        if match:
            return float(match.group(1))
    match = re.search(r"retry in ([\d.]+)s", str(exc.message or ""), re.IGNORECASE)
    return float(match.group(1)) if match else None


def backoff_delay(attempt: int, exc: Exception, base: float = 2.0) -> float:
    """Server-provided delay if any, else exponential (2, 4, 8, ...) plus jitter; capped."""
    asked = server_retry_delay(exc)
    delay = asked if asked is not None else base * 2 ** attempt + random.uniform(0, 1)
    return min(delay, MAX_DELAY_S)
