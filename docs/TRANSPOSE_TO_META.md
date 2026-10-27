# Transpose to Meta — exact checklist

This pilot runs NOW on a dev stand-in endpoint to prove the logic. Moving to the real Meta
Model API (and partner inference) is an **environment change, not a code change**. The model
client (`src/models/meta_client.py`) and resolver (`src/models/config.py`) already switch on
the presence of `META_MODEL_API_KEY`.


## STATUS (verified 2026-10-27)

Troy's Meta Model API key is obtained and **authenticates** against `https://api.meta.ai/v1`
(the default base URL below is correct — no override needed). `GET /models` returns the live
catalog; the real text model is **`muse-spark-1.3`** (the earlier placeholders `muse-spark` /
`muse-spark-open-1026` do not exist and have been corrected in `config/agents.yaml`).

The ONLY remaining blocker is **account billing**: chat completions currently return
`HTTP 402 billing_not_configured` ("a valid payment method must be on file"). Resolve at
`https://dev.meta.ai/billing/?team_id=1686951162950737`.

Two helper scripts automate the rest:
- `scripts/check_meta_billing.sh` — prints `READY` once a real call succeeds (billing fixed).
- `scripts/activate_meta.sh` — verifies billing, flips the live service to `PROVIDER=meta`,
  restarts it, and health-checks it. Then run `python3 -m benchmarks.score`.

## 1. The one required change

```bash
export META_MODEL_API_KEY=<your-meta-model-api-key>
```

That's it. With that set, `config/settings.py` resolves `PROVIDER=meta`, the client points at
the Meta Model API, and every agent's model name comes from `config/agents.yaml`.

## 2. Optional environment overrides

```bash
export META_MODEL_API_BASE_URL=https://api.meta.ai/v1   # VERIFIED correct 2026-10-27; no override needed
export META_MODEL_TEAM_ID=<your-team-id>                 # if the Meta API requires it
export META_DEFAULT_MODEL=muse-spark                     # fallback when an agent has no mapping
```

## 3. Model names (already mapped — verify against the live catalog)

`config/agents.yaml` maps each agent to a Meta model:

| Agent | Model (verified id) |
|-------|-------|
| all eight agents | `muse-spark-1.3` (latest text model confirmed in the live catalog) |

_Open-weight bonus (hypothesis, unverified): the `-contributor` variants may be the open-weight models; move the three high-volume agents to `muse-spark-1.3-contributor` once billing lets us test it — YAML only._

**Action:** confirm these exact model identifiers against the Meta Model API model list at
hackathon time and edit `config/agents.yaml` if the names differ. No code changes — only YAML.

## 4. Where the $150 Meta Model API credits plug in

- The credits are consumed by the Meta Model API calls the agents make once `META_MODEL_API_KEY`
  is set. Nothing else in the pipeline costs Meta credits.
- Per the event text blast: **apply for credits via the form, then add a credit card on the
  Billing page** so the free credits are actually applied, and optionally set a **Spend Limit**
  so you never exceed the $150 grant. Each participant claims their own credits.
- Cost control: the three highest-volume agents already use the **open-weight** model
  (`muse-spark-open-1026`). Keep them there to stretch credits and qualify for the
  "Best Build on Meta Open Weight Models" bonus.

## 5. Partner inference (Modal / Baseten) — optional

If you run an open-weight Meta model on Modal or Baseten instead of the hosted Meta API:

1. Deploy the model behind an OpenAI-compatible endpoint on Modal/Baseten.
2. Point the relevant agents at it by either:
   - setting `META_MODEL_API_BASE_URL` to the Modal/Baseten endpoint and `META_MODEL_API_KEY`
     to that service's key (whole pipeline), or
   - (finer control) extend `active_provider()` in `config/settings.py` with a third provider
     entry and map specific agents to it in `config/agents.yaml`.
3. Add `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` or `BASETEN_API_KEY` to `.env` (placeholders
   already in `.env.example`).

Because every agent goes through one OpenAI-compatible client, any OpenAI-compatible endpoint
works without touching agent code.

## 6. AWS backbone (production)

The dev demo runs on this VM. For production per the architecture:

1. Containerize (add a Dockerfile — see `infra/aws/README.md` TODO).
2. Run the coordinator + FastAPI app on EC2/ECS Fargate.
3. Create the S3 bucket and set `AWS_S3_BUCKET` + `AWS_REGION`; the Dossier Writer already
   computes the S3 destination (`s3://$AWS_S3_BUCKET/navigator/dossiers/...`) — wire the upload
   (boto3 `put_object`) where the PDF is rendered.
4. Store `META_MODEL_API_KEY` in AWS SSM Parameter Store / Secrets Manager, not in the repo.

## 7. Verify after the swap

```bash
python -m src.orchestrator.run --case benchmarks/cases/cystic_fibrosis.json   # provider should print "meta"
python -m benchmarks.score                                                    # re-check top-1/top-5
```

The summary line prints `provider=meta` once the key is set — that is your confirmation the
transpose worked.
