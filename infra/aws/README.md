# AWS deployment (backbone)

AWS is the infrastructure backbone: orchestration, storage, the demo app, and dossier
storage. Agent inference runs on Meta models (Meta Model API / Modal / Baseten), not on AWS.

## Minimum pilot footprint

- **Compute:** one small EC2 (or ECS Fargate task) to run the coordinator + FastAPI demo app.
- **Storage:** one S3 bucket for generated evidence dossiers (PDF).
- **Secrets:** AWS SSM Parameter Store / Secrets Manager for the Meta Model API key — never in the repo.
- **Networking:** HTTPS via the existing reverse proxy pattern already used on Troy's servers.

## Notes

- Containerize early (the pilot HARD RULE): a Dockerfile makes EC2 -> ECS/Batch painless later.
- No Kubernetes / GPUs until the protocol is proven on the benchmark.
- Keep the orchestrator stateless; persist dossiers + scores to S3.

TODO: add Dockerfile, task definition / user-data, and an SSM parameter list.
