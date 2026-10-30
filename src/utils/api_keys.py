"""File-backed API key store for the researcher-facing Navigator API.

RESEARCH USE ONLY — this authenticates research facilities to a research tool whose
outputs are hypotheses with explicit uncertainty, never a diagnosis and never medical
advice. The key layer only controls access; it makes no clinical claim.

Security model
--------------
* A facility is issued ONE full plaintext key, shown exactly once, of the form::

      nvk_<key_id>_<secret>

  where ``key_id`` is a short public identifier (``nvk_`` + 8 hex chars) so it can be
  extracted from the presented key for O(1) lookup, and ``secret`` is a long URL-safe
  random string.
* We persist ONLY a salted SHA-256 hash of the secret plus its per-key random salt —
  never the plaintext secret. A lost key cannot be recovered, only revoked + re-issued.
* Verification extracts the key_id, looks up the record, recomputes the salted hash and
  compares it in constant time (``hmac.compare_digest``).

Store file (``data/api_keys.json``, git-ignored) — a JSON list of records::

    {"key_id","label","salt","hashed_secret","created_at","active","notes"}
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings

KEY_PREFIX = "nvk_"
_KEY_ID_BYTES = 4           # -> 8 hex chars
_SECRET_BYTES = 32          # -> ~43 url-safe chars
_SALT_BYTES = 16


def _store_path() -> Path:
    return Path(settings.API_KEYS_STORE)


# --------------------------------------------------------------------------- #
# Persistence (robust to a missing / empty / corrupt store)
# --------------------------------------------------------------------------- #
def _load() -> list[dict[str, Any]]:
    p = _store_path()
    if not p.exists():
        return []
    try:
        text = p.read_text().strip()
        if not text:
            return []
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        # Never crash auth on a malformed store; treat as empty (fail closed on verify).
        return []


def _save(records: list[dict[str, Any]]) -> None:
    p = _store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(records, indent=2))
    tmp.replace(p)  # atomic on same filesystem
    try:
        p.chmod(0o600)  # best-effort: restrict to owner
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Hashing
# --------------------------------------------------------------------------- #
def _hash_secret(secret: str, salt: str) -> str:
    """Salted SHA-256 of the secret. Deterministic for a given (secret, salt)."""
    return hashlib.sha256((salt + secret).encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def generate_key(label: str, notes: str = "") -> tuple[str, dict[str, Any]]:
    """Create + persist a new key record; return (full_plaintext_key, record).

    The returned plaintext key is the ONLY time the secret is available; the store
    keeps only its salted hash. ``label`` is the research facility name.
    """
    label = (label or "").strip()
    if not label:
        raise ValueError("label (research facility name) is required")

    key_id = KEY_PREFIX + secrets.token_hex(_KEY_ID_BYTES)
    salt = secrets.token_hex(_SALT_BYTES)
    secret = secrets.token_urlsafe(_SECRET_BYTES)
    full_key = f"{key_id}_{secret}"

    record = {
        "key_id": key_id,
        "label": label,
        "salt": salt,
        "hashed_secret": _hash_secret(secret, salt),
        "created_at": _now_iso(),
        "active": True,
        "notes": (notes or "").strip(),
    }
    records = _load()
    records.append(record)
    _save(records)

    # Return a public view of the record (no salt / hash) alongside the plaintext key.
    return full_key, public_record(record)


def _split_presented(presented_key: str) -> tuple[str, str] | None:
    """Split 'nvk_<id>_<secret>' -> (key_id, secret). None if malformed."""
    if not presented_key or not presented_key.startswith(KEY_PREFIX):
        return None
    parts = presented_key.split("_", 2)  # ['nvk', '<id>', '<secret>']
    if len(parts) != 3 or not parts[1] or not parts[2]:
        return None
    key_id = f"{KEY_PREFIX}{parts[1]}"
    secret = parts[2]
    return key_id, secret


def verify_key(presented_key: str) -> dict[str, Any] | None:
    """Return the matching ACTIVE record for a presented full key, else None.

    Constant-time hash comparison; unknown key_id, inactive record, or mismatched
    secret all return None.
    """
    split = _split_presented(presented_key or "")
    if split is None:
        return None
    key_id, secret = split

    for rec in _load():
        if rec.get("key_id") != key_id:
            continue
        if not rec.get("active", False):
            return None
        expected = rec.get("hashed_secret", "")
        candidate = _hash_secret(secret, rec.get("salt", ""))
        if hmac.compare_digest(candidate, expected):
            return rec
        return None  # key_id matched but secret did not — do not keep scanning
    return None


def list_keys() -> list[dict[str, Any]]:
    """Return public views of all key records (no secrets / salts / hashes)."""
    return [public_record(r) for r in _load()]


def revoke_key(key_id: str) -> bool:
    """Deactivate a key by its public key_id. Returns True if a key was changed."""
    records = _load()
    changed = False
    for rec in records:
        if rec.get("key_id") == key_id and rec.get("active", False):
            rec["active"] = False
            rec["revoked_at"] = _now_iso()
            changed = True
    if changed:
        _save(records)
    return changed


def public_record(rec: dict[str, Any]) -> dict[str, Any]:
    """A record view safe to log / return: never includes salt or hashed_secret."""
    return {
        "key_id": rec.get("key_id"),
        "label": rec.get("label"),
        "created_at": rec.get("created_at"),
        "active": rec.get("active", False),
        "notes": rec.get("notes", ""),
        **({"revoked_at": rec["revoked_at"]} if rec.get("revoked_at") else {}),
    }
