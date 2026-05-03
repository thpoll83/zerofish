from PIL import Image, ImageDraw
import ui

COLORS        = ['White', 'Black', '?']
COLOR_BTN_GAP = 3
COLOR_BTN_W   = (ui.VSEP_X - 2 - 2 * COLOR_BTN_GAP) // 3
COLOR_BTN_H   = 55
COLOR_BTN_Y0  = ui.TITLE_H + (ui.H - ui.TITLE_H - COLOR_BTN_H) // 2
COLOR_BTN_Y1  = COLOR_BTN_Y0 + COLOR_BTN_H - 1
COLOR_BTN_X   = [2 + i * (COLOR_BTN_W + COLOR_BTN_GAP) for i in range(3)]


class ColorScreen(ui.Screen):
    name = 'color'

    def __init__(self) -> None:
        self._buttons = [
            ui.Button(
                (COLOR_BTN_X[i], COLOR_BTN_Y0,
                 COLOR_BTN_X[i] + COLOR_BTN_W - 1, COLOR_BTN_Y1),
                label,
            )
            for i, label in enumerate(COLORS)
        ]

    def build(self, selected=None) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts
        ui.draw_chrome(draw, f, 'Select Side',
                       ok_active=(selected is not None), sec_label='Back')
        for i, btn in enumerate(self._buttons):
            btn.style = ui.Button.FILLED if i == selected else ui.Button.OUTLINE
            btn.draw(draw, f['btn'])
        return img

    def hit(self, lx: int, ly: int, selected=None) -> str | None:
        if ui.hit_sec(lx, ly):
            return 'back'
        if ui.hit_ok(lx, ly, split=True) and selected is not None:
            return 'ok'
        for i, btn in enumerate(self._buttons):
            if btn.hit(lx, ly):
                return f'color:{i}'
        return None


_screen = ColorScreen()


def build_color_screen(selected=None) -> Image.Image:
    return _screen.build(selected=selected)


def hit_color(idx: int, lx: int, ly: int) -> bool:
    return _screen._buttons[idx].hit(lx, ly)
