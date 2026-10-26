"""Resolve which model each agent uses, for the active provider.

- Provider "meta" -> model names from config/agents.yaml (muse-spark / muse-spark-open-1026)
- Provider "dev"  -> model names from config/models.dev.yaml (gpt-5.4-mini)

This is the layer that makes the Meta swap env-only: no agent code mentions a model name.
"""
from __future__ import annotations
from functools import lru_cache

import yaml

from config import settings


@lru_cache(maxsize=1)
def _meta_map() -> dict:
    data = yaml.safe_load(settings.AGENTS_CONFIG.read_text()) or {}
    agents = data.get("agents", {})
    return {name: cfg.get("model") for name, cfg in agents.items()}


@lru_cache(maxsize=1)
def _dev_map() -> dict:
    if not settings.DEV_MODELS_CONFIG.exists():
        return {}
    data = yaml.safe_load(settings.DEV_MODELS_CONFIG.read_text()) or {}
    m = dict(data.get("agents", {}))
    m["__default__"] = data.get("default")
    return m


def model_for(agent_name: str) -> str:
    """Return the model id the given agent should use under the active provider."""
    prov = settings.active_provider()
    if prov["name"] == "meta":
        return _meta_map().get(agent_name) or prov["default_model"]
    dev = _dev_map()
    return dev.get(agent_name) or dev.get("__default__") or prov["default_model"]
