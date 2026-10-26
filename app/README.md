# Demo app

- `backend/main.py` — FastAPI: `/health`, `/run` (runs the 8-agent pilot on a case).
- `frontend/index.html` — the demo UI: **agent board** (a panel per agent), **evidence
  ledger**, and **dossier view**. This is the "panel per agent" design (not a monitor each).

## Run locally (scaffold)

```bash
uvicorn app.backend.main:app --reload --port 8000
# open app/frontend/index.html, or serve it from the backend later
```
