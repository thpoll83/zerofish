from PIL import Image, ImageDraw
import ui


def disambig_rects(n) -> list[tuple[int, int, int, int]]:
    gap   = 8
    btn_w = min(70, (ui.VSEP_X - 10 - (n - 1) * gap) // n)
    btn_h = 50
    total = n * btn_w + (n - 1) * gap
    x0    = (ui.VSEP_X - total) // 2
    y0    = ui.TITLE_H + (ui.H - ui.TITLE_H - btn_h) // 2
    return [(x0 + i * (btn_w + gap), y0,
             x0 + i * (btn_w + gap) + btn_w - 1, y0 + btn_h - 1)
            for i in range(n)]


def build_disambig_screen(labels, rects, selected=None, move_label='') -> Image.Image:
    img  = Image.new('1', (ui.W, ui.H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts()
    ui.draw_chrome(draw, f, f'Which? {move_label}', ok_active=(selected is not None))
    for i, label in enumerate(labels):
        x0, y0, x1, y1 = rects[i]
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        if i == selected:
            draw.rectangle([(x0, y0), (x1, y1)], fill=0)
            ui.draw_centered(draw, cx, cy, label, f['piece'], 255)
        else:
            draw.rectangle([(x0, y0), (x1, y1)], outline=0)
            ui.draw_centered(draw, cx, cy, label, f['piece'], 0)
    return img


def hit_disambig(idx, rects, lx, ly) -> bool:
    x0, y0, x1, y1 = rects[idx]
    return x0 <= lx <= x1 and y0 <= ly <= y1
