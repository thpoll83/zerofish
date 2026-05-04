from PIL import Image, ImageDraw
import ui

_PIECE_GLYPHS = set('♔♕♖♗♘♙♚♛♜♝♞♟')


def disambig_rects(n) -> list[tuple[int, int, int, int]]:
    gap   = 8
    btn_w = min(70, (ui.VSEP_X - 10 - (n - 1) * gap) // n)
    btn_h = 50
    total = n * btn_w + (n - 1) * gap
    x0    = (ui.VSEP_X - total) // 2
    y0    = ui.TITLE_H + (ui.H - ui.TITLE_H - btn_h) // 2
    return [(x0 + i * (btn_w + gap), y0,
             x0 + i * (btn_w + gap) + btn_w - 1, y0 + btn_h - 1)
            for i in range(n)]


def _draw_label(draw, label, f, cx, cy, fill):
    """Render label: leading piece glyph in Merida (piece), rest in Noto (btn)."""
    if label and label[0] in _PIECE_GLYPHS:
        glyph, rest = label[0], label[1:]
        g_bb = draw.textbbox((0, 0), glyph, font=f['piece'])
        r_bb = draw.textbbox((0, 0), rest,  font=f['btn'])
        glyph_w = g_bb[2] - g_bb[0]
        rest_w  = r_bb[2] - r_bb[0]
        x0 = cx - (glyph_w + rest_w) // 2
        ascent_g = f['piece'].getmetrics()[0]
        ascent_r = f['btn'].getmetrics()[0]
        lh_g     = sum(f['piece'].getmetrics())
        baseline = cy - lh_g // 2 + ascent_g
        draw.text((x0 - g_bb[0],           baseline - ascent_g), glyph, font=f['piece'], fill=fill)
        draw.text((x0 + glyph_w - r_bb[0], baseline - ascent_r), rest,  font=f['btn'],   fill=fill)
    else:
        ui.draw_centered(draw, cx, cy, label, f['btn'], fill)


class DisambigScreen(ui.Screen):
    name = 'disambig'

    def build(self, labels, rects, selected=None, move_label='') -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts
        ui.draw_chrome(draw, f, f'Which? {move_label}',
                       ok_active=(selected is not None))
        for i, (label, rect) in enumerate(zip(labels, rects)):
            x0, y0, x1, y1 = rect
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            filled = (i == selected)
            coords = [(x0, y0), (x1, y1)]
            if filled:
                ui.draw_btn(draw, coords, fill=0)
                _draw_label(draw, label, f, cx, cy, 255)
            else:
                ui.draw_btn(draw, coords, outline=0)
                _draw_label(draw, label, f, cx, cy, 0)
        return img

    def hit(self, lx: int, ly: int, rects=None, selected=None) -> str | None:
        if ui.hit_ok(lx, ly) and selected is not None:
            return 'ok'
        if rects:
            for i, (x0, y0, x1, y1) in enumerate(rects):
                if x0 <= lx <= x1 and y0 <= ly <= y1:
                    return f'disambig:{i}'
        return None


_screen = DisambigScreen()


def build_disambig_screen(labels, rects, selected=None, move_label='') -> Image.Image:
    return _screen.build(labels, rects, selected=selected, move_label=move_label)


def hit_disambig(idx: int, rects: list, lx: int, ly: int) -> bool:
    x0, y0, x1, y1 = rects[idx]
    return x0 <= lx <= x1 and y0 <= ly <= y1
