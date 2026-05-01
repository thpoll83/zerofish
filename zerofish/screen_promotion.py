import chess
from PIL import Image, ImageDraw
import ui

PROMO_GLYPHS      = ['♞', '♝', '♜', '♛']
PROMO_PIECE_TYPES = [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]

PROMO_BTN_W   = 40
PROMO_BTN_H   = 60
PROMO_BTN_GAP = 4
_PROMO_TOT_W  = 4 * PROMO_BTN_W + 3 * PROMO_BTN_GAP
PROMO_BTN_X0  = (ui.VSEP_X - _PROMO_TOT_W) // 2
PROMO_BTN_Y0  = ui.TITLE_H + (ui.H - ui.TITLE_H - PROMO_BTN_H) // 2
PROMO_BTN_Y1  = PROMO_BTN_Y0 + PROMO_BTN_H - 1


def promo_rect(idx) -> tuple[int, int, int, int]:
    x0 = PROMO_BTN_X0 + idx * (PROMO_BTN_W + PROMO_BTN_GAP)
    return (x0, PROMO_BTN_Y0, x0 + PROMO_BTN_W - 1, PROMO_BTN_Y1)


def build_promotion_screen(selected=None, move_label='') -> Image.Image:
    img  = Image.new('1', (ui.W, ui.H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts('promotion')
    ui.draw_chrome(draw, f, f'Promote {move_label}', ok_active=(selected is not None))
    for i, glyph in enumerate(PROMO_GLYPHS):
        x0, y0, x1, y1 = promo_rect(i)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        if i == selected:
            ui.draw_btn(draw, [(x0, y0), (x1, y1)], fill=0)
            ui.draw_centered(draw, cx, cy, glyph, f['promo'], 255)
        else:
            ui.draw_btn(draw, [(x0, y0), (x1, y1)], outline=0)
            ui.draw_centered(draw, cx, cy, glyph, f['promo'], 0)
    return img


def hit_promo(idx, lx, ly) -> bool:
    x0, y0, x1, y1 = promo_rect(idx)
    return x0 <= lx <= x1 and y0 <= ly <= y1
