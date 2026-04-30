import os
import subprocess
from PIL import Image, ImageDraw
import ui
import config

_LOGO_PATH      = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stockfish_logo.png')
_SPLASH_OK_Y0   = 6
_SPLASH_OK_Y1   = ui.H - 6
_SPLASH_LOGO_MAX = 65


def get_sf_info() -> tuple[str, str]:
    """Return (id_name, bitness) strings from the installed Stockfish binary."""
    name = 'Stockfish'
    bits = ''
    try:
        proc = subprocess.run(
            [config.STOCKFISH_PATH], input='uci\nquit\n',
            capture_output=True, text=True, timeout=5,
        )
        for line in proc.stdout.splitlines():
            if line.startswith('id name '):
                name = line.split('id name ', 1)[1].strip()
                break
    except Exception:
        pass
    try:
        proc = subprocess.run(
            ['file', config.STOCKFISH_PATH],
            capture_output=True, text=True, timeout=5,
        )
        out = proc.stdout.lower()
        if '64-bit' in out or 'aarch64' in out or 'x86-64' in out:
            bits = '64-bit'
        elif '32-bit' in out:
            bits = '32-bit'
    except Exception:
        pass
    return name, bits


def build_splash_screen(sf_info: tuple[str, str] | None = None) -> Image.Image:
    """Landscape splash: Stockfish logo on left, text centre, OK button right."""
    img  = Image.new('1', (ui.W, ui.H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts()

    if sf_info is None:
        sf_info = get_sf_info()
    sf_name, sf_bits = sf_info

    # Right panel — full-height OK button (no title bar)
    draw.line([(ui.VSEP_X, 0), (ui.VSEP_X, ui.H - 1)], fill=0)
    draw.rectangle([(ui.OK_X0, _SPLASH_OK_Y0), (ui.OK_X1, _SPLASH_OK_Y1)], fill=0)
    ok_cx = (ui.OK_X0 + ui.OK_X1) // 2
    ok_cy = (_SPLASH_OK_Y0 + _SPLASH_OK_Y1) // 2
    bb = draw.textbbox((0, 0), 'OK', font=f['ok'])
    draw.text(
        (ok_cx - (bb[2] - bb[0]) // 2 - bb[0],
         ok_cy - (bb[3] - bb[1]) // 2 - bb[1]),
        'OK', font=f['ok'], fill=255)

    # Logo
    logo_w = 0
    if os.path.exists(_LOGO_PATH):
        try:
            raw = Image.open(_LOGO_PATH).convert('RGBA')
            bg  = Image.new('RGBA', raw.size, (255, 255, 255, 255))
            bg.paste(raw, mask=raw.split()[3])
            grey = bg.convert('L')
            grey.thumbnail((_SPLASH_LOGO_MAX, ui.H - 4), Image.LANCZOS)
            logo_bw = grey.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
            lw, lh = logo_bw.size
            img.paste(logo_bw, (2, (ui.H - lh) // 2))
            logo_w = lw + 3
        except Exception:
            pass

    # Text block — centred in the space between logo and separator
    text_x  = 2 + logo_w
    area_w  = ui.VSEP_X - text_x - 2
    text_cx = text_x + area_w // 2

    lines = [
        ('ZeroFish', f['title']),
        ('powered by Stockfish', f['ver']),
        (sf_name,               f['ver']),
    ]
    if sf_bits:
        lines.append((sf_bits, f['ver']))

    gap = 3
    heights = [draw.textbbox((0, 0), t, font=fnt)[3] - draw.textbbox((0, 0), t, font=fnt)[1]
               for t, fnt in lines]
    total_h = sum(heights) + gap * (len(lines) - 1)
    y = (ui.H - total_h) // 2

    for (text, fnt), h in zip(lines, heights):
        bb = draw.textbbox((0, 0), text, font=fnt)
        tw = bb[2] - bb[0]
        draw.text((text_cx - tw // 2 - bb[0], y - bb[1]), text, font=fnt, fill=0)
        y += h + gap

    return img


def hit_splash_ok(lx: int, ly: int) -> bool:
    return ui.OK_X0 <= lx <= ui.OK_X1 and _SPLASH_OK_Y0 <= ly <= _SPLASH_OK_Y1
