"""Agent 1 — Intake. Parse VCF / demo case and normalize variants."""
from __future__ import annotations
from pathlib import Path

from src.agents.base import BaseAgent
from src.pipeline.vcf import parse_vcf
from src.utils.schema import CaseInput, AgentResult, Evidence, Variant, Confidence, Knowledge


class IntakeAgent(BaseAgent):
    name = "intake"

    @property
    def system_prompt(self) -> str:
        return (
            "You normalize genomic variant inputs. Given a VCF excerpt or a structured demo "
            "case, return clean variant records (gene, HGVS, chrom/pos/ref/alt). Do not infer a "
            "diagnosis. If a field is missing, say so — never invent it."
        )

    def _run(self, case: CaseInput, context: dict) -> AgentResult:
        variants: list[Variant] = list(case.variants)
        evidence: list[Evidence] = []
        notes = []

        # Merge any VCF-parsed variants with structured ones.
        if case.vcf_path:
            p = Path(case.vcf_path)
            if not p.is_absolute():
                from config import settings
                p = settings.ROOT / case.vcf_path
            if p.exists():
                parsed = parse_vcf(p)
                variants = parsed + variants
                notes.append(f"parsed {len(parsed)} variant(s) from VCF {p.name}")
                evidence.append(Evidence(
                    claim=f"Parsed {len(parsed)} variant record(s) from VCF file {p.name}.",
                    source=f"file:{p.name}", confidence=Confidence.HIGH,
                    knowledge=Knowledge.VERIFIED, agent=self.name))
            else:
                notes.append(f"VCF path not found: {case.vcf_path}")

        # Deduplicate by (chrom,pos,ref,alt) or gene+hgvs.
        seen = set()
        deduped = []
        for v in variants:
            key = (v.chrom, v.pos, v.ref, v.alt) if v.pos else (v.gene, v.hgvs)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(v)
            miss = [f for f in ("gene", "hgvs") if not getattr(v, f)]
            evidence.append(Evidence(
                claim=f"Normalized variant {v.short()}"
                      + (f"; missing field(s): {', '.join(miss)}" if miss else "; all key fields present"),
                source="intake:normalization",
                confidence=Confidence.HIGH if not miss else Confidence.MODERATE,
                knowledge=Knowledge.IMPLEMENTED, agent=self.name, gene=v.gene))

        notes.append(f"{len(deduped)} normalized variant(s)")
        return AgentResult(
            agent=self.name, status="done", evidence=evidence, notes="; ".join(notes),
            payload={"variants": [v.model_dump() for v in deduped]})
