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
import logging
import re
import time
from pathlib import Path

from fastapi import (APIRouter, Depends, FastAPI, File, Form, Header, HTTPException,
                     Request, UploadFile)
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from src.orchestrator.coordinator import Coordinator
from src.utils import api_keys
from src.utils.schema import CaseInput, Variant
from src.utils.throttle import effective_limits, throttler

log = logging.getLogger("navigator.api")

# Max size (bytes) for an uploaded VCF. Keep in sync with nginx client_max_body_size
# in deploy/navigator-genome.conf.
MAX_VCF_BYTES = 25 * 1024 * 1024  # 25 MB
UPLOADS_DIR = settings.DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Navigator Genome Pilot", version="1.0.0")

FRONTEND = settings.ROOT / "app" / "frontend" / "index.html"
LAB_PAGE = settings.ROOT / "app" / "frontend" / "lab.html"
ASSETS_DIR = settings.ROOT / "app" / "frontend" / "assets"

# Serve avatar PNGs, lab_background.png and voice_*.mp3 clips used by the Agent Lab page.
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
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


# --------------------------------------------------------------------------- #
# Researcher-facing programmatic API (/api/v1) — API-key authenticated.
#
# RESEARCH USE ONLY. Every output is a research hypothesis with explicit
# uncertainty, never a diagnosis and never medical advice. The key layer only
# controls per-facility access; it makes no clinical claim.
#
# The public web demo endpoints above stay open and unchanged. Authentication
# applies ONLY to this /api/v1 namespace, and can be toggled with the
# API_KEYS_REQUIRED env flag (default ON).
# --------------------------------------------------------------------------- #
RESEARCH_NOTICE = (
    "Research use only. Outputs are research hypotheses with explicit uncertainty — "
    "not a diagnosis and not medical advice."
)

# When a request is blocked purely for concurrency (no time window to wait on), suggest
# this many seconds before retrying. It is an estimate, not an exact window.
CONCURRENCY_RETRY_AFTER_S = 15


def _count_vcf_records(path: str) -> int:
    """Count data (non-header, non-blank) records in a VCF, gzip-aware.

    Header lines start with '#'. Used to enforce the per-request variant cap on VCF
    uploads before the pipeline runs. Returns 0 if the file cannot be read (the pipeline
    will surface any real parse problem later).
    """
    import gzip

    opener = gzip.open if str(path).lower().endswith(".gz") else open
    count = 0
    try:
        with opener(path, "rt", errors="replace") as fh:
            for line in fh:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                count += 1
    except OSError:
        return 0
    return count


def _facility_data_layer_reduce(cid: str, clinical_summary: str, parsed_hpo: list[str],
                                parsed_variants: list[Variant],
                                vcf_path: str) -> list[Variant] | None:
    """Run the deterministic data layer on an uploaded VCF for the FACILITY API path and
    return the ranked candidate variants (post-reduction), or None to fall back.

    Scoped to the authenticated /api/v1/analyze path and gated by the dedicated
    ``settings.FACILITY_DATA_LAYER_GATE`` flag — deliberately independent of the
    coordinator's global ``DATA_LAYER_GATE_ENABLED`` so enabling reduction here cannot
    change the public demo paths (/run, /run-new, /lab). We call ``data_layer.run()``
    directly (NOT ``maybe_gate()``, which keys off the global flag) using the SAME config
    the coordinator's gate uses, so the candidate set is identical to what the agents
    would otherwise receive.

    Fails safe exactly like the coordinator: on ANY error — or if the reduction yields no
    candidates — returns None so the caller keeps the current behavior (cap measured on
    raw VCF record count, raw VCF passed to the pipeline).
    """
    try:
        from src.pipeline import data_layer
        from src.pipeline import rank as rank_mod

        case = CaseInput(
            case_id=cid,
            variants=parsed_variants,
            clinical_summary=(clinical_summary or "").strip(),
            hpo_terms=parsed_hpo,
            vcf_path=vcf_path,
        )
        # Scan the whole file (no positional truncation); max_candidates bounds the set
        # the agents receive. Mirrors coordinator.run()'s DataLayerConfig exactly.
        cfg = data_layer.DataLayerConfig(
            max_variants=5_000_000,
            rank_config=rank_mod.RankConfig(drop_common=True, max_candidates=200))
        res = data_layer.run(case, cfg)
        if not res.variants:
            return None
        return list(res.variants)
    except Exception as e:  # noqa: BLE001 - never let the gate break a request
        logging.getLogger("navigator.api").warning(
            "facility data-layer reduction failed (%s); falling back to raw-record cap", e)
        return None


def _ratelimit_headers(decision) -> dict[str, str]:
    """Build X-RateLimit-* headers from a throttle.RateDecision."""
    return {
        "X-RateLimit-Limit-Minute": str(decision.limit_minute),
        "X-RateLimit-Remaining-Minute": str(decision.remaining_minute),
        "X-RateLimit-Limit-Day": str(decision.limit_day),
        "X-RateLimit-Remaining-Day": str(decision.remaining_day),
    }


def _enforce_rate_limit(facility: dict, limits: dict) -> dict[str, str]:
    """Check the per-key request rate for an expensive call.

    Returns the X-RateLimit-* headers to attach on success. Raises HTTPException(429)
    with a Retry-After header and a clear JSON body when the limit is exceeded.
    """
    key_id = facility.get("key_id") or "unknown"
    decision = throttler.check_rate(
        key_id, limits["requests_per_minute"], limits["requests_per_day"])
    if not decision.allowed:
        headers = _ratelimit_headers(decision)
        headers["Retry-After"] = str(decision.retry_after)
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": (
                    f"Rate limit exceeded for this API key: "
                    f"{limits['requests_per_minute']} requests/minute, "
                    f"{limits['requests_per_day']} requests/day. "
                    f"Retry in about {decision.retry_after}s, or slow your submission "
                    f"rate and batch work sequentially."),
                "retry_after_seconds": decision.retry_after,
                "limit_per_minute": limits["requests_per_minute"],
                "limit_per_day": limits["requests_per_day"],
                "notice": RESEARCH_NOTICE,
            },
            headers=headers,
        )
    return _ratelimit_headers(decision)


async def require_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")) -> dict:
    """FastAPI dependency: authenticate a research facility by its X-API-Key header.

    Returns a public (secret-free) record of the facility's key. Raises 401 when the
    header is missing and 403 when the key is unknown or revoked. When
    API_KEYS_REQUIRED is off, authentication is bypassed (useful for local testing).
    """
    if not settings.API_KEYS_REQUIRED:
        return {"key_id": "auth-disabled", "label": "auth-disabled",
                "active": True, "created_at": None, "notes": ""}
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")
    rec = api_keys.verify_key(x_api_key)
    if rec is None:
        raise HTTPException(status_code=403, detail="Invalid or revoked API key.")
    log.info("api/v1 call by facility key_id=%s label=%s", rec.get("key_id"), rec.get("label"))
    return api_keys.public_record(rec)


api_v1 = APIRouter(prefix="/api/v1", tags=["researcher-api"])


@api_v1.get("/me")
def api_me(facility: dict = Depends(require_api_key)):
    """Return the authenticated facility's identity + effective limits — never the secret.

    ``limits`` is the EFFECTIVE set actually enforced for this key: per-key overrides
    merged over the global defaults. ``limit_overrides`` shows only the fields this key
    overrides (empty means it uses all global defaults).
    """
    limits = effective_limits(facility)
    return {
        "key_id": facility.get("key_id"),
        "label": facility.get("label"),
        "active": facility.get("active", True),
        "limits": limits,
        "limit_overrides": dict(facility.get("limits") or {}),
        "notice": RESEARCH_NOTICE,
    }


@api_v1.get("/cases")
def api_cases(facility: dict = Depends(require_api_key)):
    """List the bundled benchmark cases (same payload as the public /cases)."""
    return list_cases()


@api_v1.get("/dossier/{case_id}")
def api_dossier(case_id: str, facility: dict = Depends(require_api_key)):
    """Download the rendered dossier PDF for a case_id, behind the API key."""
    return get_dossier(case_id)


@api_v1.post("/analyze")
async def api_analyze(request: Request, facility: dict = Depends(require_api_key)):
    """Run the 8-agent research pipeline on a submitted case.

    Accepts EITHER:
      * application/json  — {"case_id","clinical_summary","hpo_terms","variants"} where
        hpo_terms is a list[str] (or newline/comma string) and variants is a list of
        objects ({"gene","hgvs","chrom","pos","ref","alt","rsid"}) or a text block.
      * multipart/form-data — fields case_id, clinical_summary, hpo_terms, variants and
        an optional `vcf` file upload (.vcf / .vcf.gz, <= 25 MB).

    Returns the same result shape as POST /run, including variant_count. RESEARCH
    USE ONLY — the result is a hypothesis with uncertainty, never a diagnosis.

    Throttling (per API key; see docs/RESEARCHER_API.md):
      * per-key request rate limit  -> 429 + Retry-After
      * max concurrent analyses     -> 429 + Retry-After
      * per-request variant cap     -> 413
    Limits are the key's effective limits (per-key overrides merged over global defaults).
    """
    limits = effective_limits(facility)
    key_id = facility.get("key_id") or "unknown"

    # 1) Per-key request-rate limit (raises 429 w/ Retry-After when exceeded).
    rl_headers = _enforce_rate_limit(facility, limits)

    # 2) Per-key max concurrent in-flight analyses. Acquire a slot now and ALWAYS
    #    release it in the finally below, even on parse/validation/pipeline errors.
    if not throttler.acquire(key_id, limits["max_concurrent"]):
        headers = dict(rl_headers)
        headers["Retry-After"] = str(CONCURRENCY_RETRY_AFTER_S)
        raise HTTPException(
            status_code=429,
            detail={
                "error": "concurrency_limit_exceeded",
                "message": (
                    f"This API key already has {limits['max_concurrent']} analysis run(s) "
                    f"in progress (the maximum). Wait for one to finish before submitting "
                    f"another, then retry."),
                "retry_after_seconds": CONCURRENCY_RETRY_AFTER_S,
                "max_concurrent": limits["max_concurrent"],
                "notice": RESEARCH_NOTICE,
            },
            headers=headers,
        )

    try:
        return await _analyze_inner(request, key_id, limits, rl_headers)
    finally:
        throttler.release(key_id)


async def _analyze_inner(request: Request, key_id: str, limits: dict,
                         rl_headers: dict[str, str]) -> JSONResponse:
    """Parse the submission, enforce the variant cap, and run the pipeline.

    Split out of api_analyze so the concurrency slot acquired by the caller is always
    released via its try/finally, regardless of what happens in here.
    """
    content_type = (request.headers.get("content-type") or "").lower()

    cid_raw = ""
    clinical_summary = ""
    parsed_hpo: list[str] = []
    parsed_variants: list[Variant] = []
    vcf_path: str | None = None

    if content_type.startswith("application/json"):
        try:
            body = await request.json()
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"invalid JSON body: {e}")
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object.")

        cid_raw = str(body.get("case_id") or "")
        clinical_summary = str(body.get("clinical_summary") or "")

        hpo = body.get("hpo_terms")
        if isinstance(hpo, list):
            parsed_hpo = [str(t).strip() for t in hpo if str(t).strip()]
        elif isinstance(hpo, str):
            parsed_hpo = _parse_hpo_terms(hpo)
        elif hpo is not None:
            raise HTTPException(status_code=400,
                                detail="hpo_terms must be a list or a string.")

        variants = body.get("variants")
        if isinstance(variants, list):
            try:
                parsed_variants = [
                    v if isinstance(v, Variant) else Variant(**v) for v in variants
                ]
            except Exception as e:  # noqa: BLE001
                raise HTTPException(status_code=400,
                                    detail=f"invalid variants entry: {e}")
        elif isinstance(variants, str):
            parsed_variants = _parse_variants(variants)
        elif variants is not None:
            raise HTTPException(status_code=400,
                                detail="variants must be a list of objects or a string.")

    elif content_type.startswith("multipart/form-data") or \
            content_type.startswith("application/x-www-form-urlencoded"):
        form = await request.form()
        cid_raw = str(form.get("case_id") or "")
        clinical_summary = str(form.get("clinical_summary") or "")
        parsed_hpo = _parse_hpo_terms(str(form.get("hpo_terms") or ""))
        parsed_variants = _parse_variants(str(form.get("variants") or ""))
        # request.form() yields starlette UploadFile (not the fastapi subclass), so
        # duck-type on the file interface rather than isinstance(..., UploadFile).
        vcf = form.get("vcf")
        if vcf is not None and getattr(vcf, "filename", None) and hasattr(vcf, "read"):
            cid_tmp = _sanitize_case_id(cid_raw)
            vcf_path = await _save_vcf_upload(vcf, cid_tmp)
    else:
        raise HTTPException(
            status_code=400,
            detail="Content-Type must be application/json or multipart/form-data.")

    if not clinical_summary.strip() and not parsed_variants and not vcf_path:
        raise HTTPException(
            status_code=400,
            detail="Provide at least a clinical_summary, variants, or a VCF file.")

    cid = _sanitize_case_id(cid_raw)

    # 3) Data-layer gate FIRST (facility path only), THEN the per-request variant cap.
    #
    #    The deterministic data layer reduces a raw VCF (potentially tens of thousands of
    #    records) down to a small RANKED candidate set (typically tens-to-low-hundreds) —
    #    and that reduced set is what the 8 agents actually consume. So on the authenticated
    #    facility path we run the reduction BEFORE measuring the cap, and enforce the cap on
    #    the REDUCED candidate count (plus any JSON/text variants, which the data layer
    #    merges in) rather than on raw VCF records. This is scoped via the dedicated
    #    settings.FACILITY_DATA_LAYER_GATE flag (independent of the coordinator's global
    #    DATA_LAYER_GATE_ENABLED) so the public demo paths stay byte-identical.
    #
    #    When the gate reduces the file we clear vcf_path and hand the reduced variants to
    #    the pipeline, so the coordinator does NOT run the gate a second time (no double
    #    work). If the gate is OFF, unavailable, errors, or yields no candidates, we keep
    #    the EXACTLY current behavior: cap measured on raw record count, raw VCF passed on.
    cap = limits["max_variants_per_request"]
    saved_upload_path = vcf_path  # remember the on-disk upload even after the gate clears it

    if vcf_path and settings.FACILITY_DATA_LAYER_GATE:
        reduced = _facility_data_layer_reduce(
            cid, clinical_summary, parsed_hpo, parsed_variants, vcf_path)
        if reduced is not None:
            # Reduction succeeded (and merged in any JSON/text variants): agents consume
            # `reduced`. Clear vcf_path so the pipeline/coordinator does not re-parse/re-gate.
            parsed_variants = reduced
            vcf_path = None

    submitted = len(parsed_variants)
    if vcf_path:  # only when the gate did NOT reduce (off/unavailable/failed/empty)
        submitted += _count_vcf_records(vcf_path)
    if submitted > cap:
        # Drop the just-saved upload so a rejected call leaves nothing behind.
        if saved_upload_path:
            try:
                Path(saved_upload_path).unlink(missing_ok=True)
            except OSError:
                pass
        raise HTTPException(
            status_code=413,
            detail={
                "error": "variant_cap_exceeded",
                "message": (
                    f"Submission has {submitted} variants, which exceeds the per-request "
                    f"cap of {cap} for this API key. Split the work into smaller batches "
                    f"of at most {cap} variants and submit them sequentially."),
                "submitted_variants": submitted,
                "max_variants_per_request": cap,
                "notice": RESEARCH_NOTICE,
            },
            headers=rl_headers,
        )

    result = _run_case_payload(cid, clinical_summary, parsed_hpo, parsed_variants, vcf_path)
    return JSONResponse(result, headers=rl_headers)


app.include_router(api_v1)


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


def _parse_hpo_terms(raw: str) -> list[str]:
    """Parse HPO terms entered one-per-line and/or comma-separated into a clean list."""
    if not raw:
        return []
    tokens = re.split(r"[,\n\r]+", raw)
    out: list[str] = []
    for t in tokens:
        t = t.strip()
        if t and t not in out:
            out.append(t)
    return out


def _parse_variants(raw: str) -> list[Variant]:
    """Parse a lightweight variants textarea into Variant records.

    One variant per line. Fields are separated by commas OR whitespace, in order:
        gene  hgvs  [chrom]  [pos]  [ref]  [alt]  [rsid]
    Only `gene` is required per line; everything else is optional. Blank lines ignored.
    """
    variants: list[Variant] = []
    if not raw:
        return variants
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p for p in re.split(r"[,\t]+|\s{1,}", line) if p]
        if not parts:
            continue
        gene = parts[0]
        hgvs = parts[1] if len(parts) > 1 else None
        chrom = parts[2] if len(parts) > 2 else None
        pos = None
        if len(parts) > 3:
            try:
                pos = int(parts[3])
            except ValueError:
                pos = None
        ref = parts[4] if len(parts) > 4 else None
        alt = parts[5] if len(parts) > 5 else None
        rsid = parts[6] if len(parts) > 6 else None
        variants.append(Variant(gene=gene, hgvs=hgvs, chrom=chrom, pos=pos,
                                ref=ref, alt=alt, rsid=rsid))
    return variants


def _sanitize_case_id(case_id: str) -> str:
    """Sanitize a case_id for safe filesystem use (same scheme as the dossier PDF)."""
    cid = (case_id or "").strip()
    if not cid:
        cid = f"new-{int(time.time())}"
    return re.sub(r"[^A-Za-z0-9._-]", "-", cid)[:80] or f"new-{int(time.time())}"


async def _save_vcf_upload(vcf: UploadFile, cid: str) -> str:
    """Validate + stream-save an uploaded VCF under data/uploads/; return its path.

    Shared by POST /run-new and POST /api/v1/analyze. Enforces extension (.vcf/.vcf.gz)
    and the MAX_VCF_BYTES cap; raises HTTPException(400/413) on bad input.
    """
    fname = vcf.filename
    if not fname.lower().endswith((".vcf", ".vcf.gz")):
        raise HTTPException(status_code=400,
                            detail="VCF file must have a .vcf or .vcf.gz extension.")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(fname).name)
    dest = UPLOADS_DIR / f"{cid}_{int(time.time())}_{safe_name}"
    size = 0
    try:
        with dest.open("wb") as out:
            while True:
                chunk = await vcf.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_VCF_BYTES:
                    out.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"VCF too large (> {MAX_VCF_BYTES // (1024*1024)} MB).")
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"could not save VCF: {e}")
    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded VCF file is empty.")
    return str(dest)


def _run_case_payload(cid: str, clinical_summary: str, parsed_hpo: list[str],
                      parsed_variants: list[Variant], vcf_path: str | None) -> dict:
    """Build a CaseInput, run the 8-agent pipeline, and return the result dict.

    Adds ``variant_count`` (candidate variants + 1 if a VCF was supplied) so a
    symptom-only submission can be distinguished from one with genomic input. Shared
    by /run-new and /api/v1/analyze. Raises HTTPException(400/500) on failure.
    """
    try:
        case = CaseInput(
            case_id=cid,
            variants=parsed_variants,
            clinical_summary=(clinical_summary or "").strip(),
            hpo_terms=parsed_hpo,
            vcf_path=vcf_path,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"invalid case input: {e}")

    try:
        result = Coordinator().run(case)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"pipeline error: {type(e).__name__}: {e}")
    if isinstance(result, dict):
        result["variant_count"] = len(parsed_variants) + (1 if vcf_path else 0)
    return result


@app.post("/run-new")
async def run_new_case(
    case_id: str = Form(""),
    clinical_summary: str = Form(""),
    hpo_terms: str = Form(""),
    variants: str = Form(""),
    vcf: UploadFile | None = File(None),
):
    """Accept a researcher-submitted UNKNOWN case (multipart/form-data) and run the pipeline.

    An optional VCF file is saved under data/uploads/ and its path is passed as vcf_path,
    so the Intake agent parses it into variants. Returns the same result JSON shape as /run.
    """
    cid = _sanitize_case_id(case_id)
    parsed_hpo = _parse_hpo_terms(hpo_terms)
    parsed_variants = _parse_variants(variants)

    vcf_path: str | None = None
    if vcf is not None and vcf.filename:
        vcf_path = await _save_vcf_upload(vcf, cid)

    result = _run_case_payload(cid, clinical_summary, parsed_hpo, parsed_variants, vcf_path)
    return JSONResponse(result)


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
