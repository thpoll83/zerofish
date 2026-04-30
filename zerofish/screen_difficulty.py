from PIL import Image, ImageDraw
import ui
import config

_COLS        = 5
_ROWS        = 3
_BTN_MARGIN  = 2
_BTN_GAP     = 2
_BTN_W       = (ui.VSEP_X - 2 * _BTN_MARGIN - (_COLS - 1) * _BTN_GAP) // _COLS  # ≈ 36
_BTN_H       = 30
_ROW_GAP     = 2
_CONTENT_H   = ui.H - ui.TITLE_H
_BLOCK_H     = _ROWS * _BTN_H + (_ROWS - 1) * _ROW_GAP
_TOP_MARGIN  = ((_CONTENT_H - _BLOCK_H) // 2)
_ROW_Y       = [
    ui.TITLE_H + _TOP_MARGIN + r * (_BTN_H + _ROW_GAP)
    for r in range(_ROWS)
]


def diff_rect(level) -> tuple[int, int, int, int]:
    col = (level - 1) % _COLS
    row = (level - 1) // _COLS
    x0  = _BTN_MARGIN + col * (_BTN_W + _BTN_GAP)
    y0  = _ROW_Y[row]
    return (x0, y0, x0 + _BTN_W - 1, y0 + _BTN_H - 1)


def build_difficulty_screen(selected=None) -> Image.Image:
    img  = Image.new('1', (ui.W, ui.H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts('difficulty')
    ui.draw_chrome(draw, f, 'Difficulty', ok_active=(selected is not None))
    for lvl in range(1, 16):
        x0, y0, x1, y1 = diff_rect(lvl)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        label  = config.DIFF_LABELS.get(lvl, str(lvl))
        if lvl == selected:
            draw.rectangle([(x0, y0), (x1, y1)], fill=0)
            ui.draw_centered(draw, cx, cy, label, f['btn'], 255)
        else:
            draw.rectangle([(x0, y0), (x1, y1)], outline=0)
            ui.draw_centered(draw, cx, cy, label, f['btn'], 0)
    return img


def hit_diff(level, lx, ly) -> bool:
    x0, y0, x1, y1 = diff_rect(level)
    return x0 <= lx <= x1 and y0 <= ly <= y1
