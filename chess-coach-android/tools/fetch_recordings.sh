#!/bin/bash
# Fetch the native-resolution recordings (debug bundles, game videos, photos) from the private
# repo thpoll83/zerofish-recordings, which keeps them in Git LFS, and check every downloaded
# file against its MANIFEST.md.
#
# usage: tools/fetch_recordings.sh [DIR] [PATTERN...]
#   DIR      where the clone goes (default ../zerofish-recordings, next to the main repo)
#   PATTERN  which files to download, as Git LFS include patterns (default: all of them),
#            for example "videos/*" or "bundles/03-*"
#
# The game videos are read by the replay tests at 4 frames per second:
#   ffmpeg -i DIR/videos/video1-wooden-board-18-plies.mp4 -vf fps=4 -q:v 2 frames/f%04d.jpg
set -euo pipefail
DIR=${1:-../zerofish-recordings}
shift || true
INCLUDE=$(IFS=,; echo "${*:-*}")
if [ ! -d "$DIR/.git" ]; then
    GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/thpoll83/zerofish-recordings "$DIR"
fi
git -C "$DIR" lfs pull --include "$INCLUDE"
python3 - "$DIR" <<'PY'
import hashlib, os, re, sys
d = sys.argv[1]
ok = bad = skipped = 0
for line in open(os.path.join(d, "MANIFEST.md"), encoding="utf-8"):
    m = re.match(r"\| (\S+) \| (\d+) \| `([0-9a-f]{64})`", line)
    if not m:
        continue
    path, size, want = os.path.join(d, m.group(1)), int(m.group(2)), m.group(3)
    if not os.path.exists(path) or os.path.getsize(path) != size:
        skipped += 1  # not downloaded (still a Git LFS pointer)
        continue
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    if h.hexdigest() == want:
        ok += 1
    else:
        bad += 1
        print("checksum differs:", m.group(1))
print(f"{ok} files match MANIFEST.md, {bad} differ, {skipped} not downloaded")
sys.exit(1 if bad else 0)
PY
