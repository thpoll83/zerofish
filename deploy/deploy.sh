#!/bin/bash
# Run this script FROM your development machine to copy the project to the RPi.
#
# Usage:
#   bash deploy/deploy.sh [rpi-host]
#
# Default host is 192.168.68.55 — override with the first argument, e.g.:
#   bash deploy/deploy.sh 192.168.1.42

set -e

RPI_HOST="${1:-192.168.68.55}"
RPI_USER="zero"
REMOTE="${RPI_USER}@${RPI_HOST}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

RSYNC="rsync -avz -e ssh"

echo "=== Deploying to ${REMOTE} ==="

echo ""
echo "--- Syncing zerofish app (includes TP_lib drivers) ---"
${RSYNC} --delete \
    "${PROJECT_ROOT}/zerofish/" \
    "${REMOTE}:~/zerofish/"

echo ""
echo "--- Syncing service files ---"
ssh "${REMOTE}" "mkdir -p ~/deploy"
${RSYNC} \
    "${PROJECT_ROOT}/deploy/zerofish.service" \
    "${PROJECT_ROOT}/deploy/zerofish-boot.service" \
    "${REMOTE}:~/deploy/"

echo ""
echo "--- Installing systemd services ---"
ssh "${REMOTE}" "sudo cp ~/deploy/zerofish.service /etc/systemd/system/zerofish.service \
    && sudo cp ~/deploy/zerofish-boot.service /etc/systemd/system/zerofish-boot.service \
    && sudo systemctl daemon-reload \
    && sudo systemctl enable zerofish zerofish-boot \
    && sudo systemctl restart zerofish-boot zerofish \
    && echo 'Services enabled and started'"

echo ""
echo "=== Deploy complete ==="
echo "Service status:  ssh ${REMOTE} systemctl status zerofish zerofish-boot"
echo "Live logs:       ssh ${REMOTE} journalctl -fu zerofish"
