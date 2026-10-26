"""HPO term lookup via the JAX ontology API (free, no key).

Used to VALIDATE phenotype terms the LLM extracts from the clinical summary against the
real Human Phenotype Ontology — so we return genuine HP:IDs + official labels, not
invented ones. Falls back to a small bundled subset when the API is unavailable.
"""
from __future__ import annotations

from src.utils import http

SEARCH = "https://ontology.jax.org/api/hp/search"

# Minimal offline fallback so the pipeline still maps common terms when the API is down.
_FALLBACK = {
    "cough": ("HP:0012735", "Cough"),
    "chronic cough": ("HP:0031246", "Chronic cough"),
    "recurrent respiratory infections": ("HP:0002205", "Recurrent respiratory infections"),
    "pancreatic insufficiency": ("HP:0001738", "Exocrine pancreatic insufficiency"),
    "failure to thrive": ("HP:0001508", "Failure to thrive"),
    "salty sweat": ("HP:0012236", "Increased sweat chloride"),
    "anemia": ("HP:0001903", "Anemia"),
    "hemolytic anemia": ("HP:0001878", "Hemolytic anemia"),
    "jaundice": ("HP:0000952", "Jaundice"),
    "pain crisis": ("HP:0032181", "Pain crisis"),
    "intellectual disability": ("HP:0001249", "Intellectual disability"),
    "seizures": ("HP:0001250", "Seizure"),
    "hepatomegaly": ("HP:0002240", "Hepatomegaly"),
    "splenomegaly": ("HP:0001744", "Splenomegaly"),
    "developmental regression": ("HP:0002376", "Developmental regression"),
    "cherry red spot": ("HP:0010729", "Cherry red spot of the macula"),
    "hypotonia": ("HP:0001252", "Hypotonia"),
}


def search_term(text: str, limit: int = 1) -> dict | None:
    """Return the best-matching real HPO term {"id","name"} or None."""
    data = http.get_json(SEARCH, namespace="hpo_search",
                         params={"q": text, "limit": limit})
    if data and data.get("terms"):
        t = data["terms"][0]
        return {"id": t["id"], "name": t["name"], "source": "HPO (JAX ontology API)"}
    key = text.strip().lower()
    if key in _FALLBACK:
        hp_id, name = _FALLBACK[key]
        return {"id": hp_id, "name": name, "source": "HPO (bundled offline subset)"}
    return None
