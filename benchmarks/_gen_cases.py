"""One-off authoring helper: writes 12 additional solved-public-case JSONs + answer keys.

Every case is an ALREADY-SOLVED, PUBLISHED monogenic rare disease using the real causal
gene and a real, canonically documented pathogenic variant. The clinical pictures are
textbook presentations (HPO-mappable), NOT real patients. The known gene/variant is written
to _answers.json (hidden from agents; used only by the scorer).

Each case carries the rare causal variant (low allele_freq -> survives Filtering) plus one
common, real polymorphism (high allele_freq -> correctly dropped) so Filtering has real work.
Distractors are genuinely common benign variants, never implied to be causal.
"""
import json
from pathlib import Path

CASES = Path(__file__).parent / "cases"

# Common, real benign/population polymorphisms used purely as high-AF distractors.
MTHFR = {"gene": "MTHFR", "hgvs": "NM_005957.5:c.665C>T", "chrom": "1", "pos": 11796321,
         "ref": "C", "alt": "T", "rsid": "rs1801133", "allele_freq": 0.31}
HFE = {"gene": "HFE", "hgvs": "NM_000410.4:c.187C>G", "chrom": "6", "pos": 26090951,
       "ref": "C", "alt": "G", "rsid": "rs1799945", "allele_freq": 0.14}

CASES_DATA = [
    {
        "case_id": "DMD-DMD-R1577X",
        "disease": "Duchenne muscular dystrophy",
        "gene": "DMD",
        "clinical_summary": "Boy aged 4 with delayed motor milestones, frequent falls, difficulty "
            "climbing stairs, a positive Gowers sign, and calf pseudohypertrophy. Proximal lower-limb "
            "weakness and a waddling gait are noted. Serum creatine kinase is markedly elevated. "
            "A maternal uncle reportedly used a wheelchair from his teens.",
        "hpo_terms": ["motor delay", "proximal muscle weakness", "elevated creatine kinase",
                      "calf muscle pseudohypertrophy", "waddling gait"],
        "causal": {"gene": "DMD", "hgvs": "NM_004006.3:c.4729C>T", "chrom": "X", "pos": 32398435,
                   "ref": "G", "alt": "A", "allele_freq": 0.00001},
        "variant_label": "c.4729C>T (p.Arg1577Ter)",
    },
    {
        "case_id": "HEMA-F8-R2016W",
        "disease": "Hemophilia A",
        "gene": "F8",
        "clinical_summary": "Male infant with prolonged bleeding after circumcision and recurrent "
            "spontaneous joint bleeds (hemarthroses) with easy bruising. Coagulation studies show a "
            "prolonged activated partial thromboplastin time that corrects on mixing, with a markedly "
            "reduced factor VIII level. A maternal grandfather had a lifelong bleeding disorder.",
        "hpo_terms": ["prolonged bleeding after surgery", "joint hemorrhage", "bruising susceptibility",
                      "prolonged partial thromboplastin time"],
        "causal": {"gene": "F8", "hgvs": "NM_000132.4:c.6046C>T", "chrom": "X", "pos": 154930311,
                   "ref": "G", "alt": "A", "allele_freq": 0.00001},
        "variant_label": "c.6046C>T (p.Arg2016Trp)",
    },
    {
        "case_id": "TSD-HEXA-1278insTATC",
        "disease": "Tay-Sachs disease",
        "gene": "HEXA",
        "clinical_summary": "Infant of Ashkenazi Jewish ancestry, developing normally until ~6 months, "
            "then losing acquired motor skills with increasing hypotonia. An exaggerated startle "
            "response to sound is prominent, and fundoscopy shows a cherry-red spot at the macula. "
            "Progressive psychomotor regression follows.",
        "hpo_terms": ["developmental regression", "exaggerated startle response", "hypotonia",
                      "cherry red spot of the macula"],
        "causal": {"gene": "HEXA", "hgvs": "NM_000520.6:c.1274_1277dupTATC", "chrom": "15",
                   "pos": 72346580, "ref": "C", "alt": "CTATC", "allele_freq": 0.00005},
        "variant_label": "c.1274_1277dupTATC (p.Tyr427IlefsTer5)",
    },
    {
        "case_id": "SMA-SMN1-EX7DEL",
        "disease": "Spinal muscular atrophy type 1",
        "gene": "SMN1",
        "clinical_summary": "Floppy infant with severe generalized hypotonia, symmetric proximal "
            "weakness, absent deep tendon reflexes, tongue fasciculations, and a bell-shaped chest "
            "with paradoxical breathing. The infant is alert with preserved facial expression. "
            "Motor milestones are not achieved.",
        "hpo_terms": ["neonatal hypotonia", "areflexia", "tongue fasciculations", "muscle weakness"],
        "causal": {"gene": "SMN1", "hgvs": "NM_000344.4:c.840C>T (homozygous SMN1 exon 7 loss)",
                   "chrom": "5", "pos": 70951946, "ref": "C", "alt": "T", "allele_freq": 0.00002},
        "variant_label": "homozygous SMN1 exon 7 deletion (c.840C>T / gene conversion)",
    },
    {
        "case_id": "MFS-FBN1-C1170Y",
        "disease": "Marfan syndrome",
        "gene": "FBN1",
        "clinical_summary": "Tall, slender adolescent with long limbs, arachnodactyly (positive wrist "
            "and thumb signs), pectus excavatum, joint hypermobility, and high-arched palate. "
            "Ophthalmology documents ectopia lentis, and echocardiography shows aortic root dilation. "
            "A parent has a similar habitus and known aortic enlargement.",
        "hpo_terms": ["arachnodactyly", "ectopia lentis", "aortic root aneurysm", "tall stature",
                      "pectus excavatum"],
        "causal": {"gene": "FBN1", "hgvs": "NM_000138.5:c.3509G>A", "chrom": "15", "pos": 48479997,
                   "ref": "C", "alt": "T", "allele_freq": 0.00001},
        "variant_label": "c.3509G>A (p.Cys1170Tyr)",
    },
    {
        "case_id": "FH-LDLR-G592E",
        "disease": "Familial hypercholesterolemia",
        "gene": "LDLR",
        "clinical_summary": "Adult with markedly elevated LDL cholesterol resistant to diet, tendon "
            "xanthomas over the Achilles and knuckles, and corneal arcus at a young age. There is a "
            "strong family history of premature myocardial infarction affecting a parent and sibling "
            "before age 50.",
        "hpo_terms": ["hypercholesterolemia", "tendon xanthomatosis", "premature coronary artery disease",
                      "corneal arcus"],
        "causal": {"gene": "LDLR", "hgvs": "NM_000527.5:c.1775G>A", "chrom": "19", "pos": 11116926,
                   "ref": "G", "alt": "A", "allele_freq": 0.00008},
        "variant_label": "c.1775G>A (p.Gly592Glu)",
    },
    {
        "case_id": "RETT-MECP2-T158M",
        "disease": "Rett syndrome",
        "gene": "MECP2",
        "clinical_summary": "Girl with normal development until ~12 months, followed by regression with "
            "loss of purposeful hand use and spoken words. Prominent stereotypic hand-wringing "
            "movements appear, head circumference growth decelerates (acquired microcephaly), and gait "
            "becomes unsteady.",
        "hpo_terms": ["developmental regression", "stereotypic hand wringing", "acquired microcephaly",
                      "loss of speech", "gait disturbance"],
        "causal": {"gene": "MECP2", "hgvs": "NM_004992.4:c.473C>T", "chrom": "X", "pos": 154031326,
                   "ref": "G", "alt": "A", "allele_freq": 0.00001},
        "variant_label": "c.473C>T (p.Thr158Met)",
    },
    {
        "case_id": "HD-HTT-CAG-EXP",
        "disease": "Huntington disease",
        "gene": "HTT",
        "clinical_summary": "Adult in their 40s with progressive involuntary choreiform movements, "
            "deteriorating coordination, cognitive decline, and personality/behavioral change with "
            "irritability. A parent developed similar progressive movement and psychiatric symptoms in "
            "mid-life, consistent with autosomal dominant inheritance.",
        "hpo_terms": ["chorea", "progressive cognitive impairment", "personality changes",
                      "involuntary movements"],
        "causal": {"gene": "HTT", "hgvs": "NM_002111.8:c.52CAG[42] (expanded CAG repeat)", "chrom": "4",
                   "pos": 3074877, "ref": "CAG", "alt": "CAGCAG", "allele_freq": 0.00002},
        "variant_label": "expanded CAG trinucleotide repeat (~42) in HTT exon 1",
    },
    {
        "case_id": "POMPE-GAA-IVS1",
        "disease": "Pompe disease (late-onset)",
        "gene": "GAA",
        "clinical_summary": "Patient with progressive proximal limb-girdle weakness and prominent "
            "respiratory muscle involvement causing exertional dyspnea and orthopnea, with exercise "
            "intolerance. Serum creatine kinase is elevated. Muscle studies suggest a metabolic "
            "myopathy with glycogen accumulation.",
        "hpo_terms": ["proximal muscle weakness", "respiratory insufficiency", "elevated creatine kinase",
                      "exercise intolerance"],
        "causal": {"gene": "GAA", "hgvs": "NM_000152.5:c.-32-13T>G", "chrom": "17", "pos": 80101535,
                   "ref": "T", "alt": "G", "allele_freq": 0.0025},
        "variant_label": "c.-32-13T>G (common late-onset splice variant)",
    },
    {
        "case_id": "WILSON-ATP7B-H1069Q",
        "disease": "Wilson disease",
        "gene": "ATP7B",
        "clinical_summary": "Young adult with hepatic dysfunction and new neurological signs including "
            "tremor and dystonia, plus psychiatric changes. Slit-lamp examination reveals "
            "Kayser-Fleischer rings. Serum ceruloplasmin is low and 24-hour urinary copper excretion "
            "is markedly elevated.",
        "hpo_terms": ["Kayser-Fleischer ring", "tremor", "hepatic failure", "dystonia"],
        "causal": {"gene": "ATP7B", "hgvs": "NM_000053.4:c.3207C>A", "chrom": "13", "pos": 51934628,
                   "ref": "G", "alt": "T", "allele_freq": 0.0004},
        "variant_label": "c.3207C>A (p.His1069Gln)",
    },
    {
        "case_id": "HBOC-BRCA1-185delAG",
        "disease": "Hereditary breast and ovarian cancer syndrome",
        "gene": "BRCA1",
        "clinical_summary": "Woman with early-onset breast cancer and a striking multigenerational "
            "family history of breast and ovarian cancer on the same side, including a relative with "
            "bilateral breast cancer. Ancestry is Ashkenazi Jewish. Evaluated for a germline "
            "cancer-predisposition variant (research context, not clinical management).",
        "hpo_terms": ["breast carcinoma", "ovarian neoplasm", "neoplasm of the breast",
                      "family history of cancer"],
        "causal": {"gene": "BRCA1", "hgvs": "NM_007294.4:c.68_69delAG", "chrom": "17", "pos": 43124027,
                   "ref": "CTT", "alt": "C", "allele_freq": 0.0001},
        "variant_label": "c.68_69delAG (185delAG; p.Glu23ValfsTer17)",
    },
    {
        "case_id": "VHL-VHL-R167W",
        "disease": "Von Hippel-Lindau disease",
        "gene": "VHL",
        "clinical_summary": "Adult with retinal capillary hemangioblastomas and a cerebellar "
            "hemangioblastoma, plus a renal mass consistent with clear-cell renal cell carcinoma and "
            "episodic hypertension suggestive of pheochromocytoma. A parent had cerebellar and renal "
            "tumors, consistent with autosomal dominant inheritance.",
        "hpo_terms": ["retinal capillary hemangioma", "cerebellar hemangioblastoma",
                      "renal cell carcinoma", "pheochromocytoma"],
        "causal": {"gene": "VHL", "hgvs": "NM_000551.4:c.499C>T", "chrom": "3", "pos": 10146576,
                   "ref": "C", "alt": "T", "allele_freq": 0.00001},
        "variant_label": "c.499C>T (p.Arg167Trp)",
    },
]


def main():
    answers = json.loads((CASES / "_answers.json").read_text())
    distractors = [MTHFR, HFE]
    written = []
    for i, c in enumerate(CASES_DATA):
        distractor = dict(distractors[i % len(distractors)])
        case = {
            "case_id": c["case_id"],
            "clinical_summary": c["clinical_summary"],
            "hpo_terms": c["hpo_terms"],
            "variants": [c["causal"], distractor],
            "vcf_path": None,
        }
        fname = CASES / (c["case_id"].lower().replace("-", "_") + ".json")
        fname.write_text(json.dumps(case, indent=2) + "\n")
        answers[c["case_id"]] = {
            "disease": c["disease"],
            "gene": c["gene"],
            "variant": c["variant_label"],
            "accepted_genes": [c["gene"]],
        }
        written.append(fname.name)
    (CASES / "_answers.json").write_text(json.dumps(answers, indent=2) + "\n")
    print(f"Wrote {len(written)} case files:")
    for w in written:
        print("  ", w)
    print(f"_answers.json now has {len([k for k in answers if not k.startswith('_')])} answers")


if __name__ == "__main__":
    main()
