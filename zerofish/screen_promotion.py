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


class PromotionScreen(ui.Screen):
    name = 'promotion'

    def __init__(self) -> None:
        self._buttons = [
            ui.Button(promo_rect(i), glyph)
            for i, glyph in enumerate(PROMO_GLYPHS)
        ]

    def build(self, selected=None, move_label='') -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts
        ui.draw_chrome(draw, f, f'Promote {move_label}',
                       ok_active=(selected is not None))
        for i, btn in enumerate(self._buttons):
            btn.style = ui.Button.FILLED if i == selected else ui.Button.OUTLINE
            btn.draw(draw, f['promo'])
        return img

    def hit(self, lx: int, ly: int, selected=None) -> str | None:
        if ui.hit_ok(lx, ly) and selected is not None:
            return 'ok'
        for i, btn in enumerate(self._buttons):
            if btn.hit(lx, ly):
                return f'promo:{i}'
        return None


_screen = PromotionScreen()


def build_promotion_screen(selected=None, move_label='') -> Image.Image:
    return _screen.build(selected=selected, move_label=move_label)


def hit_promo(idx: int, lx: int, ly: int) -> bool:
    return _screen._buttons[idx].hit(lx, ly)
