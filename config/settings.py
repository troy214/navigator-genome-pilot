"""Central settings. Reads from environment (.env locally, AWS params in prod).

Provider switch (critical for "transpose to Meta later"):
  * If META_MODEL_API_KEY is set  -> PROVIDER = "meta"  (production path, Meta Model API)
  * Otherwise                      -> PROVIDER = "dev"   (this VM's OpenAI-compatible endpoint)

Swapping to Meta is a ONE-LINE / env-only change: export META_MODEL_API_KEY.
The API key is NEVER logged or printed anywhere in the codebase.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent

# --- Meta Model API (production) ---------------------------------------------
META_MODEL_API_KEY = os.getenv("META_MODEL_API_KEY", "")
META_MODEL_API_BASE_URL = os.getenv("META_MODEL_API_BASE_URL", "https://api.meta.ai/v1")
META_MODEL_TEAM_ID = os.getenv("META_MODEL_TEAM_ID", "")

# --- Dev stand-in endpoint (OpenAI-compatible, this VM) -----------------------
# Used ONLY to prove the pipeline logic end-to-end while no Meta key is present.
DEV_API_BASE_URL = os.getenv("DEV_API_BASE_URL", "https://routellm.abacus.ai/v1")
DEV_API_KEY = os.getenv("DEV_API_KEY", os.getenv("ABACUS_API_KEY", ""))
DEV_MODEL = os.getenv("DEV_MODEL", "gpt-5.4-mini")

# --- Provider resolution ------------------------------------------------------
# Explicit override wins; otherwise infer from whether a Meta key is present.
PROVIDER = os.getenv("PROVIDER", "meta" if META_MODEL_API_KEY else "dev").lower()


def active_provider() -> dict:
    """Return the resolved provider config (base_url, api_key, default_model).

    The api_key is returned for use by the client only — callers must never log it.
    """
    if PROVIDER == "meta":
        return {
            "name": "meta",
            "base_url": META_MODEL_API_BASE_URL,
            "api_key": META_MODEL_API_KEY,
            "default_model": os.getenv("META_DEFAULT_MODEL", "muse-spark"),
        }
    return {
        "name": "dev",
        "base_url": DEV_API_BASE_URL,
        "api_key": DEV_API_KEY,
        "default_model": DEV_MODEL,
    }


# --- Model request tuning -----------------------------------------------------
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "60"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

# --- External bio-data APIs (free, no key) -----------------------------------
HTTP_TIMEOUT_S = float(os.getenv("HTTP_TIMEOUT_S", "20"))
HTTP_MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "2"))
# Polite contact string sent to NCBI E-utilities / Europe PMC per their etiquette.
API_CONTACT_EMAIL = os.getenv("API_CONTACT_EMAIL", "troyburnsfamily@gmail.com")
API_TOOL_NAME = "navigator-genome-pilot"

# --- AWS backbone (orchestration / storage / demo app) -----------------------
AWS_REGION = os.getenv("AWS_REGION", "")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "")
AWS_S3_DOSSIER_PREFIX = os.getenv("AWS_S3_DOSSIER_PREFIX", "navigator/dossiers/")

# --- App ----------------------------------------------------------------------
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

# --- Researcher API (programmatic access for research facilities) --------------
# When on (default), the versioned /api/v1/* endpoints require a valid X-API-Key.
# The public web demo endpoints are NEVER gated by this. Toggle OFF only for local
# testing with: API_KEYS_REQUIRED=0
API_KEYS_REQUIRED = os.getenv("API_KEYS_REQUIRED", "1").lower() in ("1", "true", "yes", "on")
# Location of the salted-hash key store (git-ignored). Override for tests via env.
API_KEYS_STORE = os.getenv("API_KEYS_STORE", str(ROOT / "data" / "api_keys.json"))

# --- Researcher API throttling / quota controls --------------------------------
# These global DEFAULTS apply to every API key unless the key carries a per-key
# override (see src/utils/api_keys.py and scripts/manage_api_keys.py). They protect
# shared processing capacity from a single facility pushing too much work at once.
# They DO NOT affect the public web demo endpoints (/run, /lab, etc.) in any way.
#
# NOTE: the rate-limit and in-flight counters are PER PROCESS (per uvicorn worker).
# With a single worker (the current deployment) that is the whole app. If scaled to
# multiple workers/hosts, move the counters to a shared store (e.g. Redis) — see
# src/utils/throttle.py for where the swap would go.

# Per-request variant cap: reject /api/v1/analyze when the submitted variant count
# (VCF data records, or JSON variant-list entries) exceeds this.
API_MAX_VARIANTS_PER_REQUEST = int(os.getenv("API_MAX_VARIANTS_PER_REQUEST", "50000"))

# Per-key sliding-window request rate limits (primarily for the expensive /analyze).
API_REQUESTS_PER_MINUTE = int(os.getenv("API_REQUESTS_PER_MINUTE", "10"))
API_REQUESTS_PER_DAY = int(os.getenv("API_REQUESTS_PER_DAY", "200"))

# Max concurrent in-flight /analyze runs per key.
API_MAX_CONCURRENT_ANALYSES = int(os.getenv("API_MAX_CONCURRENT_ANALYSES", "2"))

# --- Genomic streaming data layer (Stages 01–06) ------------------------------
# Opt-in gate: when enabled, the deterministic data layer (ingest→normalize→QC→
# store→index→annotate→rank) runs BEFORE the agents and hands Intake a ranked,
# pre-filtered candidate set. Default OFF so existing behavior / demo cases are
# unchanged. See docs/DATA_LAYER_DESIGN.md ("how to enable the full gated path").
DATA_LAYER_GATE_ENABLED = os.getenv("DATA_LAYER_GATE_ENABLED", "").lower() in ("1", "true", "yes", "on")
# Optional override for the columnar store location (defaults to data/variant_store).
DATA_LAYER_STORE_DIR = os.getenv("DATA_LAYER_STORE_DIR", "")

# --- Paths --------------------------------------------------------------------
AGENTS_CONFIG = ROOT / "config" / "agents.yaml"
DEV_MODELS_CONFIG = ROOT / "config" / "models.dev.yaml"
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
RUNS_DIR = DATA_DIR / "runs"

for _d in (DATA_DIR, CACHE_DIR, RUNS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
