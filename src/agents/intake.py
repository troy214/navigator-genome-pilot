"""Agent 1 — Intake. Parse VCF / demo case and normalize variants.
Status: SCAFFOLD (Designed).
"""
from src.agents.base import BaseAgent
from src.utils.schema import CaseInput, AgentResult


class IntakeAgent(BaseAgent):
    name = "intake"
    model = "meta-models/muse-spark-open-1026"

    @property
    def system_prompt(self) -> str:
        return (
            "You normalize genomic variant inputs. Given a VCF excerpt or a structured demo "
            "case, return clean variant records (gene, HGVS, chrom/pos/ref/alt). Do not infer a "
            "diagnosis. If a field is missing, say so — never invent it."
        )

    def run(self, case: CaseInput, context: dict) -> AgentResult:
        # TODO: call self.client / src.pipeline.vcf to parse and normalize.
        return AgentResult(agent=self.name, notes="scaffold: not implemented",
                           payload={"variants": [v.model_dump() for v in case.variants]})
