"""Benchmark scoring harness: top-1 / top-5 hit rate over solved public cases.

Status: SCAFFOLD (Designed). Wires the loop; ranking comparison is a TODO.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from src.orchestrator.coordinator import Coordinator
from src.utils.schema import CaseInput


def load_answers(cases_dir: Path) -> dict:
    f = cases_dir / "_answers.json"
    return json.loads(f.read_text()) if f.exists() else {}


def score_case(result: dict, truth: dict) -> dict:
    """TODO: compare ranked candidates in `result` against `truth` (causal gene/variant)."""
    return {"top1": None, "top5": None, "note": "scoring not implemented (scaffold)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="benchmarks/cases")
    ap.add_argument("--out", default="benchmarks/results")
    args = ap.parse_args()

    cases_dir = Path(args.cases)
    answers = load_answers(cases_dir)
    coord = Coordinator()
    scores = []

    for case_file in sorted(cases_dir.glob("*.json")):
        if case_file.name.startswith("_"):
            continue
        case = CaseInput(**json.loads(case_file.read_text()))
        result = coord.run(case)
        scores.append({case.case_id: score_case(result, answers.get(case.case_id, {}))})

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    (out / "scores.json").write_text(json.dumps(scores, indent=2))
    print(json.dumps(scores, indent=2))


if __name__ == "__main__":
    main()
