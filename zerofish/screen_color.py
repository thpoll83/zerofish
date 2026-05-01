from PIL import Image, ImageDraw
import ui

COLORS        = ['White', 'Black', '?']
COLOR_BTN_GAP = 3
COLOR_BTN_W   = (ui.VSEP_X - 2 - 2 * COLOR_BTN_GAP) // 3
COLOR_BTN_H   = 55
COLOR_BTN_Y0  = ui.TITLE_H + (ui.H - ui.TITLE_H - COLOR_BTN_H) // 2
COLOR_BTN_Y1  = COLOR_BTN_Y0 + COLOR_BTN_H - 1
COLOR_BTN_X   = [2 + i * (COLOR_BTN_W + COLOR_BTN_GAP) for i in range(3)]


def build_color_screen(selected=None) -> Image.Image:
    img  = Image.new('1', (ui.W, ui.H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts('color')
    ui.draw_chrome(draw, f, 'Select Side', ok_active=(selected is not None),
                   sec_label='Back')
    for i, label in enumerate(COLORS):
        x0 = COLOR_BTN_X[i]
        x1 = x0 + COLOR_BTN_W - 1
        cx, cy = (x0 + x1) // 2, (COLOR_BTN_Y0 + COLOR_BTN_Y1) // 2
        if i == selected:
            ui.draw_btn(draw, [(x0, COLOR_BTN_Y0), (x1, COLOR_BTN_Y1)], fill=0)
            ui.draw_centered(draw, cx, cy, label, f['btn'], 255)
        else:
            ui.draw_btn(draw, [(x0, COLOR_BTN_Y0), (x1, COLOR_BTN_Y1)], outline=0)
            ui.draw_centered(draw, cx, cy, label, f['btn'], 0)
    return img


def hit_color(idx, lx, ly) -> bool:
    x0 = COLOR_BTN_X[idx]
    return x0 <= lx <= x0 + COLOR_BTN_W - 1 and COLOR_BTN_Y0 <= ly <= COLOR_BTN_Y1
