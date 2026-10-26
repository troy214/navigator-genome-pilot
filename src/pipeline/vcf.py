"""VCF intake + variant parsing.

Status: SCAFFOLD (Designed). Implement with pysam or a lightweight VCF reader.
Keep memory bounded — stream, do not load whole-genome VCFs into RAM.
"""
from __future__ import annotations
from pathlib import Path

from src.utils.schema import Variant


def parse_vcf(path: str | Path, max_variants: int = 10000) -> list[Variant]:
    """Parse a (small / already-filtered) VCF into Variant records.

    TODO: implement streaming parse. For the pilot, inputs are filtered candidate
    lists or demo cases — not raw whole-genome VCFs.
    """
    raise NotImplementedError("VCF parsing not yet implemented (scaffold).")
