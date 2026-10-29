"""Stage 06 of the Navigator genomic streaming data layer: Filter & Rank (the GATE).

RESEARCH USE ONLY — part of a research tool for interpreting rare-disease genomes.
Outputs are ranked research hypotheses for researchers to review, NEVER a diagnosis and
never medical advice. Rank order reflects prioritization heuristics only.

This is the deterministic, non-LLM gate that decides which (tens–low hundreds of)
variants are worth an agent's attention, and in what order — BEFORE any agent runs.
It is fully explainable: every candidate records which filters it passed and which
factors drove its score (``raw["rank"] = {"score", "factors", "filters_passed"}``).

Scoring factors (each configurable in :class:`RankConfig`):
  * RARITY — rare variants score high; variants above ``max_af`` are penalized (or
    dropped if ``drop_common`` is set). Missing AF is treated as "unknown", scored
    neutrally (never penalized for a frequency we cannot see).
  * CONSEQUENCE SEVERITY — HIGH-impact / loss-of-function (frameshift, stop gained/lost,
    splice donor/acceptor, start lost) > MODERATE (missense, inframe indel) > LOW /
    synonymous / MODIFIER.
  * PHENOTYPE MATCH — variant's gene is in the case's phenotype gene panel
    (``raw["phenotype_match"]`` from Stage 05).
  * CLINICAL SIGNIFICANCE — a ClinVar "pathogenic"/"likely pathogenic" annotation adds
    weight; "benign"/"likely benign" subtracts (research signal only, not a verdict).
  * INHERITANCE MODEL — when genotype (and, ideally, trio) data is present: a compound-
    heterozygous pattern (≥2 heterozygous hits in the same gene) or a homozygous
    recessive hit adds weight; de-novo scoring activates only when parental genotypes
    are supplied (absent in the current demo inputs — documented, degrades to no-op).

Deterministic: identical input always yields identical order (stable tie-break on
score, then gene, then position).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable

from src.utils.schema import CaseInput, Variant

log = logging.getLogger("navigator.rank")


# --------------------------------------------------------------------------- #
# Consequence severity vocabulary
# --------------------------------------------------------------------------- #
_HIGH_TERMS = {
    "frameshift_variant", "stop_gained", "stop_lost", "start_lost",
    "splice_acceptor_variant", "splice_donor_variant", "transcript_ablation",
    "frameshift", "nonsense", "splice_acceptor", "splice_donor",
}
_MODERATE_TERMS = {
    "missense_variant", "inframe_insertion", "inframe_deletion",
    "protein_altering_variant", "missense", "inframe",
}
_LOW_TERMS = {
    "synonymous_variant", "splice_region_variant", "5_prime_utr_variant",
    "3_prime_utr_variant", "intron_variant", "synonymous",
}


def _severity(v: Variant) -> tuple[int, str]:
    """Map a variant's consequence/impact to (severity_level, label). 0=unknown."""
    impact = (v.raw.get("impact") or "").upper()
    if impact == "HIGH":
        return 3, "HIGH-impact"
    if impact == "MODERATE":
        return 2, "MODERATE-impact"
    if impact in ("LOW", "MODIFIER"):
        return 1, f"{impact}-impact"

    cons = (v.raw.get("consequence") or "").lower()
    if not cons:
        return 0, "unknown-consequence"
    terms = set(cons.replace("&", " ").replace(",", " ").split())
    if terms & _HIGH_TERMS:
        return 3, "loss-of-function"
    if terms & _MODERATE_TERMS:
        return 2, "missense/inframe"
    if terms & _LOW_TERMS:
        return 1, "low/synonymous"
    return 0, "unknown-consequence"


def _effective_af(v: Variant) -> float | None:
    af = v.raw.get("gnomad_af")
    if af is None:
        af = v.allele_freq
    try:
        return float(af) if af is not None else None
    except (TypeError, ValueError):
        return None


def _is_het(gt: str | None) -> bool:
    if not gt:
        return False
    alleles = gt.replace("|", "/").split("/")
    uniq = {a for a in alleles if a not in (".", "")}
    return len(uniq) > 1


def _is_hom_alt(gt: str | None) -> bool:
    if not gt:
        return False
    alleles = [a for a in gt.replace("|", "/").split("/") if a not in (".", "")]
    return len(alleles) >= 2 and len(set(alleles)) == 1 and alleles[0] not in ("0",)


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
@dataclass
class RankConfig:
    """Weights + thresholds for the ranking gate (all deterministic)."""
    max_af: float = 0.01            # AF at/below this is "rare" (matches Filtering agent)
    drop_common: bool = False       # if True, exclude AF>max_af entirely (else just penalize)

    w_rare: float = 3.0             # bonus for AF <= max_af
    w_af_unknown: float = 1.0       # neutral-ish bonus when AF unknown (don't over-reward)
    p_common: float = 4.0           # penalty for AF > max_af
    w_severity: float = 2.0         # multiplied by severity level (0..3)
    w_phenotype: float = 3.0        # bonus when gene in phenotype panel
    w_clinvar_path: float = 4.0     # bonus for (likely) pathogenic ClinVar
    p_clinvar_benign: float = 2.0   # penalty for (likely) benign ClinVar
    w_inheritance: float = 2.0      # bonus for comp-het / hom-recessive pattern

    max_candidates: int | None = None  # keep only the top N after ranking (None = all)


# --------------------------------------------------------------------------- #
# The gate
# --------------------------------------------------------------------------- #
def _clinvar_direction(v: Variant) -> int:
    sig = (v.raw.get("clinvar") or "").lower()
    if not sig:
        return 0
    if "pathogenic" in sig and "benign" not in sig:  # covers 'likely pathogenic'
        return 1
    if "benign" in sig:
        return -1
    return 0


def _inheritance_flags(variants: list[Variant]) -> dict[int, str]:
    """Return {variant_index: inheritance_note} for comp-het / hom-recessive patterns.

    Comp-het heuristic: a gene carrying ≥2 heterozygous variants. Hom-recessive: a
    homozygous-ALT genotype. Requires genotype data; silently empty without it.
    De-novo detection needs parental genotypes (trio) and is intentionally not
    inferred from a single sample.
    """
    flags: dict[int, str] = {}
    het_by_gene: dict[str, list[int]] = {}
    for i, v in enumerate(variants):
        gt = v.raw.get("gt")
        if _is_hom_alt(gt):
            flags[i] = "homozygous (recessive-consistent)"
        elif _is_het(gt) and v.gene:
            het_by_gene.setdefault(v.gene, []).append(i)
    for gene, idxs in het_by_gene.items():
        if len(idxs) >= 2:
            for i in idxs:
                flags.setdefault(i, "compound-heterozygous-consistent")
    return flags


def rank_candidates(variants: Iterable[Variant], case: CaseInput | None = None,
                    config: RankConfig | None = None) -> list[Variant]:
    """Score and rank variants; return a new list ordered best-first.

    Each returned Variant carries ``raw["rank"] = {"score", "factors", "filters_passed"}``
    for full provenance. Inputs are not mutated beyond their ``raw["rank"]`` stamp.
    Deterministic: equal scores break ties on (gene, chrom, pos).
    """
    config = config or RankConfig()
    variants = list(variants)
    inh = _inheritance_flags(variants)

    scored: list[tuple[float, Variant]] = []
    for i, v in enumerate(variants):
        score = 0.0
        factors: dict[str, float] = {}
        passed: list[str] = []

        # --- rarity ---
        af = _effective_af(v)
        if af is None:
            score += config.w_af_unknown
            factors["af_unknown"] = config.w_af_unknown
        elif af <= config.max_af:
            score += config.w_rare
            factors["rare"] = config.w_rare
            passed.append(f"rare (AF {af:.3g} <= {config.max_af})")
        else:
            score -= config.p_common
            factors["common_penalty"] = -config.p_common

        # --- consequence severity ---
        sev_level, sev_label = _severity(v)
        if sev_level:
            bump = config.w_severity * sev_level
            score += bump
            factors[f"severity:{sev_label}"] = bump
            if sev_level >= 2:
                passed.append(f"consequence {sev_label}")

        # --- phenotype match ---
        if v.raw.get("phenotype_match"):
            score += config.w_phenotype
            factors["phenotype_match"] = config.w_phenotype
            passed.append("phenotype gene-panel match")

        # --- clinical significance ---
        cvd = _clinvar_direction(v)
        if cvd > 0:
            score += config.w_clinvar_path
            factors["clinvar_pathogenic"] = config.w_clinvar_path
            passed.append(f"ClinVar: {v.raw.get('clinvar')}")
        elif cvd < 0:
            score -= config.p_clinvar_benign
            factors["clinvar_benign_penalty"] = -config.p_clinvar_benign

        # --- inheritance model ---
        if i in inh:
            score += config.w_inheritance
            factors[f"inheritance:{inh[i]}"] = config.w_inheritance
            passed.append(inh[i])

        v.raw["rank"] = {
            "score": round(score, 4),
            "factors": factors,
            "filters_passed": passed,
        }
        if config.drop_common and af is not None and af > config.max_af:
            continue  # excluded from the candidate set entirely
        scored.append((score, v))

    def _tie(v: Variant):
        return (v.gene or "~", v.chrom or "~", v.pos or 0)

    scored.sort(key=lambda sv: (-sv[0], _tie(sv[1])))
    ranked = [v for _, v in scored]
    if config.max_candidates is not None:
        ranked = ranked[: config.max_candidates]
    log.info("ranked %d candidate(s) (from %d input)", len(ranked), len(variants))
    return ranked
