"""Offline unit tests for the genomic streaming data layer (Stages 02–06).

All tests are fully offline: no network, no LLM, no Meta credits. Network clients are
stubbed either via http monkeypatch (returns None -> clients report unavailable) or via
injected annotation stubs. Matches the existing tests/ style (plain pytest functions,
tmp_path, monkeypatch).
"""
from __future__ import annotations

import pytest

from src.utils.schema import CaseInput, Variant


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    # Every external HTTP call "unavailable" -> exercises graceful degradation.
    monkeypatch.setattr("src.utils.http.get_json", lambda *a, **k: None)
    monkeypatch.setattr("src.utils.http.post_json", lambda *a, **k: None)


# --------------------------------------------------------------------------- #
# Stage 02 — QC & hard filters
# --------------------------------------------------------------------------- #
def _row(chrom="7", pos=100, ref="A", alt="T", flt="PASS", info="AF=0.001",
         fmt=None, sample=None):
    cols = [chrom, str(pos), ".", ref, alt, ".", flt, info]
    if fmt is not None:
        cols += [fmt, sample]
    return "\t".join(cols)


def test_qc_filter_not_pass_dropped():
    from src.pipeline import qc
    stats = qc.QCStats()
    lines = [_row(flt="PASS"), _row(flt="LowQual"), _row(flt=".")]
    kept = list(qc.qc_filter_lines(lines, qc.QCThresholds(), stats=stats))
    assert len(kept) == 2            # PASS and '.' kept, LowQual dropped
    assert stats.reasons.get("filter_not_pass") == 1


def test_qc_missing_field_passes_through():
    """A variant with no DP/GQ fields must PASS even under strict thresholds."""
    from src.pipeline import qc
    thr = qc.QCThresholds.recommended()  # min_dp=10, min_gq=20
    # INFO-only row (no FORMAT/sample) -> DP/GQ absent -> must be kept
    kept = list(qc.qc_filter_lines([_row()], thr))
    assert len(kept) == 1


def test_qc_present_field_below_threshold_dropped():
    from src.pipeline import qc
    thr = qc.QCThresholds(require_pass=True, min_dp=10, min_gq=20)
    low = _row(fmt="GT:DP:GQ", sample="0/1:4:15")   # DP=4<10 -> drop
    good = _row(fmt="GT:DP:GQ", sample="0/1:30:50")  # ok
    stats = qc.QCStats()
    kept = list(qc.qc_filter_lines([low, good], thr, stats=stats))
    assert len(kept) == 1
    assert stats.reasons.get("low_dp") == 1


def test_qc_bed_mask(tmp_path):
    from src.pipeline import qc
    bed = tmp_path / "mask.bed"
    bed.write_text("7\t90\t110\n")  # 0-based half-open covers VCF pos 91..110
    mask = qc.BedMask.from_file(bed)
    assert mask.contains("7", 100) is True
    assert mask.contains("chr7", 100) is True   # chr-prefix normalized
    assert mask.contains("7", 200) is False
    kept = list(qc.qc_filter_lines([_row(pos=100), _row(pos=200)],
                                   qc.QCThresholds(), bed=mask))
    assert len(kept) == 1  # pos=100 masked out, pos=200 kept


# --------------------------------------------------------------------------- #
# Stage 03 — columnar store (Parquet)
# --------------------------------------------------------------------------- #
def _variants():
    return [
        Variant(gene="CFTR", hgvs="c.1", chrom="7", pos=117559590, ref="CTT",
                alt="C", allele_freq=0.0001,
                raw={"consequence": "frameshift_variant", "impact": "HIGH", "filter": "PASS"}),
        Variant(gene="MTHFR", hgvs="c.2", chrom="1", pos=11856378, ref="C",
                alt="T", allele_freq=0.3,
                raw={"consequence": "missense_variant", "impact": "MODERATE"}),
    ]


def test_store_roundtrip_partition_and_pushdown(tmp_path):
    store = pytest.importorskip("src.pipeline.store")
    if store.pyarrow_version() is None:
        pytest.skip("pyarrow not installed")
    root = store.write_variants(_variants(), "CASE1", base_dir=tmp_path)
    # partitioned by chrom -> hive-style subdirs exist
    assert (root / "chrom=7").exists() and (root / "chrom=1").exists()
    # column projection
    rows = store.read_variants("CASE1", base_dir=tmp_path, columns=["gene", "gnomad_af"])
    assert {r["gene"] for r in rows} == {"CFTR", "MTHFR"}
    # predicate push-down: chrom partition filter
    only7 = store.read_variants("CASE1", base_dir=tmp_path, chrom="7")
    assert len(only7) == 1 and only7[0]["gene"] == "CFTR"
    # predicate push-down: max gnomad_af
    rare = store.read_variants("CASE1", base_dir=tmp_path, max_gnomad_af=0.01)
    assert len(rare) == 1 and rare[0]["gene"] == "CFTR"


def test_store_as_objects(tmp_path):
    store = pytest.importorskip("src.pipeline.store")
    if store.pyarrow_version() is None:
        pytest.skip("pyarrow not installed")
    store.write_variants(_variants(), "CASE2", base_dir=tmp_path)
    objs = store.read_variants_as_objects("CASE2", base_dir=tmp_path, chrom="7")
    assert len(objs) == 1
    assert objs[0].gene == "CFTR"
    assert objs[0].raw.get("consequence") == "frameshift_variant"


# --------------------------------------------------------------------------- #
# Stage 04 — index (tabix region query + lookup maps)
# --------------------------------------------------------------------------- #
def test_lookup_maps():
    from src.pipeline import index
    vs = _variants()
    maps = index.build_lookup_maps(vs)
    assert maps["n"] == 2
    assert index.lookup_by_gene(maps, "CFTR") == [0]
    assert index.lookup_by_gene(maps, "NOPE") == []


def test_lookup_maps_persist(tmp_path):
    from src.pipeline import index
    vs = [Variant(gene="CFTR", rsid="rs123", chrom="7", pos=1)]
    maps = index.build_lookup_maps(vs)
    p = index.save_lookup_maps(maps, tmp_path / "maps.json")
    loaded = index.load_lookup_maps(p)
    assert index.lookup_by_rsid(loaded, "rs123") == 0


def test_tabix_region_query(tmp_path):
    index = pytest.importorskip("src.pipeline.index")
    try:
        import pysam  # noqa: F401
    except Exception:
        pytest.skip("pysam not available")
    lines = [
        "7\t117559590\t.\tCTT\tC\t.\tPASS\tAF=0.0001",
        "7\t117559600\t.\tA\tG\t.\tPASS\tAF=0.002",
        "1\t11856378\t.\tC\tT\t.\tPASS\tAF=0.3",
    ]
    vcf = index.write_sorted_vcf(lines, tmp_path / "x.vcf")
    gz = index.bgzip_and_tabix(vcf)
    hits = index.region_query(gz, "7", 117559585, 117559595)
    assert len(hits) == 1 and hits[0].split("\t")[1] == "117559590"
    # chr-prefix tolerance
    hits2 = index.region_query(gz, "chr7", 117559585, 117559605)
    assert len(hits2) == 2


# --------------------------------------------------------------------------- #
# Stage 05 — annotate (join) with stubbed clients
# --------------------------------------------------------------------------- #
def test_annotate_with_stub_sources():
    from src.pipeline import annotate
    def fake_mv(gene, term=None):
        if gene == "CFTR":
            return {"available": True, "hits": [
                {"rsid": None, "gnomad_af": 0.00005,
                 "clinical_significance": "Pathogenic", "hgvs": None}]}
        return {"available": False, "hits": []}
    def fake_cv(gene, term=None):
        return {"available": False, "present": False, "records": []}
    sources = annotate.AnnotationSources(myvariant_query=fake_mv, clinvar_query=fake_cv)
    v = Variant(gene="CFTR", chrom="7", pos=1, ref="A", alt="T")  # no allele_freq
    stats = annotate.AnnotationStats()
    annotate.annotate_variants([v], sources=sources,
                               phenotype_panel={"CFTR"}, stats=stats)
    assert v.raw["gnomad_af"] == 0.00005
    assert v.raw["clinvar"] == "Pathogenic"
    assert v.raw["phenotype_match"] is True
    assert stats.gnomad_af_filled == 1 and stats.clinvar_filled == 1


def test_annotate_degrades_offline():
    """With the real clients + http stubbed to None, annotation leaves columns null."""
    from src.pipeline import annotate
    v = Variant(gene="CFTR", chrom="7", pos=1, ref="A", alt="T")
    stats = annotate.AnnotationStats()
    annotate.annotate_variants([v], phenotype_panel=None, stats=stats)  # real clients
    assert v.raw.get("gnomad_af") is None
    assert v.raw.get("clinvar") is None
    assert stats.sources_unavailable  # noted as unavailable, no crash


# --------------------------------------------------------------------------- #
# Stage 06 — filter & rank (the GATE)
# --------------------------------------------------------------------------- #
def test_rank_rare_high_consequence_phenotype_outranks_common_benign():
    from src.pipeline import rank
    rare = Variant(gene="CFTR", chrom="7", pos=1, ref="A", alt="T", allele_freq=0.0001,
                   raw={"impact": "HIGH", "consequence": "frameshift_variant",
                        "phenotype_match": True, "clinvar": "Pathogenic"})
    common = Variant(gene="MTHFR", chrom="1", pos=2, ref="C", alt="T", allele_freq=0.3,
                     raw={"impact": "MODERATE", "consequence": "missense_variant",
                          "phenotype_match": False, "clinvar": "Benign"})
    ranked = rank.rank_candidates([common, rare])
    assert ranked[0].gene == "CFTR"
    assert ranked[1].gene == "MTHFR"
    # provenance recorded
    prov = ranked[0].raw["rank"]
    assert prov["score"] > ranked[1].raw["rank"]["score"]
    assert any("rare" in f for f in prov["filters_passed"])
    assert "phenotype gene-panel match" in prov["filters_passed"]


def test_rank_missing_af_not_penalized():
    from src.pipeline import rank
    v = Variant(gene="X", chrom="1", pos=1, raw={"impact": "HIGH",
                                                 "consequence": "stop_gained"})
    ranked = rank.rank_candidates([v])
    assert ranked[0].raw["rank"]["score"] > 0  # unknown AF neutral, severity positive


def test_rank_compound_het_flag():
    from src.pipeline import rank
    v1 = Variant(gene="ABC", chrom="2", pos=10, raw={"gt": "0/1", "impact": "MODERATE",
                                                     "consequence": "missense_variant"})
    v2 = Variant(gene="ABC", chrom="2", pos=20, raw={"gt": "0/1", "impact": "MODERATE",
                                                     "consequence": "missense_variant"})
    ranked = rank.rank_candidates([v1, v2])
    assert all("compound-heterozygous-consistent" in r.raw["rank"]["filters_passed"]
               for r in ranked)


def test_rank_drop_common_option():
    from src.pipeline import rank
    rare = Variant(gene="A", chrom="1", pos=1, allele_freq=0.0001,
                   raw={"impact": "HIGH", "consequence": "frameshift_variant"})
    common = Variant(gene="B", chrom="1", pos=2, allele_freq=0.5,
                     raw={"impact": "LOW", "consequence": "synonymous_variant"})
    ranked = rank.rank_candidates([rare, common], config=rank.RankConfig(drop_common=True))
    assert [v.gene for v in ranked] == ["A"]


# --------------------------------------------------------------------------- #
# Orchestration — chain 01→06 + opt-in gate
# --------------------------------------------------------------------------- #
def test_data_layer_run_demo_vcf():
    from src.pipeline import data_layer
    from src.pipeline.data_layer import DataLayerConfig
    case = CaseInput(case_id="DL-TEST", vcf_path="samples/sample_unknown.vcf",
                     clinical_summary="test", hpo_terms=["cough"])
    cfg = DataLayerConfig(phenotype_panel={"CFTR", "PAH"})
    res = data_layer.run(case, cfg)
    assert len(res.variants) == 3
    # the rare, high-consequence, phenotype-matching CFTR variant should rank first
    assert res.variants[0].gene == "CFTR"
    # the common MTHFR distractor should rank last
    assert res.variants[-1].gene == "MTHFR"
    assert res.qc_stats.kept == 3


def test_maybe_gate_off_by_default(monkeypatch):
    from src.pipeline import data_layer
    monkeypatch.setattr("config.settings.DATA_LAYER_GATE_ENABLED", False)
    case = CaseInput(case_id="G", vcf_path="samples/sample_unknown.vcf")
    out = data_layer.maybe_gate(case)
    assert out is case  # unchanged pass-through


def test_maybe_gate_on_returns_ranked(monkeypatch):
    from src.pipeline import data_layer
    monkeypatch.setattr("config.settings.DATA_LAYER_GATE_ENABLED", True)
    case = CaseInput(case_id="G2", vcf_path="samples/sample_unknown.vcf",
                     clinical_summary="test")
    out = data_layer.maybe_gate(case, data_layer.DataLayerConfig(phenotype_panel={"CFTR"}))
    assert out is not case
    assert out.vcf_path is None          # variants already parsed
    assert len(out.variants) == 3
    assert out.variants[0].gene == "CFTR"  # ranked
