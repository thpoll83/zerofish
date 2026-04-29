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
echo "--- Syncing Touch_e-Paper_Code ---"
${RSYNC} --delete \
    "${PROJECT_ROOT}/Touch_e-Paper_Code/" \
    "${REMOTE}:~/Touch_e-Paper_Code/"

echo ""
echo "--- Syncing zerofish app ---"
${RSYNC} --delete \
    "${PROJECT_ROOT}/zerofish/" \
    "${REMOTE}:~/zerofish/"

echo ""
echo "--- Syncing deploy scripts ---"
${RSYNC} \
    "${PROJECT_ROOT}/deploy/" \
    "${REMOTE}:~/deploy/"

echo ""
echo "=== Deploy complete ==="
echo "To run ZeroFish:"
echo "  ssh ${REMOTE} python3 ~/zerofish/main.py"
