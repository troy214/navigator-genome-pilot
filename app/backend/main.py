"""Demo app backend (FastAPI). Serves the agent board + evidence ledger + dossier view.

Status: SCAFFOLD (Designed). One endpoint wired to the coordinator stub.
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.orchestrator.coordinator import Coordinator
from src.utils.schema import CaseInput

app = FastAPI(title="Navigator Genome Pilot", version="0.1.0-scaffold")


@app.get("/health")
def health():
    return {"status": "ok", "stage": "scaffold"}


@app.post("/run")
def run_case(case: CaseInput):
    """Run the 8-agent pilot on a submitted case and return the dossier payload."""
    result = Coordinator().run(case)
    return JSONResponse(result)
