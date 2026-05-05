import os
import socket
import subprocess
from PIL import Image, ImageDraw
import ui
import config

_LOGO_PATH    = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stockfish_logo.png')
_SPLASH_OK_Y0 = 6
_SPLASH_OK_Y1 = ui.H - 6

_OK_RECT = (ui.OK_X0, _SPLASH_OK_Y0, ui.OK_X1, _SPLASH_OK_Y1)
_OK_BTN  = ui.Button(_OK_RECT, 'OK', ui.Button.BAR)

_SPLASH_LOGO_MAX = 90


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

    def build(self, sf_info=None) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts

        # Right panel — only drawn once SF info is available
        if sf_info is not None:
            sf_name, sf_bits = sf_info
            draw.line([(ui.VSEP_X, 0), (ui.VSEP_X, ui.H - 1)], fill=0)
            _OK_BTN.draw(draw, f['ok'])
        else:
            sf_name = sf_bits = None

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

        lines = [('ZeroFish', f['title'])]
        if sf_name is not None:
            lines += [
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

    def hit(self, lx: int, ly: int) -> str | None:
        if _OK_BTN.hit(lx, ly):
            return 'ok'
        return None


_screen = SplashScreen()


def build_splash_screen(sf_info=None, **_kw) -> Image.Image:
    return _screen.build(sf_info=sf_info)


def hit_splash_ok(lx: int, ly: int, **_kw) -> bool:
    return _OK_BTN.hit(lx, ly)
