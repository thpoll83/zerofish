"""Puzzle loading screen: displayed while puzzles are downloaded in the background."""

from PIL import Image
import ui

_RX0 = ui.OK_X0
_RX1 = ui.OK_X1
_RCX = (_RX0 + _RX1) // 2

_HDR_H    = 36
_HDR_CY1  = _HDR_H // 4        # 9
_HDR_CY2  = _HDR_H * 3 // 4   # 27

_BTN_Y_BACK = (_HDR_H + 4,  _HDR_H + 4 + 24)   # (40, 64)
_BTN_Y_PLAY = (_HDR_H + 32, _HDR_H + 32 + 24)  # (68, 92)

_BACK_BTN = ui.Button((_RX0, _BTN_Y_BACK[0], _RX1, _BTN_Y_BACK[1]), 'Back', ui.Button.BAR)
_PLAY_BTN = ui.Button((_RX0, _BTN_Y_PLAY[0], _RX1, _BTN_Y_PLAY[1]), 'Play', ui.Button.OUTLINE)


class PuzzleLoadingScreen(ui.Screen):
    name = 'puzzle_loading'

    def build(self, has_existing: bool = False,
              rows_scanned: int = 0, found: int = 0) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts

        draw.line([(ui.VSEP_X, 0), (ui.VSEP_X, ui.H - 1)], fill=0)
        draw.rectangle([(ui.VSEP_X, 0), (ui.W - 1, _HDR_H - 1)], fill=0)
        ui.draw_centered(draw, _RCX, _HDR_CY1, 'Puzzles', f['title'], 255)
        ui.draw_centered(draw, _RCX, _HDR_CY2, 'Loading', f['title'], 255)

        _BACK_BTN.draw(draw, f['btn'])
        if has_existing:
            _PLAY_BTN.draw(draw, f['btn'])

        sf = f['small']
        cx = ui.VSEP_X // 2
        ui.draw_centered(draw, cx, 28, 'Downloading', sf, 0)
        ui.draw_centered(draw, cx, 44, 'puzzles...', sf, 0)
        if rows_scanned > 0:
            ui.draw_centered(draw, cx, 64, f'{rows_scanned // 1000}k rows', sf, 0)
            ui.draw_centered(draw, cx, 80, f'{found} found', sf, 0)

        return img

    def hit(self, lx: int, ly: int, has_existing: bool = False) -> str | None:
        if _BACK_BTN.hit(lx, ly):
            return 'back'
        if has_existing and _PLAY_BTN.hit(lx, ly):
            return 'play'
        return None


_screen = PuzzleLoadingScreen()


def build_puzzle_loading_screen(has_existing: bool = False,
                                 rows_scanned: int = 0,
                                 found: int = 0) -> Image.Image:
    return _screen.build(has_existing, rows_scanned, found)


def hit_puzzle_loading(lx: int, ly: int, has_existing: bool = False) -> str | None:
    return _screen.hit(lx, ly, has_existing)
