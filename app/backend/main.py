"""Demo app backend (FastAPI).

Endpoints:
  GET  /health            -> liveness + active provider
  GET  /cases             -> list bundled benchmark cases
  POST /run               -> run the 8-agent pipeline on a submitted/selected case
  GET  /dossier/{case_id} -> download the rendered dossier PDF
  GET  /                  -> serve the single-page demo frontend
"""
from __future__ import annotations
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse

from config import settings
from src.orchestrator.coordinator import Coordinator
from src.utils.schema import CaseInput

app = FastAPI(title="Navigator Genome Pilot", version="1.0.0")

FRONTEND = settings.ROOT / "app" / "frontend" / "index.html"
CASES_DIR = settings.ROOT / "benchmarks" / "cases"


@app.get("/health")
def health():
    return {"status": "ok", "provider": settings.active_provider()["name"],
            "service": "navigator-genome-pilot"}


@app.get("/cases")
def list_cases():
    out = []
    for f in sorted(CASES_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            d = json.loads(f.read_text())
            out.append({"file": f.name, "case_id": d.get("case_id"),
                        "summary": d.get("clinical_summary", "")[:160]})
        except Exception:
            continue
    return {"cases": out}


@app.post("/run")
def run_case(case: CaseInput):
    """Run the 8-agent pilot on a submitted case and return results + evidence + dossier."""
    try:
        result = Coordinator().run(case)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"pipeline error: {type(e).__name__}: {e}")
    return JSONResponse(result)


@app.post("/run/{case_file}")
def run_bundled(case_file: str):
    """Run a bundled benchmark case by filename (convenience for the demo UI)."""
    p = (CASES_DIR / case_file).resolve()
    if not str(p).startswith(str(CASES_DIR.resolve())) or not p.exists():
        raise HTTPException(status_code=404, detail="case not found")
    case = CaseInput(**json.loads(p.read_text()))
    return JSONResponse(Coordinator().run(case))


@app.get("/dossier/{case_id}")
def get_dossier(case_id: str):
    safe = "".join(c for c in case_id if c.isalnum() or c in "-_")
    pdf = settings.DATA_DIR / f"dossier_{safe}.pdf"
    if not pdf.exists():
        raise HTTPException(status_code=404, detail="dossier not found — run the case first")
    return FileResponse(str(pdf), media_type="application/pdf", filename=pdf.name)


@app.get("/", response_class=HTMLResponse)
def index():
    if FRONTEND.exists():
        return HTMLResponse(FRONTEND.read_text())
    return HTMLResponse("<h1>Navigator Genome Pilot</h1><p>frontend missing</p>")
