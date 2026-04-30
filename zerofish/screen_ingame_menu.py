from PIL import Image, ImageDraw
import ui

# Button order: 0=Resign  1=Board  (row 0)
#               2=Score Sheet  3=Time  (row 1)
IGMENU_BTN_LABELS = ['Resign', 'Board', 'Score Sheet', 'Time']
IGMENU_COLS    = 2
IGMENU_BTN_GAP = 4
IGMENU_X0      = 5
IGMENU_X1      = ui.VSEP_X - 5
IGMENU_BTN_W   = (IGMENU_X1 - IGMENU_X0 - IGMENU_BTN_GAP) // 2
IGMENU_BTN_H   = 46
_IGMENU_TOT_H  = 2 * IGMENU_BTN_H + IGMENU_BTN_GAP
IGMENU_Y0      = ui.TITLE_H + (ui.H - ui.TITLE_H - _IGMENU_TOT_H) // 2


def igmenu_rect(idx) -> tuple[int, int, int, int]:
    col = idx % IGMENU_COLS
    row = idx // IGMENU_COLS
    x0  = IGMENU_X0 + col * (IGMENU_BTN_W + IGMENU_BTN_GAP)
    y0  = IGMENU_Y0 + row * (IGMENU_BTN_H + IGMENU_BTN_GAP)
    return (x0, y0, x0 + IGMENU_BTN_W - 1, y0 + IGMENU_BTN_H - 1)


def build_ingame_menu_screen(move_label='') -> Image.Image:
    img  = Image.new('1', (ui.W, ui.H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts()
    ui.draw_chrome(draw, f, move_label or 'Menu', ok_active=True, ok_label='Back')
    for i, label in enumerate(IGMENU_BTN_LABELS):
        x0, y0, x1, y1 = igmenu_rect(i)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        draw.rectangle([(x0, y0), (x1, y1)], outline=0)
        ui.draw_centered(draw, cx, cy, label, f['btn'], 0)
    return img


def hit_igmenu(idx, lx, ly) -> bool:
    x0, y0, x1, y1 = igmenu_rect(idx)
    return x0 <= lx <= x1 and y0 <= ly <= y1
