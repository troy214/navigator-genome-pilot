"""CLI entry point: run the pilot on one case.

Usage:
    python -m src.orchestrator.run --case benchmarks/cases/demo_case.json

Status: SCAFFOLD (Designed).
"""
import argparse
import json
from pathlib import Path

from src.orchestrator.coordinator import Coordinator
from src.utils.schema import CaseInput


def main():
    ap = argparse.ArgumentParser(description="Run the Navigator genome pilot on one case.")
    ap.add_argument("--case", required=True, help="Path to a case JSON file")
    args = ap.parse_args()

    data = json.loads(Path(args.case).read_text())
    case = CaseInput(**data)

    result = Coordinator().run(case)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
