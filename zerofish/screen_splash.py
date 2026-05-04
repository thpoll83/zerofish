import os
import socket
import subprocess
from PIL import Image, ImageDraw
import ui
import config

_LOGO_PATH         = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stockfish_logo.png')
_SPLASH_OK_Y0      = 6
_SPLASH_OK_Y1_FULL = ui.H - 6
_SPLASH_MID_Y      = (_SPLASH_OK_Y0 + (ui.H - 6)) // 2   # = 61
_SPLASH_OK_Y1      = _SPLASH_MID_Y - 2                    # = 59
_SPLASH_SEC_Y0     = _SPLASH_MID_Y + 2                    # = 63
_SPLASH_SEC_Y1     = ui.H - 6                             # = 116
_SPLASH_LOGO_MAX   = 90

_OK_RECT_FULL  = (ui.OK_X0, _SPLASH_OK_Y0, ui.OK_X1, _SPLASH_OK_Y1_FULL)
_OK_RECT_SPLIT = (ui.OK_X0, _SPLASH_OK_Y0, ui.OK_X1, _SPLASH_OK_Y1)
_SEC_RECT      = (ui.OK_X0, _SPLASH_SEC_Y0, ui.OK_X1, _SPLASH_SEC_Y1)

# Module-level Button constants used for both drawing and hit-detection.
_OK_BTN_FULL  = ui.Button(_OK_RECT_FULL,  'OK',   ui.Button.BAR)
_OK_BTN_SPLIT = ui.Button(_OK_RECT_SPLIT, 'OK',   ui.Button.BAR)
_SEC_BTN      = ui.Button(_SEC_RECT,      'Cont', ui.Button.BAR)


def _wifi_ip() -> str:
    try:
        out = subprocess.run(['ip', '-4', 'addr', 'show', 'wlan0'],
                             capture_output=True, text=True, timeout=2).stdout
        for line in out.splitlines():
            line = line.strip()
            if line.startswith('inet '):
                return line.split()[1].split('/')[0]
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ''


def get_sf_info() -> tuple[str, str]:
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


class SplashScreen(ui.Screen):
    name = 'splash'

    def build(self, sf_info=None, has_resume: bool = False) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts

        if sf_info is None:
            sf_info = get_sf_info()
        sf_name, sf_bits = sf_info

        # Right panel — choose the appropriate OK button size
        ok_btn = _OK_BTN_SPLIT if has_resume else _OK_BTN_FULL
        draw.line([(ui.VSEP_X, 0), (ui.VSEP_X, ui.H - 1)], fill=0)
        ok_btn.draw(draw, f['ok'])
        if has_resume:
            _SEC_BTN.draw(draw, f['btn'])

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

        # Text block
        text_x  = 2 + logo_w
        area_w  = ui.VSEP_X - text_x - 2
        text_cx = text_x + area_w // 2

        lines = [
            ('ZeroFish', f['title']),
            (f'v{config.VERSION}', f['ver']),
            ('powered by', f['ver']),
            (sf_name, f['ver']),
        ]
        if sf_bits:
            lines.append((sf_bits, f['ver']))
        ip = _wifi_ip()
        if ip:
            lines.append((ip, f['ver']))

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

    def hit(self, lx: int, ly: int, has_resume: bool = False) -> str | None:
        if (_OK_BTN_SPLIT if has_resume else _OK_BTN_FULL).hit(lx, ly):
            return 'new_game'
        if has_resume and _SEC_BTN.hit(lx, ly):
            return 'resume'
        return None


_screen = SplashScreen()


def build_splash_screen(sf_info=None, has_resume: bool = False) -> Image.Image:
    return _screen.build(sf_info=sf_info, has_resume=has_resume)


def hit_splash_ok(lx: int, ly: int, has_resume: bool = False) -> bool:
    return (_OK_BTN_SPLIT if has_resume else _OK_BTN_FULL).hit(lx, ly)


def hit_splash_resume(lx: int, ly: int) -> bool:
    return _SEC_BTN.hit(lx, ly)
