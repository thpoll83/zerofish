import time
from PIL import Image, ImageDraw
import ui


class TimeScreen(ui.Screen):
    name = 'time'

    def build(self, game_start: float, sf_time: float) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts
        ui.draw_chrome(draw, f, 'Game Time', ok_active=True, ok_label='Back')

        total    = time.time() - game_start if game_start else 0.0
        player_t = max(0.0, total - sf_time)

        def _fmt(secs: float) -> str:
            m, s = divmod(int(secs), 60)
            return f'{m}m {s:02d}s'

        rows = [
            ('You',       player_t),
            ('Stockfish', sf_time),
            ('Total',     total),
        ]
        area_h = ui.H - ui.TITLE_H
        row_h  = area_h // (len(rows) + 1)
        for i, (label, secs) in enumerate(rows):
            y = ui.TITLE_H + row_h * (i + 1)
            text = f'{label}:  {_fmt(secs)}'
            ascent, descent = f['plain_lg'].getmetrics()
            draw.text((6, y - (ascent + descent) // 2), text, font=f['plain_lg'], fill=0)
        return img

    def hit(self, lx: int, ly: int, **kw) -> str | None:
        if ui.hit_ok(lx, ly):
            return 'ok'
        return None


_screen = TimeScreen()


def build_time_screen(game_start: float, sf_time: float) -> Image.Image:
    return _screen.build(game_start, sf_time)
