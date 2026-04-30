from PIL import Image, ImageDraw
import ui

BTN_MARGIN = 2
BTN_W      = 36
BTN_GAP    = 2
BTN_H      = 38
ROW1_Y     = ui.TITLE_H + 4
ROW2_Y     = ROW1_Y + BTN_H + 4


def diff_rect(level) -> tuple[int, int, int, int]:
    col = (level - 1) % 5
    y0  = ROW1_Y if level <= 5 else ROW2_Y
    x0  = BTN_MARGIN + col * (BTN_W + BTN_GAP)
    return (x0, y0, x0 + BTN_W - 1, y0 + BTN_H - 1)


def build_difficulty_screen(selected=None) -> Image.Image:
    img  = Image.new('1', (ui.W, ui.H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts('difficulty')
    ui.draw_chrome(draw, f, 'Select Difficulty', ok_active=(selected is not None))
    for lvl in range(1, 11):
        x0, y0, x1, y1 = diff_rect(lvl)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        if lvl == selected:
            draw.rectangle([(x0, y0), (x1, y1)], fill=0)
            ui.draw_centered(draw, cx, cy, str(lvl), f['btn'], 255)
        else:
            draw.rectangle([(x0, y0), (x1, y1)], outline=0)
            ui.draw_centered(draw, cx, cy, str(lvl), f['btn'], 0)
    return img


def hit_diff(level, lx, ly) -> bool:
    x0, y0, x1, y1 = diff_rect(level)
    return x0 <= lx <= x1 and y0 <= ly <= y1
