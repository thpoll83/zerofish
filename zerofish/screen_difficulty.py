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


class DifficultyScreen(ui.Screen):
    name = 'difficulty'

    def __init__(self) -> None:
        self._buttons = [
            ui.Button(diff_rect(lvl), config.DIFF_LABELS.get(lvl, str(lvl)))
            for lvl in range(1, 16)
        ]

    def build(self, selected=None) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts
        ui.draw_chrome(draw, f, 'Difficulty',
                       ok_active=(selected is not None), sec_label='Back')
        for i, btn in enumerate(self._buttons):
            lvl = i + 1
            btn.style = ui.Button.FILLED if lvl == selected else ui.Button.OUTLINE
            btn.draw(draw, f['btn_diff'])
        return img

    def hit(self, lx: int, ly: int, selected=None) -> str | None:
        if ui.hit_sec(lx, ly):
            return 'back'
        if ui.hit_ok(lx, ly, split=True) and selected is not None:
            return 'ok'
        for i, btn in enumerate(self._buttons):
            if btn.hit(lx, ly):
                return f'diff:{i + 1}'
        return None


_screen = DifficultyScreen()


def build_difficulty_screen(selected=None) -> Image.Image:
    return _screen.build(selected=selected)


def hit_diff(level: int, lx: int, ly: int) -> bool:
    return _screen._buttons[level - 1].hit(lx, ly)
