from PIL import Image, ImageDraw
import ui

# Full-screen 2×2 grid — no right-panel separator needed
_MENU_LABELS = ['New\nGame', 'Cont', 'Puzzle', 'Back']

_MENU_GAP_X = 6
_MENU_GAP_Y = 6
_MENU_M_X   = 8   # horizontal margin
_MENU_M_Y   = 4   # vertical margin below title bar
_MENU_BTN_W = (ui.W - 2 * _MENU_M_X - _MENU_GAP_X) // 2          # = 114
_MENU_BTN_H = (ui.H - ui.TITLE_H - 2 * _MENU_M_Y - _MENU_GAP_Y) // 2  # ≈ 43
_MENU_Y0    = ui.TITLE_H + _MENU_M_Y


def _menu_rect(idx: int) -> tuple[int, int, int, int]:
    col = idx % 2
    row = idx // 2
    x0  = _MENU_M_X + col * (_MENU_BTN_W + _MENU_GAP_X)
    y0  = _MENU_Y0  + row * (_MENU_BTN_H + _MENU_GAP_Y)
    return (x0, y0, x0 + _MENU_BTN_W - 1, y0 + _MENU_BTN_H - 1)


class MainMenuScreen(ui.Screen):
    name = 'main_menu'

    def __init__(self) -> None:
        self._buttons = [
            ui.Button(_menu_rect(i), label, ui.Button.OUTLINE)
            for i, label in enumerate(_MENU_LABELS)
        ]

    def build(self, has_saves: bool = False) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts

        # Title bar
        draw.rectangle([(0, 0), (ui.W - 1, ui.TITLE_H - 1)], fill=0)
        draw.text((4, 3), 'ZeroFish', font=f['title'], fill=255)

        for i, btn in enumerate(self._buttons):
            # Grey out Cont when no saves by using OUTLINE (can't truly grey on 1-bit)
            btn.style = ui.Button.OUTLINE
            btn.draw(draw, f['btn'])

        return img

    def hit(self, lx: int, ly: int, **kw) -> str | None:
        actions = ['new_game', 'cont', 'puzzle', 'back']
        for i, btn in enumerate(self._buttons):
            if btn.hit(lx, ly):
                return actions[i]
        return None


_screen = MainMenuScreen()


def build_main_menu_screen(has_saves: bool = False) -> Image.Image:
    return _screen.build(has_saves=has_saves)


def hit_main_menu(lx: int, ly: int) -> str | None:
    return _screen.hit(lx, ly)
