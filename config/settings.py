"""Central settings. Reads from environment (.env locally, AWS params in prod)."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent

META_MODEL_API_KEY = os.getenv("META_MODEL_API_KEY", "")
META_MODEL_API_BASE_URL = os.getenv("META_MODEL_API_BASE_URL", "https://api.meta.ai/v1")
META_MODEL_TEAM_ID = os.getenv("META_MODEL_TEAM_ID", "")

AWS_REGION = os.getenv("AWS_REGION", "")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "")

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

AGENTS_CONFIG = ROOT / "config" / "agents.yaml"
