#!/usr/bin/env python3
"""Minimal end-to-end verification of the Meta Model API execution path.

RESEARCH USE ONLY. This makes ONE tiny real completion through the app's own LLM client
(src/models/meta_client.MetaModelClient) so it exercises the real production code path —
the same client the 8 agents use — not a raw HTTP call. Token usage is intentionally
minimal (a one-word reply).

Routing: the app selects the provider in config/settings.py. To route through Meta, set
META_MODEL_API_KEY (and optionally PROVIDER=meta / META_DEFAULT_MODEL). This script does
NOT hardcode any key; it relies on the environment / .env the app already reads.

Offline-safe: if no Meta key is configured, it prints a clear message and exits non-zero
WITHOUT making any network call, so it is safe to re-run anytime.

Exit codes: 0 = Meta path verified; 1 = not configured for Meta; 2 = call failed.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import settings  # noqa: E402


def main() -> int:
    prov = settings.active_provider()
    # Resolve the model exactly as the agents do (config/agents.yaml via model_for),
    # so this probe hits the SAME model id the pipeline uses — not the bare fallback.
    from src.models.config import model_for

    probe_agent = "intake"  # representative agent; all 8 map to the same text model
    model_id = model_for(probe_agent)

    print("=" * 66)
    print("  Meta Model API path verification — RESEARCH USE ONLY")
    print("=" * 66)
    print(f"  Resolved provider : {prov['name']}")
    print(f"  Base URL          : {prov['base_url']}")
    print(f"  Model id (agents) : {model_id}  (resolved via model_for('{probe_agent}'))")
    print(f"  Fallback default  : {prov['default_model']}")
    print(f"  API key present   : {bool(prov['api_key'])}")
    print("-" * 66)

    if prov["name"] != "meta":
        print("  NOT routed to Meta. The app resolved provider =", prov["name"], ".")
        print("  To route through Meta, set META_MODEL_API_KEY (and optionally")
        print("  PROVIDER=meta) in the environment / .env, then re-run.")
        return 1
    if not prov["api_key"]:
        print("  Provider is 'meta' but no API key is configured — cannot call.")
        print("  Set META_MODEL_API_KEY in the environment / .env and re-run.")
        return 1

    # One minimal real call through the app's own client (tiny prompt / tiny reply),
    # using the agents' resolved model id so the probe is faithful to the real path.
    from src.models.meta_client import MetaModelClient, ModelUnavailable

    client = MetaModelClient(model_id)
    system = "You are a connectivity probe. Reply with exactly one word."
    user = "Reply with the single word: OK"
    try:
        reply = client.complete(system, user, temperature=0.0)
    except ModelUnavailable as e:
        print(f"  RESULT: FAIL — model unavailable: {e}")
        print("  Likely causes: wrong base URL, invalid/expired key, or unknown model id.")
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"  RESULT: FAIL — {type(e).__name__}: {e}")
        return 2

    reply = (reply or "").strip()
    if not reply:
        print("  RESULT: FAIL — empty response from the model.")
        return 2

    preview = reply if len(reply) <= 120 else reply[:117] + "..."
    print(f"  RESULT: PASS — received a well-formed completion.")
    print(f"  Model reply       : {preview!r}")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
