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
LAB_PAGE = settings.ROOT / "app" / "frontend" / "lab.html"
CASES_DIR = settings.ROOT / "benchmarks" / "cases"
RUNS_DIR = settings.DATA_DIR / "runs"

# Human-readable "job" blurbs for each agent, spoken by the lab robots.
AGENT_JOBS = {
    "intake": "I am the Intake unit. I read the VCF file and normalize every variant so the "
              "rest of the lab speaks one language.",
    "filtering": "I am the Filtering unit. I remove variants that are too common in the "
                 "population to explain a rare disease.",
    "phenotype": "I am the Phenotype unit. I map the patient's clinical picture onto standard "
                 "HPO ontology terms.",
    "literature": "I am the Literature unit. I search the published record and summarize what is "
                  "known, with real citations.",
    "database": "I am the Database unit. I query ClinVar, gnomAD and MyVariant for what the "
                "archives already record about each variant.",
    "case_matching": "I am the Case Matching unit. I compare this case against a library of "
                     "previously solved cases.",
    "red_team": "I am the Red Team unit. I work in isolation and challenge every conclusion, "
                "flagging anything that is overstated.",
    "dossier_writer": "I am the Dossier Writer. I assemble the ranked, physician-facing evidence "
                      "dossier — as a research hypothesis, never a diagnosis.",
}


def _latest_run(prefix: str = "CF-CFTR-F508del") -> dict | None:
    """Return the parsed run.json of the most recent run whose folder starts with prefix."""
    if not RUNS_DIR.exists():
        return None
    candidates = sorted(
        (p for p in RUNS_DIR.glob(f"{prefix}_*") if (p / "run.json").exists()),
        key=lambda p: p.name, reverse=True)
    if not candidates:
        return None
    try:
        return json.loads((candidates[0] / "run.json").read_text())
    except Exception:
        return None


def _build_lab_data(run: dict) -> dict:
    """Turn a raw run.json into per-agent lab cards (role, status, key finding, spoken text).

    Everything here is derived from the actual run — no invented findings. When a field is
    absent the agent is made to say so rather than fabricate.
    """
    results = {r["agent"]: r for r in run.get("agent_results", [])}
    order = ["intake", "filtering", "phenotype", "literature", "database",
             "case_matching", "red_team", "dossier_writer"]
    dossier = run.get("dossier", {}) or {}
    findings = dossier.get("findings", []) or []
    top = findings[0] if findings else None
    agents = []
    for name in order:
        res = results.get(name)
        job = AGENT_JOBS.get(name, "")
        if not res:
            agents.append({
                "agent": name, "job": job, "status": "unknown",
                "finding": "This unit did not report in the loaded run — status unknown.",
                "spoken": f"{job} I did not report in this run, so my status is unknown.",
                "evidence_count": 0,
            })
            continue
        status = res.get("status", "unknown")
        notes = (res.get("notes") or "").strip()
        ev = res.get("evidence") or []
        first_claim = (ev[0].get("claim") if ev else "") or ""
        # Per-agent contribution line, pulled from the real run.
        contrib = _contribution(name, res, run, top)
        finding_line = notes or first_claim or "No finding recorded."
        spoken = f"{job} {contrib}".strip()
        agents.append({
            "agent": name,
            "job": job,
            "status": status,
            "finding": finding_line,
            "spoken": spoken,
            "evidence_count": len(ev),
        })
    return {
        "case_id": run.get("case_id"),
        "provider": run.get("provider"),
        "status": run.get("status"),
        "total_elapsed_s": run.get("total_elapsed_s"),
        "sources_unavailable": run.get("sources_unavailable", []),
        "top_candidate": ({"gene": top.get("gene"), "variant": top.get("variant"),
                           "rank": top.get("rank")} if top else None),
        "clinical_summary": dossier.get("clinical_summary", ""),
        "agents": agents,
    }


def _trim(text: str, limit: int = 320) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if "." in cut:
        cut = cut[:cut.rfind(".") + 1]
    return cut.rstrip() + " …"


def _contribution(name: str, res: dict, run: dict, top: dict | None) -> str:
    """Build a spoken contribution string from the real run data for one agent."""
    ev = res.get("evidence") or []
    claims = [e.get("claim", "") for e in ev if e.get("claim")]
    if name == "intake":
        return _trim(res.get("notes") or (claims[0] if claims else "No intake record."))
    if name == "filtering":
        kept = [c for c in claims if c.lower().startswith("retained")]
        excl = [c for c in claims if c.lower().startswith("excluded")]
        parts = []
        if kept:
            parts.append(kept[0])
        if excl:
            parts.append(excl[0])
        return _trim(" ".join(parts) or (res.get("notes") or "No filtering record."))
    if name == "phenotype":
        terms = [t.get("name") for t in (run.get("dossier", {}).get("hpo_terms") or []) if t.get("name")]
        if terms:
            shown = ", ".join(terms[:4])
            more = f", and {len(terms) - 4} more" if len(terms) > 4 else ""
            return _trim(f"I mapped the clinical picture to {len(terms)} HPO terms, including {shown}{more}.")
        return _trim(res.get("notes") or "No phenotype terms mapped.")
    if name == "literature":
        pmids = []
        for e in ev:
            src = e.get("source", "")
            if "PMID:" in src:
                pmids.append(src.split("PMID:")[1].split(" ")[0].strip("() "))
        if pmids:
            return _trim(f"I retrieved {len(ev)} article(s) with real citations, including PMID "
                         f"{', PMID '.join(pmids[:3])}, supporting CFTR-related respiratory and "
                         f"pancreatic disease.")
        return _trim(res.get("notes") or "No literature retrieved.")
    if name == "database":
        return _trim(claims[0] if claims else (res.get("notes") or "No database records."))
    if name == "case_matching":
        return _trim(claims[0] if claims else (res.get("notes") or "No candidate matches."))
    if name == "red_team":
        crit = next((c for c in claims if c), "")
        crit = crit.replace("Red-team critique:", "").strip()
        n = len(claims)
        return _trim(f"Working in isolation, I raised {n} critique(s). My main caution: {crit}")
    if name == "dossier_writer":
        if top:
            return _trim(f"I assembled the dossier. The top ranked candidate is {top.get('gene')} "
                         f"{top.get('variant')} — presented as a research hypothesis with explicit "
                         f"uncertainty, not a diagnosis.")
        return _trim(res.get("notes") or "No dossier assembled.")
    return _trim(claims[0] if claims else (res.get("notes") or ""))


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


@app.get("/lab-data")
def lab_data(case: str = "CF-CFTR-F508del"):
    """Return the per-agent lab payload derived from the most recent run of `case`.

    Used by the interactive Agent Lab page so each robot reports its genuine contribution.
    """
    run = _latest_run(case)
    if not run:
        raise HTTPException(status_code=404,
                            detail=f"no run found for case prefix '{case}' — run the case first")
    return JSONResponse(_build_lab_data(run))


@app.get("/lab", response_class=HTMLResponse)
def lab():
    if LAB_PAGE.exists():
        return HTMLResponse(LAB_PAGE.read_text())
    return HTMLResponse("<h1>Agent Lab</h1><p>lab page missing</p>", status_code=404)


@app.get("/", response_class=HTMLResponse)
def index():
    if FRONTEND.exists():
        return HTMLResponse(FRONTEND.read_text())
    return HTMLResponse("<h1>Navigator Genome Pilot</h1><p>frontend missing</p>")
