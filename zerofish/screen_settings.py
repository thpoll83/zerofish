"""Settings screen: Wifi and Back buttons."""

from PIL import Image, ImageDraw
import ui

_BTN_W = ui.VSEP_X - 24   # left-panel button width (margin of 12 each side)
_BTN_H = 34
_BTN_CX = ui.VSEP_X // 2
_BTN_CY = (ui.TITLE_H + ui.H) // 2


class SettingsScreen(ui.Screen):
    name = 'settings'

    def __init__(self) -> None:
        x0 = _BTN_CX - _BTN_W // 2
        y0 = _BTN_CY - _BTN_H // 2
        self._wifi_btn = ui.Button(
            (x0, y0, x0 + _BTN_W - 1, y0 + _BTN_H - 1),
            'Wifi', ui.Button.OUTLINE,
        )

    def build(self) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts
        ui.draw_chrome(draw, f, 'Settings', ok_active=True, ok_label='Back')
        self._wifi_btn.draw(draw, f['btn'])
        return img

    def hit(self, lx: int, ly: int, **kw) -> str | None:
        if self._wifi_btn.hit(lx, ly):
            return 'wifi'
        if ui.hit_ok(lx, ly):
            return 'back'
        return None


_screen = SettingsScreen()


def build_settings_screen() -> Image.Image:
    return _screen.build()


def hit_settings(lx: int, ly: int) -> str | None:
    return _screen.hit(lx, ly)
