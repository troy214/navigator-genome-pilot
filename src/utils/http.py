"""Polite HTTP helper for free public bio-data APIs.

- bounded timeouts + retries with backoff
- a light per-host rate limit (respects the shared-IP network rules: no hammering)
- disk caching via src.utils.cache
- NEVER raises to the caller for a network failure: returns None so agents degrade
  gracefully and record the source as unavailable (the "say when it doesn't know" rule)
"""
from __future__ import annotations
import threading
import time
from typing import Any

import requests

from config import settings
from src.utils import cache

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": f"{settings.API_TOOL_NAME} ({settings.API_CONTACT_EMAIL})"})

_last_call: dict[str, float] = {}
_lock = threading.Lock()
_MIN_INTERVAL_S = 0.34  # ~3 req/s per host, conservative for NCBI etiquette


def _rate_limit(host: str) -> None:
    with _lock:
        now = time.time()
        wait = _MIN_INTERVAL_S - (now - _last_call.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.time()


def _request(method: str, url: str, *, namespace: str, cache_key: Any,
             want: str = "json", **kwargs) -> Any | None:
    cached = cache.get(namespace, cache_key)
    if cached is not None:
        return cached

    from urllib.parse import urlparse
    host = urlparse(url).netloc

    last_exc = None
    for attempt in range(settings.HTTP_MAX_RETRIES + 1):
        try:
            _rate_limit(host)
            resp = _SESSION.request(method, url, timeout=settings.HTTP_TIMEOUT_S, **kwargs)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"status {resp.status_code}")
            resp.raise_for_status()
            data = resp.json() if want == "json" else resp.text
            cache.put(namespace, cache_key, data)
            return data
        except Exception as e:  # noqa: BLE001
            last_exc = e
            if attempt < settings.HTTP_MAX_RETRIES:
                time.sleep(1.0 * (attempt + 1))
    return None


def get_json(url: str, *, namespace: str, params: dict | None = None) -> Any | None:
    return _request("GET", url, namespace=namespace,
                    cache_key={"url": url, "params": params or {}}, want="json", params=params)


def post_json(url: str, *, namespace: str, json_body: dict) -> Any | None:
    return _request("POST", url, namespace=namespace,
                    cache_key={"url": url, "body": json_body}, want="json", json=json_body)
