"""Tiny on-disk JSON cache for external API responses.

Keeps demo runs fast and repeatable, and respects the shared-IP network rules by not
re-hitting an API we already queried. Keyed by a hash of (namespace + request args).
"""
from __future__ import annotations
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from config import settings

TTL_S = 60 * 60 * 24 * 14  # 14 days — bio-database records are slow-moving


def _key(namespace: str, payload: Any) -> str:
    h = hashlib.sha256(
        (namespace + "::" + json.dumps(payload, sort_keys=True, default=str)).encode()
    ).hexdigest()[:40]
    return f"{namespace}_{h}"


def get(namespace: str, payload: Any) -> Any | None:
    p = settings.CACHE_DIR / f"{_key(namespace, payload)}.json"
    if not p.exists():
        return None
    try:
        obj = json.loads(p.read_text())
        if time.time() - obj.get("_ts", 0) > TTL_S:
            return None
        return obj.get("data")
    except Exception:
        return None


def put(namespace: str, payload: Any, data: Any) -> None:
    p = settings.CACHE_DIR / f"{_key(namespace, payload)}.json"
    try:
        p.write_text(json.dumps({"_ts": time.time(), "data": data}))
    except Exception:
        pass  # cache is best-effort; never fail the pipeline over it
