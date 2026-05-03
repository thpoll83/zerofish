#!/bin/bash
# Run this script FROM your development machine to copy the project to the RPi.
#
# Usage:
#   bash deploy/deploy.sh [rpi-host]
#
# Default host is 192.168.68.55 — override with the first argument, e.g.:
#   bash deploy/deploy.sh 192.168.1.42

set -e

RPI_HOST="${1:-zerofish.local}"
RPI_USER="zero"
REMOTE="${RPI_USER}@${RPI_HOST}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

RSYNC="rsync -avz -e ssh"

echo "=== Deploying to ${REMOTE} ==="

echo ""
echo "--- Ensuring Chess Merida Unicode font is present ---"
FONTS_DIR="${PROJECT_ROOT}/zerofish/fonts"
MERIDA_TTF="${FONTS_DIR}/Chess_Merida_Unicode.ttf"
MERIDA_URL="https://raw.githubusercontent.com/xeyownt/chess_merida_unicode/master/chess_merida_unicode.ttf"
mkdir -p "${FONTS_DIR}"
if [ ! -f "${MERIDA_TTF}" ]; then
    echo "Downloading from ${MERIDA_URL} ..."
    curl -fSL "${MERIDA_URL}" -o "${MERIDA_TTF}" \
        && echo "Font saved to ${MERIDA_TTF}" \
        || { echo "WARNING: font download failed — chess glyphs will use DejaVu Sans fallback"; rm -f "${MERIDA_TTF}"; }
else
    echo "Already present: ${MERIDA_TTF}"
fi

echo ""
echo "--- Syncing zerofish app (includes TP_lib drivers) ---"
# --exclude=tests/ prevents the --delete sweep from removing ~/zerofish/tests/
# which is populated by the separate rsync step below.
${RSYNC} --delete --exclude=tests/ \
    "${PROJECT_ROOT}/zerofish/" \
    "${REMOTE}:~/zerofish/"

echo ""
echo "--- Syncing tests into ~/zerofish/tests/ ---"
# No --delete: on-device logs or ad-hoc scripts are preserved between syncs.
# Run the suite with: ssh ${REMOTE} 'cd ~/zerofish && pytest tests/rpi/ -v'
${RSYNC} \
    "${PROJECT_ROOT}/tests/" \
    "${REMOTE}:~/zerofish/tests/"
${RSYNC} \
    "${PROJECT_ROOT}/pytest.ini" \
    "${REMOTE}:~/zerofish/pytest.ini"

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
echo "RPi tests:       ssh ${REMOTE} 'cd ~/zerofish && pytest tests/rpi/ -v'"
