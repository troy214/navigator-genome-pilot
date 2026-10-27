#!/usr/bin/env bash
# Flip the Navigator pipeline (and live demo) from the dev endpoint to the Meta Model API.
# Run this ONLY after scripts/check_meta_billing.sh prints READY.
set -euo pipefail
cd "$(dirname "$0")/.."
echo ">> Verifying Meta billing is live..."
if ! ./scripts/check_meta_billing.sh | grep -q '^READY'; then
  echo "!! Meta billing is NOT ready yet. Resolve billing first; aborting." ; exit 1
fi
sed -i 's/^PROVIDER=.*/PROVIDER=meta/' deploy/navigator.env
cp deploy/navigator.env .env 2>/dev/null || true
echo ">> PROVIDER set to meta. Restarting service..."
sudo systemctl restart navigator
sleep 3
echo ">> Live /lab-data check:"
curl -s https://navigator-genome.abacusai.cloud/lab-data | python3 -c "import sys,json;d=json.load(sys.stdin);print('agents:',len(d.get('agents',[])),'top:',d.get('top_candidate'))"
echo ">> Done. Next: python3 -m benchmarks.score to re-run the benchmark on Meta models."
