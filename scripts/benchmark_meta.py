#!/usr/bin/env python3
"""Meta Model API benchmark runner — with HARD PROOF of real Meta usage.

RESEARCH USE ONLY. Navigator Genome Pilot is a research tool; every output is a research
hypothesis with explicit uncertainty — never a diagnosis and never medical advice. This
script only measures the benchmark; it makes no clinical claim.

Why this exists
---------------
``benchmarks/score.py`` reports ``provider`` straight from ``config.settings`` and the
pipeline degrades gracefully when the model is unreachable (``complete_json`` returns
``{"_unavailable": True}``). So a run can show ``provider: meta`` and top-1/top-5 = 1.0
while EVERY real Meta call actually failed and the deterministic fallback carried it.

This runner closes that gap: it wraps the app's real ``MetaModelClient`` at runtime to
tally genuine completion calls (attempted / succeeded / failed), capture token usage from
``resp.usage`` when present, and measure latency — WITHOUT permanently altering core code.
It then runs the SAME scoring logic as ``benchmarks/score.py`` over all cases, snapshots
the counters per case, and applies a hard proof gate: if zero real Meta completions
succeeded, the run is reported as FAILED-TO-REACH-META, not a passing Meta benchmark.

Outputs (never overwrites the existing dev/prior run):
  * benchmarks/results/scores_meta.json
  * benchmarks/results/report_meta.md

Offline-safe: if the resolved provider is not ``meta`` or no key is present, it prints a
clear message and exits non-zero WITHOUT any network call. No secret is ever printed.

Exit codes: 0 = valid Meta run (real calls > 0); 1 = not configured for Meta;
            2 = ran but reached Meta zero times (invalid Meta benchmark).
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import settings  # noqa: E402


# --------------------------------------------------------------------------- #
# Runtime instrumentation of the app's real MetaModelClient (no core edits).
# --------------------------------------------------------------------------- #
class MetaCallMeter:
    """Tally real completion calls, token usage, and latency on MetaModelClient.

    Wraps:
      * ``_call``        -> attempted / succeeded / failed + wall-clock latency
      * ``_lazy_client`` -> wraps the OpenAI client's ``chat.completions.create`` so we
                            can read ``resp.usage`` (prompt/completion/total tokens).
    A completion "attempt" is one ``_call`` invocation (which internally may do bounded
    retries); it SUCCEEDS when it returns content and FAILS when it raises ModelUnavailable
    (the exact path that makes ``complete_json`` return the degraded ``_unavailable`` dict).
    """

    def __init__(self) -> None:
        self.attempted = 0
        self.succeeded = 0
        self.failed = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.usage_available = False
        self.latency_s = 0.0
        self.error_classes: dict[str, int] = {}
        self._orig_call = None
        self._orig_lazy = None

    def snapshot(self) -> dict:
        return {
            "attempted": self.attempted,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    def install(self) -> None:
        import src.models.meta_client as mc

        meter = self
        self._orig_call = mc.MetaModelClient._call
        self._orig_lazy = mc.MetaModelClient._lazy_client
        ModelUnavailable = mc.ModelUnavailable

        def wrapped_call(self_client, messages, temperature, json_mode):  # noqa: ANN001
            meter.attempted += 1
            t0 = time.monotonic()
            try:
                out = meter._orig_call(self_client, messages, temperature, json_mode)
                meter.succeeded += 1
                return out
            except ModelUnavailable as e:
                meter.failed += 1
                cls = type(e).__name__
                meter.error_classes[cls] = meter.error_classes.get(cls, 0) + 1
                raise
            except Exception as e:  # noqa: BLE001
                meter.failed += 1
                cls = type(e).__name__
                meter.error_classes[cls] = meter.error_classes.get(cls, 0) + 1
                raise
            finally:
                meter.latency_s += time.monotonic() - t0

        def wrapped_lazy(self_client):  # noqa: ANN001
            client = meter._orig_lazy(self_client)
            if not getattr(client, "_meter_wrapped", False):
                orig_create = client.chat.completions.create

                def wrapped_create(**kwargs):
                    resp = orig_create(**kwargs)
                    u = getattr(resp, "usage", None)
                    if u is not None:
                        meter.usage_available = True
                        meter.prompt_tokens += int(getattr(u, "prompt_tokens", 0) or 0)
                        meter.completion_tokens += int(getattr(u, "completion_tokens", 0) or 0)
                        meter.total_tokens += int(getattr(u, "total_tokens", 0) or 0)
                    return resp

                client.chat.completions.create = wrapped_create
                client._meter_wrapped = True
            return client

        mc.MetaModelClient._call = wrapped_call
        mc.MetaModelClient._lazy_client = wrapped_lazy

    def uninstall(self) -> None:
        import src.models.meta_client as mc

        if self._orig_call is not None:
            mc.MetaModelClient._call = self._orig_call
        if self._orig_lazy is not None:
            mc.MetaModelClient._lazy_client = self._orig_lazy


def main() -> int:  # noqa: C901
    prov = settings.active_provider()
    from src.models.config import model_for

    model_id = model_for("intake")  # all 8 agents map to the same text model

    print("=" * 70)
    print("  Meta Model API BENCHMARK — RESEARCH USE ONLY")
    print("=" * 70)
    print(f"  Provider resolved : {prov['name']}")
    print(f"  Base URL          : {prov['base_url']}")
    print(f"  Model id (agents) : {model_id}")
    print(f"  API key present   : {bool(prov['api_key'])}")
    print("-" * 70)

    if prov["name"] != "meta":
        print("  NOT routed to Meta (provider =", prov["name"], ").")
        print("  Set PROVIDER=meta / META_MODEL_API_KEY for this process and re-run.")
        return 1
    if not prov["api_key"]:
        print("  Provider is 'meta' but no API key is configured — cannot call. STOP.")
        return 1

    # Import scoring helpers + harness pieces (reuse score.py logic verbatim).
    from benchmarks import score as score_mod
    from src.orchestrator.coordinator import Coordinator
    from src.utils.schema import CaseInput

    cases_dir = REPO_ROOT / "benchmarks" / "cases"
    out_dir = REPO_ROOT / "benchmarks" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    answers = score_mod.load_answers(cases_dir)

    case_files = [f for f in sorted(cases_dir.glob("*.json")) if not f.name.startswith("_")]
    print(f"  Cases found       : {len(case_files)}")
    print("-" * 70)

    meter = MetaCallMeter()
    meter.install()
    per_case: dict[str, dict] = {}
    t_start = time.monotonic()
    try:
        coord = Coordinator()
        for cf in case_files:
            case = CaseInput(**json.loads(cf.read_text()))
            before = meter.snapshot()
            print(f"[meta-bench] running {case.case_id} ...", flush=True)
            try:
                result = coord.run(case, persist=False)
                sc = score_mod.score_case(result, answers.get(case.case_id, {}))
            except Exception as e:  # noqa: BLE001
                sc = {"top1": None, "top5": None, "error": f"{type(e).__name__}: {e}"}
            after = meter.snapshot()
            # Per-case real-Meta tally (diff of global counters).
            sc["meta_calls"] = {
                "attempted": after["attempted"] - before["attempted"],
                "succeeded": after["succeeded"] - before["succeeded"],
                "failed": after["failed"] - before["failed"],
            }
            if after["total_tokens"] or before["total_tokens"]:
                sc["meta_calls"]["total_tokens"] = after["total_tokens"] - before["total_tokens"]
            sc["agents_real_meta"] = sc["meta_calls"]["succeeded"]
            sc["agents_degraded"] = sc["meta_calls"]["failed"]
            per_case[case.case_id] = sc
    finally:
        meter.uninstall()

    total_wall = round(time.monotonic() - t_start, 3)

    # Aggregate scoring (same definition as score.py).
    scored = [c for c in per_case.values() if c.get("top1") is not None]
    n = len(scored)
    top1_rate = sum(1 for c in scored if c["top1"]) / n if n else 0.0
    top5_rate = sum(1 for c in scored if c["top5"]) / n if n else 0.0

    # Hard proof gate.
    real_ok = meter.succeeded > 0
    valid_meta_run = real_ok and n > 0
    expected_min = len(case_files)  # at least ~1 LLM agent per case if truly on Meta

    summary = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "provider": prov["name"],
        "model_id": model_id,
        "base_url": prov["base_url"],
        "valid_meta_run": valid_meta_run,
        "proof_gate": {
            "rule": "real Meta completions succeeded > 0",
            "passed": real_ok,
            "succeeded": meter.succeeded,
            "expected_min_if_meta": expected_min,
        },
        "n_cases": len(case_files),
        "n_scored": n,
        "top1_hit_rate": round(top1_rate, 3),
        "top5_hit_rate": round(top5_rate, 3),
        "meta_completions": {
            "attempted": meter.attempted,
            "succeeded": meter.succeeded,
            "failed": meter.failed,
            "error_classes": meter.error_classes,
        },
        "tokens": {
            "usage_reported_by_api": meter.usage_available,
            "prompt_tokens": meter.prompt_tokens,
            "completion_tokens": meter.completion_tokens,
            "total_tokens": meter.total_tokens,
        },
        "latency": {
            "total_model_latency_s": round(meter.latency_s, 3),
            "total_wall_clock_s": total_wall,
            "mean_model_latency_per_call_s": (
                round(meter.latency_s / meter.attempted, 3) if meter.attempted else None),
        },
        "per_case": per_case,
    }

    (out_dir / "scores_meta.json").write_text(json.dumps(summary, indent=2))
    _write_report(out_dir / "report_meta.md", summary)

    # Console summary.
    print("-" * 70)
    print(f"  Real Meta completions: attempted={meter.attempted} "
          f"succeeded={meter.succeeded} failed={meter.failed}")
    if meter.usage_available:
        print(f"  Tokens: prompt={meter.prompt_tokens} completion={meter.completion_tokens} "
              f"total={meter.total_tokens}")
    else:
        print("  Tokens: not reported by the API (usage object absent)")
    print(f"  Latency: model={round(meter.latency_s,1)}s wall={total_wall}s")
    print(f"  Scored {n}/{len(case_files)}  top1={top1_rate:.0%}  top5={top5_rate:.0%}")
    print("-" * 70)
    if valid_meta_run:
        print(f"  RESULT: VALID META RUN — genuinely executed on {model_id} "
              f"via the Meta Model API.")
        print(f"  Wrote: {out_dir/'scores_meta.json'}")
        print(f"         {out_dir/'report_meta.md'}")
        return 0
    print("  RESULT: FAILED-TO-REACH-META — zero real Meta completions succeeded.")
    print(f"  Error classes seen: {meter.error_classes or 'none captured'}")
    print("  This is NOT a valid Meta benchmark; the deterministic fallback carried it.")
    return 2


def _write_report(path: Path, s: dict) -> None:
    mc = s["meta_completions"]
    tok = s["tokens"]
    lat = s["latency"]
    verdict = ("**VALID META RUN** — this benchmark genuinely executed on "
               f"`{s['model_id']}` via the Meta Model API (`{s['base_url']}`)."
               if s["valid_meta_run"] else
               "**FAILED TO REACH META** — zero real Meta completions succeeded; the "
               "deterministic fallback carried the run. This is NOT a valid Meta benchmark.")
    lines = [
        "# Navigator Genome Pilot — Meta Model API Benchmark",
        "",
        "> **RESEARCH USE ONLY.** Every output is a research hypothesis with explicit "
        "uncertainty — not a diagnosis and not medical advice. This benchmark runs over "
        "published, already-solved public cases to measure the system's ability to "
        "re-derive the known causal gene; it is not a clinical validation.",
        "",
        f"_Generated: {s['generated']}_",
        "",
        "## Verdict",
        "",
        verdict,
        "",
        f"- Proof gate (`{s['proof_gate']['rule']}`): "
        f"**{'PASSED' if s['proof_gate']['passed'] else 'FAILED'}** "
        f"(succeeded = {s['proof_gate']['succeeded']}).",
        "",
        "## Provider & model",
        "",
        f"- Provider: **{s['provider']}**",
        f"- Model id: **{s['model_id']}**",
        f"- Base URL: `{s['base_url']}`",
        "",
        "## Real Meta completion calls (proof of genuine usage)",
        "",
        f"- Attempted: **{mc['attempted']}**",
        f"- Succeeded: **{mc['succeeded']}**",
        f"- Failed / degraded: **{mc['failed']}**",
        f"- Error classes: `{mc['error_classes'] or 'none'}`",
        "",
        "## Tokens",
        "",
        (f"- Usage reported by API: **{tok['usage_reported_by_api']}**"),
        f"- Prompt tokens: **{tok['prompt_tokens']}**",
        f"- Completion tokens: **{tok['completion_tokens']}**",
        f"- Total tokens: **{tok['total_tokens']}**",
        "",
        "## Latency",
        "",
        f"- Total model latency: **{lat['total_model_latency_s']} s**",
        f"- Total wall-clock: **{lat['total_wall_clock_s']} s**",
        f"- Mean per model call: **{lat['mean_model_latency_per_call_s']} s**",
        "",
        "## Aggregate score",
        "",
        f"- Cases scored: **{s['n_scored']} / {s['n_cases']}**",
        f"- Top-1 hit rate: **{s['top1_hit_rate']:.0%}**",
        f"- Top-5 hit rate: **{s['top5_hit_rate']:.0%}**",
        "",
        "## Per-case results",
        "",
        "| Case | Expected | Top-1 | Top-5 | Ranked (top 5) | Meta calls ✓/✗ | Sources unavailable |",
        "|------|----------|-------|-------|----------------|----------------|---------------------|",
    ]
    for cid, c in s["per_case"].items():
        mcalls = c.get("meta_calls", {})
        ok = mcalls.get("succeeded", 0)
        bad = mcalls.get("failed", 0)
        ranked = ", ".join(c.get("ranked_genes", []) or []) or c.get("error", "")
        src_un = ", ".join(c.get("sources_unavailable", []) or []) or "—"
        t1 = "✓" if c.get("top1") else "✗" if c.get("top1") is not None else "—"
        t5 = "✓" if c.get("top5") else "✗" if c.get("top5") is not None else "—"
        lines.append(f"| {cid} | {c.get('expected_gene','?')} | {t1} | {t5} | "
                     f"{ranked} | {ok}/{bad} | {src_un} |")
    lines += [
        "",
        "_\"Meta calls ✓/✗\" = real Meta completions that succeeded / failed (degraded to "
        "fallback) during that case. A valid Meta run requires ✓ > 0 overall._",
        "",
        "---",
        "",
        "_Navigator Genome Pilot is a research project. Outputs are hypotheses for research "
        "review, not clinical conclusions._",
    ]
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
