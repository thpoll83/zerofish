from PIL import Image, ImageDraw
import ui

IGMENU_BTN_LABELS = ['Resign', 'Board', 'Score\nSheet', 'Time']
IGMENU_COLS    = 2
IGMENU_BTN_GAP = 4
IGMENU_X0      = 5
IGMENU_X1      = ui.VSEP_X - 5
IGMENU_BTN_W   = (IGMENU_X1 - IGMENU_X0 - IGMENU_BTN_GAP) // 2
IGMENU_BTN_H   = 46
_IGMENU_TOT_H  = 2 * IGMENU_BTN_H + IGMENU_BTN_GAP
IGMENU_Y0      = ui.TITLE_H + (ui.H - ui.TITLE_H - _IGMENU_TOT_H) // 2 + 2


def igmenu_rect(idx) -> tuple[int, int, int, int]:
    col = idx % IGMENU_COLS
    row = idx // IGMENU_COLS
    x0  = IGMENU_X0 + col * (IGMENU_BTN_W + IGMENU_BTN_GAP)
    y0  = IGMENU_Y0 + row * (IGMENU_BTN_H + IGMENU_BTN_GAP)
    return (x0, y0, x0 + IGMENU_BTN_W - 1, y0 + IGMENU_BTN_H - 1)


class InGameMenuScreen(ui.Screen):
    name = 'ingame_menu'

    def __init__(self) -> None:
        self._buttons = [
            ui.Button(igmenu_rect(i), label)
            for i, label in enumerate(IGMENU_BTN_LABELS)
        ]

    def build(self, move_label='') -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts
        ui.draw_chrome(draw, f, move_label or 'Menu', ok_active=True, ok_label='Back')
        for btn in self._buttons:
            btn.style = ui.Button.OUTLINE
            btn.draw(draw, f['btn'])
        return img

    def hit(self, lx: int, ly: int, **kw) -> str | None:
        if ui.hit_ok(lx, ly):
            return 'back'
        actions = ['resign', 'board', 'scoresheet', 'time']
        for i, btn in enumerate(self._buttons):
            if btn.hit(lx, ly):
                return actions[i]
        return None


_screen = InGameMenuScreen()


def build_ingame_menu_screen(move_label='') -> Image.Image:
    return _screen.build(move_label=move_label)


def hit_igmenu(idx: int, lx: int, ly: int) -> bool:
    return _screen._buttons[idx].hit(lx, ly)
