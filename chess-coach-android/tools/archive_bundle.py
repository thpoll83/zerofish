#!/usr/bin/env python3
"""Archive a debug bundle (the zip "Share debug bundle" makes) as a recorded game.

The log is kept whole. The camera frames are cropped to the board (the grid corners the log
prints for the frame, plus a margin, taller above because the far pieces stand there), scaled
down and saved as JPEG. Only the frames something was decided on are kept (learned, played,
tap, asked, undo, confirm). The offer frames are left out: they are taken while the hand is
still over the board. A frame that shows a person is dropped by listing its name in --skip.

usage: archive_bundle.py BUNDLE.zip OUT_DIR [--skip f00123_offer.jpg ...] [--max-side 720]
"""
import argparse, os, re, shutil, sys, tempfile, zipfile
import cv2

KEEP = {"learned", "played", "tap", "asked", "undo", "confirm"}


def grids(log_path):
    """frame number -> four corner points, from the 'grid x,y x,y x,y x,y' of the log lines."""
    out = {}
    for line in open(log_path, encoding="utf-8", errors="replace"):
        m = re.search(r" f(\d{5}) .*?grid ((?:-?\d+,-?\d+ ?){4})", line)
        if m:
            out[int(m.group(1))] = [tuple(map(int, p.split(","))) for p in m.group(2).split()]
    return out


def crop(img, pts, max_side):
    h, w = img.shape[:2]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    bw = max(xs) - min(xs); bh = max(ys) - min(ys)
    x0 = max(0, int(min(xs) - 0.02 * bw)); x1 = min(w, int(max(xs) + 0.02 * bw))
    y0 = max(0, int(min(ys) - 0.10 * bh)); y1 = min(h, int(max(ys) + 0.02 * bh))
    c = img[y0:y1, x0:x1]
    s = max_side / max(c.shape[:2])
    return cv2.resize(c, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle"); ap.add_argument("out")
    ap.add_argument("--skip", nargs="*", default=[])
    ap.add_argument("--max-side", type=int, default=720)
    a = ap.parse_args()
    tmp = tempfile.mkdtemp()
    with zipfile.ZipFile(a.bundle) as z:
        z.extractall(tmp)
    src = os.path.join(tmp, "debug") if os.path.isdir(os.path.join(tmp, "debug")) else tmp
    os.makedirs(os.path.join(a.out, "frames"), exist_ok=True)
    log = os.path.join(src, "log.txt")
    shutil.copy(log, os.path.join(a.out, "log.txt"))
    g = grids(log)
    known = sorted(g)
    kept = 0
    for name in sorted(os.listdir(src)):
        m = re.match(r"f(\d{5})_([a-z]+)\.(jpg|png)$", name)
        if not m or name in a.skip:
            continue
        n, tag = int(m.group(1)), m.group(2)
        if tag not in KEEP:
            continue
        before = [k for k in known if k <= n]
        pts = g.get(n) or (g[before[-1]] if before else None)
        if pts is None:
            continue
        img = cv2.imread(os.path.join(src, name))
        if img is None:
            continue
        cv2.imwrite(os.path.join(a.out, "frames", re.sub(r"\.png$", ".jpg", name)), crop(img, pts, a.max_side), [cv2.IMWRITE_JPEG_QUALITY, 72])
        kept += 1
    shutil.rmtree(tmp)
    print(f"{a.bundle}: log kept, {kept} frames")


if __name__ == "__main__":
    sys.exit(main())
