#!/usr/bin/env bash
# Idempotent deploy for Navigator Genome Pilot. Re-runnable after an image update.
set -euo pipefail
PROJ=/home/ubuntu/navigator-genome-pilot

# systemd unit (symlinked so restore points / image updates can re-link it)
sudo ln -sf "$PROJ/deploy/navigator.service" /etc/systemd/system/navigator.service
sudo systemctl daemon-reload
sudo systemctl enable --now navigator

# nginx vhost
sudo ln -sf "$PROJ/deploy/navigator-genome.conf" /etc/nginx/conf.d/navigator-genome.conf
sudo nginx -t && sudo systemctl reload nginx

echo "Deployed. Health:"
sleep 2
curl -s -H 'Host: navigator-genome.vm.internal' http://127.0.0.1/health || true
echo
