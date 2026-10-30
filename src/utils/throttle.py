"""In-process throttling / quota controls for the researcher-facing /api/v1 API.

RESEARCH USE ONLY — these controls only shape *how much work* a research facility can
push through the programmatic API. They make no clinical claim and never alter the
research-hypothesis framing of any output.

What this module provides
-------------------------
* ``effective_limits(record)`` — resolve a key's effective limits by merging its optional
  per-key overrides (stored on the key record) over the global defaults in
  ``config/settings.py``.
* ``Throttler`` — a thread-safe, **per-process** enforcer for:
    - a per-key **sliding-window request rate** (requests/minute and requests/day), and
    - a per-key **max concurrent in-flight analyses** counter.

Scaling note (IMPORTANT)
------------------------
The counters live in this process's memory (see ``_STATES`` on the module-level
``throttler`` singleton). With the current single-uvicorn-worker deployment that is the
entire application, so the limits are global. If the app is ever scaled to multiple
workers or hosts, each worker would keep its own counts and the effective limit would
multiply by the worker count. To make the limits truly global in that setup, replace the
in-memory ``_KeyState`` bookkeeping with a shared store (e.g. Redis: an INCR with EXPIRE
for the windows, and an INCR/DECR for in-flight). The public method surface
(``check_rate``/``acquire``/``release``) is intentionally small so that swap is local to
this file.
"""
from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from config import settings

# Window lengths in seconds.
_MINUTE = 60.0
_DAY = 86_400.0

# Limit field names shared across the key store, CLI, and API responses.
LIMIT_FIELDS = (
    "max_variants_per_request",
    "requests_per_minute",
    "requests_per_day",
    "max_concurrent",
)


def _global_defaults() -> dict[str, int]:
    """Current global default limits (read live so tests can monkeypatch settings)."""
    return {
        "max_variants_per_request": int(settings.API_MAX_VARIANTS_PER_REQUEST),
        "requests_per_minute": int(settings.API_REQUESTS_PER_MINUTE),
        "requests_per_day": int(settings.API_REQUESTS_PER_DAY),
        "max_concurrent": int(settings.API_MAX_CONCURRENT_ANALYSES),
    }


def effective_limits(record: dict[str, Any] | None) -> dict[str, int]:
    """Merge a key record's per-key overrides over the global defaults.

    A field is overridden only when the record carries a positive integer for it; any
    missing / ``None`` / non-positive value falls back to the global default. Returns a
    plain dict with exactly the keys in ``LIMIT_FIELDS``.
    """
    limits = _global_defaults()
    if record:
        overrides = record.get("limits") if isinstance(record.get("limits"), dict) else record
        for name in LIMIT_FIELDS:
            val = overrides.get(name)
            if isinstance(val, bool):  # guard: bool is an int subclass
                continue
            if isinstance(val, int) and val > 0:
                limits[name] = val
    return limits


@dataclass
class _KeyState:
    minute_hits: deque[float] = field(default_factory=deque)
    day_hits: deque[float] = field(default_factory=deque)
    in_flight: int = 0


@dataclass
class RateDecision:
    allowed: bool
    retry_after: int           # seconds until the binding window frees (0 when allowed)
    remaining_minute: int
    remaining_day: int
    limit_minute: int
    limit_day: int


class Throttler:
    """Thread-safe per-key sliding-window rate limiter + in-flight concurrency gate."""

    def __init__(self) -> None:
        self._states: dict[str, _KeyState] = {}
        self._lock = threading.Lock()

    def _state(self, key_id: str) -> _KeyState:
        st = self._states.get(key_id)
        if st is None:
            st = _KeyState()
            self._states[key_id] = st
        return st

    @staticmethod
    def _purge(hits: deque[float], now: float, window: float) -> None:
        cutoff = now - window
        while hits and hits[0] <= cutoff:
            hits.popleft()

    def check_rate(self, key_id: str, rpm: int, rpd: int,
                   now: float | None = None) -> RateDecision:
        """Check the per-minute and per-day windows for ``key_id``.

        Records a hit (in both windows) only when the request is ALLOWED. When rejected,
        no hit is recorded and ``retry_after`` is the whole seconds until the binding
        window has room again.
        """
        now = time.monotonic() if now is None else now
        with self._lock:
            st = self._state(key_id)
            self._purge(st.minute_hits, now, _MINUTE)
            self._purge(st.day_hits, now, _DAY)

            retry_after = 0
            over_minute = len(st.minute_hits) >= rpm
            over_day = len(st.day_hits) >= rpd
            if over_minute:
                retry_after = max(retry_after,
                                  math.ceil(st.minute_hits[0] + _MINUTE - now))
            if over_day:
                retry_after = max(retry_after,
                                  math.ceil(st.day_hits[0] + _DAY - now))

            if over_minute or over_day:
                return RateDecision(
                    allowed=False, retry_after=max(retry_after, 1),
                    remaining_minute=max(0, rpm - len(st.minute_hits)),
                    remaining_day=max(0, rpd - len(st.day_hits)),
                    limit_minute=rpm, limit_day=rpd)

            st.minute_hits.append(now)
            st.day_hits.append(now)
            return RateDecision(
                allowed=True, retry_after=0,
                remaining_minute=max(0, rpm - len(st.minute_hits)),
                remaining_day=max(0, rpd - len(st.day_hits)),
                limit_minute=rpm, limit_day=rpd)

    def acquire(self, key_id: str, max_concurrent: int) -> bool:
        """Try to reserve an in-flight slot. Returns True on success (slot taken)."""
        with self._lock:
            st = self._state(key_id)
            if st.in_flight >= max_concurrent:
                return False
            st.in_flight += 1
            return True

    def release(self, key_id: str) -> None:
        """Release a previously acquired in-flight slot (never drops below zero)."""
        with self._lock:
            st = self._state(key_id)
            if st.in_flight > 0:
                st.in_flight -= 1

    def in_flight(self, key_id: str) -> int:
        with self._lock:
            return self._state(key_id).in_flight

    def reset(self) -> None:
        """Clear all state (used by tests)."""
        with self._lock:
            self._states.clear()


# Module-level singleton used by the app. (Replace internals with a shared store to
# scale across workers — see the module docstring.)
throttler = Throttler()
