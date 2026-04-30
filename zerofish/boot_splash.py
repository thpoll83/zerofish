#!/usr/bin/env python3
"""Minimal early-boot splash: displays 'Booting...' on the e-ink screen.
Runs as a one-shot systemd service (zerofish-boot.service) before the main
zerofish.service, so the screen shows something useful during the ~30 s boot.
The main app will reinitialise the display when it starts.
"""
import sys
import os

# TP_lib lives next to this script; add its parent so 'from TP_lib import' works.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from TP_lib import epd2in13_V4
from PIL import Image, ImageDraw, ImageFont

# Font search order: Noto → DejaVu → built-in default
_FONT_PATHS = [
    '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
]
_FONT_SIZE = 18


def _load_font():
    for p in _FONT_PATHS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, _FONT_SIZE)
            except Exception:
                pass
    return ImageFont.load_default()


def main():
    epd = epd2in13_V4.EPD()
    epd.init(epd.FULL_UPDATE)

    # Landscape: PIL image is 250×122; getbuffer() rotates 270° internally.
    img  = Image.new('1', (250, 122), 255)
    draw = ImageDraw.Draw(img)
    font = _load_font()

    text = 'Booting…'   # 'Booting…'
    bb   = draw.textbbox((0, 0), text, font=font)
    tw   = bb[2] - bb[0]
    th   = bb[3] - bb[1]
    draw.text(
        (125 - tw // 2 - bb[0], 61 - th // 2 - bb[1]),
        text, font=font, fill=0,
    )

    epd.displayPartBaseImage(epd.getbuffer(img))
    epd.sleep()
    epd.Dev_exit()


if __name__ == '__main__':
    main()
