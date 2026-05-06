"""Confirmation screen shown when the user taps End on the puzzle screen."""

from PIL import Image
import ui

_YES_W  = 90
_YES_H  = 52
_YES_X0 = (ui.VSEP_X - _YES_W) // 2
_YES_X1 = _YES_X0 + _YES_W
_YES_Y0 = ui.TITLE_H + 30
_YES_Y1 = _YES_Y0 + _YES_H
_TEXT_CY = ui.TITLE_H + 16

_YES_RECT = (_YES_X0, _YES_Y0, _YES_X1, _YES_Y1)


class PuzzleEndConfirmScreen(ui.Screen):
    name = 'puzzle_end_confirm'

    def __init__(self) -> None:
        self._yes_btn = ui.Button(_YES_RECT, 'Yes', ui.Button.FILLED)

    def build(self) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts
        ui.draw_chrome(draw, f, 'End puzzles?', ok_active=False, ok_label='No')
        ui.draw_centered(draw, ui.VSEP_X // 2, _TEXT_CY, 'Are you sure?', f['small'], 0)
        self._yes_btn.draw(draw, f['btn'])
        return img

    def hit(self, lx: int, ly: int) -> str | None:
        if self._yes_btn.hit(lx, ly):
            return 'yes'
        if ui.hit_ok(lx, ly):
            return 'no'
        return None


_screen = PuzzleEndConfirmScreen()


def build_puzzle_end_confirm_screen() -> Image.Image:
    return _screen.build()


def hit_puzzle_end_confirm(lx: int, ly: int) -> str | None:
    return _screen.hit(lx, ly)
