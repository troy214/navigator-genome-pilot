"""Benchmark scoring harness: top-1 / top-5 hit rate over solved public cases.

Runs the full pipeline on every case in benchmarks/cases/, compares the ranked candidate
genes against the hidden ground truth in _answers.json, and writes scores.json + a
markdown report. Degrades gracefully if the LLM/APIs are unavailable.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.orchestrator.coordinator import Coordinator
from src.utils.schema import CaseInput


def load_answers(cases_dir: Path) -> dict:
    f = cases_dir / "_answers.json"
    return json.loads(f.read_text()) if f.exists() else {}


def ranked_genes(result: dict) -> list[str]:
    findings = result.get("dossier", {}).get("findings", [])
    return [f.get("gene") for f in sorted(findings, key=lambda x: x.get("rank", 99))
            if f.get("gene")]


def score_case(result: dict, truth: dict) -> dict:
    if not truth:
        return {"top1": None, "top5": None, "note": "no ground truth for this case"}
    accepted = {g.upper() for g in truth.get("accepted_genes", [truth.get("gene", "")])}
    ranked = [g.upper() for g in ranked_genes(result)]
    top1 = bool(ranked and ranked[0] in accepted)
    top5 = any(g in accepted for g in ranked[:5])
    return {
        "top1": top1, "top5": top5,
        "expected_gene": truth.get("gene"),
        "ranked_genes": ranked[:5],
        "provider": result.get("provider"),
        "sources_unavailable": result.get("sources_unavailable", []),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="benchmarks/cases")
    ap.add_argument("--out", default="benchmarks/results")
    args = ap.parse_args()

    cases_dir = Path(args.cases)
    answers = load_answers(cases_dir)
    coord = Coordinator()
    per_case = {}

    for case_file in sorted(cases_dir.glob("*.json")):
        if case_file.name.startswith("_"):
            continue
        case = CaseInput(**json.loads(case_file.read_text()))
        print(f"[score] running {case.case_id} ...")
        try:
            result = coord.run(case, persist=False)
            per_case[case.case_id] = score_case(result, answers.get(case.case_id, {}))
        except Exception as e:  # noqa: BLE001
            per_case[case.case_id] = {"top1": None, "top5": None,
                                      "error": f"{type(e).__name__}: {e}"}

    scored = [c for c in per_case.values() if c.get("top1") is not None]
    n = len(scored)
    top1_rate = sum(1 for c in scored if c["top1"]) / n if n else 0.0
    top5_rate = sum(1 for c in scored if c["top5"]) / n if n else 0.0

    summary = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "n_scored": n,
        "top1_hit_rate": round(top1_rate, 3),
        "top5_hit_rate": round(top5_rate, 3),
        "per_case": per_case,
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scores.json").write_text(json.dumps(summary, indent=2))

    md = [f"# Benchmark results\n",
          f"Generated: {summary['generated']}\n",
          f"- Cases scored: **{n}**",
          f"- Top-1 hit rate: **{top1_rate:.0%}**",
          f"- Top-5 hit rate: **{top5_rate:.0%}**\n",
          "| Case | Expected | Top-1 | Top-5 | Ranked (top 5) |",
          "|------|----------|-------|-------|----------------|"]
    for cid, c in per_case.items():
        md.append(f"| {cid} | {c.get('expected_gene','?')} | "
                  f"{'✓' if c.get('top1') else '✗' if c.get('top1') is not None else '—'} | "
                  f"{'✓' if c.get('top5') else '✗' if c.get('top5') is not None else '—'} | "
                  f"{', '.join(c.get('ranked_genes', []) or []) or c.get('error','')} |")
    md.append("\n_Research use only — benchmark over published, already-solved public cases._")
    (out / "report.md").write_text("\n".join(md))

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
