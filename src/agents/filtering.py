"""Agent 2 — Filtering. Reduce candidate variants by frequency / quality heuristics."""
from __future__ import annotations

from src.agents.base import BaseAgent
from src.utils.schema import CaseInput, AgentResult, Evidence, Variant, Confidence, Knowledge

# Rare-disease causal variants are typically rare in the population.
MAX_AF = 0.01  # exclude common variants (AF > 1%)


class FilteringAgent(BaseAgent):
    name = "filtering"

    @property
    def system_prompt(self) -> str:
        return (
            "You filter candidate variants by population frequency and quality. Explain each "
            "exclusion. Do not rank for pathogenicity here — only reduce noise."
        )

    def _run(self, case: CaseInput, context: dict) -> AgentResult:
        variants = [Variant(**v) for v in context.get("intake", {}).get("variants", [])]
        if not variants:
            variants = list(case.variants)

        kept: list[Variant] = []
        evidence: list[Evidence] = []
        for v in variants:
            af = v.allele_freq
            if af is not None and af > MAX_AF:
                evidence.append(Evidence(
                    claim=f"Excluded {v.short()}: allele frequency {af:.4g} > {MAX_AF} "
                          f"(too common for a rare-disease candidate).",
                    source="filtering:population-frequency", confidence=Confidence.HIGH,
                    knowledge=Knowledge.IMPLEMENTED, agent=self.name, gene=v.gene))
                continue
            kept.append(v)
            freq_note = (f"AF {af:.4g} (rare)" if af is not None
                         else "no allele frequency provided — retained; frequency check deferred to Database agent")
            evidence.append(Evidence(
                claim=f"Retained {v.short()}: {freq_note}.",
                source="filtering:population-frequency",
                confidence=Confidence.MODERATE if af is None else Confidence.HIGH,
                knowledge=Knowledge.IMPLEMENTED if af is not None else Knowledge.UNKNOWN,
                agent=self.name, gene=v.gene))

        notes = f"kept {len(kept)}/{len(variants)} variant(s) after frequency/quality filtering"
        return AgentResult(
            agent=self.name, status="done", evidence=evidence, notes=notes,
            payload={"variants": [v.model_dump() for v in kept]})
