"""Thin wrapper around the Meta Model API (OpenAI-compatible).

Status: SCAFFOLD (Designed). The call path is written but NOT yet verified against a
live Meta Model API key. Do not treat responses as validated until tested.
"""
from __future__ import annotations
import json
from typing import Any

from config import settings


class MetaModelClient:
    """Calls a Meta model and returns text (or parsed JSON).

    The Meta Model API is OpenAI-compatible, so the official `openai` client works
    when pointed at META_MODEL_API_BASE_URL.
    """

    def __init__(self, model: str, api_key: str | None = None, base_url: str | None = None):
        self.model = model
        self.api_key = api_key or settings.META_MODEL_API_KEY
        self.base_url = base_url or settings.META_MODEL_API_BASE_URL
        self._client = None

    def _lazy_client(self):
        if self._client is None:
            # Imported lazily so the scaffold imports even before deps are installed.
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        """Return the model's text response."""
        client = self._lazy_client()
        resp = client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    def complete_json(self, system: str, user: str, temperature: float = 0.2) -> dict[str, Any]:
        """Return parsed JSON. Falls back to {} on parse failure (logged by caller)."""
        raw = self.complete(system, user, temperature)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(raw[start:end + 1])
                except json.JSONDecodeError:
                    pass
            return {"_parse_error": True, "_raw": raw}
