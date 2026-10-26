"""Model client for Navigator agents.

OpenAI-compatible, so ONE client serves both providers:
  * "meta" -> the Meta Model API (production), base_url + key from config/settings.py
  * "dev"  -> this VM's OpenAI-compatible endpoint (routellm), used to prove the logic now

Transpose to Meta is env-only: set META_MODEL_API_KEY (see docs/TRANSPOSE_TO_META.md).

Hardening:
  * timeouts + bounded retries with backoff
  * JSON-mode request with graceful text-extraction fallback
  * the API key is NEVER logged or printed
"""
from __future__ import annotations
import json
import time
from typing import Any

from config import settings


class ModelUnavailable(RuntimeError):
    """Raised when the model endpoint cannot be reached after retries."""


class MetaModelClient:
    """Calls a chat model and returns text (or parsed JSON).

    Despite the name (kept for the Meta production path), this transparently drives the
    dev endpoint too — the provider is resolved from settings at construction time.
    """

    def __init__(self, model: str | None = None, api_key: str | None = None,
                 base_url: str | None = None):
        prov = settings.active_provider()
        self.provider = prov["name"]
        self.model = model or prov["default_model"]
        # api_key is held only to construct the client; never logged.
        self._api_key = api_key or prov["api_key"]
        self.base_url = base_url or prov["base_url"]
        self._client = None

    def _lazy_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self._api_key or "missing",
                base_url=self.base_url,
                timeout=settings.LLM_TIMEOUT_S,
                max_retries=0,  # we manage retries ourselves for clearer logging
            )
        return self._client

    # -- low level ------------------------------------------------------------
    def _call(self, messages: list[dict], temperature: float, json_mode: bool) -> str:
        client = self._lazy_client()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "messages": messages,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        last_err: Exception | None = None
        for attempt in range(settings.LLM_MAX_RETRIES + 1):
            try:
                resp = client.chat.completions.create(**kwargs)
                return resp.choices[0].message.content or ""
            except Exception as e:  # noqa: BLE001 - surface a redacted summary only
                last_err = e
                # If json_mode is unsupported by the model, retry once without it.
                if json_mode and "response_format" in str(e).lower():
                    kwargs.pop("response_format", None)
                    json_mode = False
                    continue
                if attempt < settings.LLM_MAX_RETRIES:
                    time.sleep(1.5 * (attempt + 1))
        raise ModelUnavailable(
            f"model '{self.model}' via provider '{self.provider}' failed: "
            f"{type(last_err).__name__}"
        )

    # -- public ---------------------------------------------------------------
    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        return self._call(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature, json_mode=False,
        )

    def complete_json(self, system: str, user: str, temperature: float = 0.2,
                      default: dict | None = None) -> dict[str, Any]:
        """Return parsed JSON, with graceful fallback.

        On model failure returns {"_unavailable": True} (or the provided default) so the
        pipeline can degrade gracefully and note the source as unavailable.
        """
        sys_json = system + "\n\nRespond with a single valid JSON object and nothing else."
        try:
            raw = self._call(
                [{"role": "system", "content": sys_json}, {"role": "user", "content": user}],
                temperature, json_mode=True,
            )
        except ModelUnavailable:
            out = dict(default or {})
            out["_unavailable"] = True
            return out
        return self._parse(raw, default)

    @staticmethod
    def _parse(raw: str, default: dict | None = None) -> dict[str, Any]:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(raw[start:end + 1])
                except json.JSONDecodeError:
                    pass
            out = dict(default or {})
            out["_parse_error"] = True
            return out
