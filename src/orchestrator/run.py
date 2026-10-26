"""CLI entry point: run the pilot on one case end-to-end.

Usage:
    python -m src.orchestrator.run --case benchmarks/cases/cystic_fibrosis.json
    python -m src.orchestrator.run --case <file> --json   # full JSON output
"""
import argparse
import json
from pathlib import Path

from src.orchestrator.coordinator import Coordinator
from src.utils.schema import CaseInput


def _summary(result: dict) -> str:
    lines = []
    lines.append(f"Case {result['case_id']}  |  provider={result['provider']}  "
                 f"|  {result['total_elapsed_s']}s")
    lines.append("-" * 64)
    lines.append("Agents:")
    for r in result["agent_results"]:
        lines.append(f"  {r['agent']:<15} {r['status']:<9} {r['elapsed_s']:>6}s  "
                     f"({len(r['evidence'])} evidence)  {r['notes'][:60]}")
    lines.append("-" * 64)
    findings = result.get("dossier", {}).get("findings", [])
    lines.append(f"Ranked candidate findings ({len(findings)}):")
    for f in findings[:5]:
        lines.append(f"  #{f['rank']} {f.get('gene')} {f.get('variant') or ''} "
                     f"[{f.get('confidence')}]")
    if result.get("sources_unavailable"):
        lines.append(f"Sources unavailable: {', '.join(result['sources_unavailable'])}")
    lines.append(f"Dossier PDF: {result.get('pdf_path')}")
    lines.append(f"S3 destination: {result.get('s3_destination')}")
    lines.append("\nRESEARCH USE ONLY — not a diagnostic system, not medical advice.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Run the Navigator genome pilot on one case.")
    ap.add_argument("--case", required=True, help="Path to a case JSON file")
    ap.add_argument("--json", action="store_true", help="Print full JSON instead of a summary")
    args = ap.parse_args()

    data = json.loads(Path(args.case).read_text())
    case = CaseInput(**data)
    result = Coordinator().run(case)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(_summary(result))


if __name__ == "__main__":
    main()
