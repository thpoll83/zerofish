from PIL import Image, ImageDraw
import ui
import config

SCORE_TITLE_H = 21
SCORE_ROW_H   = 13
SCORE_ROWS    = 15
SCORE_BACK_Y0 = config.SCORE_H - config.SCORE_BACK_H
SCORE_BACK_Y1 = config.SCORE_H - 1


def build_scoresheet_screen(move_history, move_label='') -> Image.Image:
    """Portrait image — raw SAN, no glyphs (unreadable at small size)."""
    img  = Image.new('1', (config.SCORE_W, config.SCORE_H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts()

    draw.rectangle([(0, 0), (config.SCORE_W - 1, SCORE_TITLE_H - 1)], fill=0)
    ui.draw_centered(draw, config.SCORE_W // 2, SCORE_TITLE_H // 2,
                     'Score Sheet', f['title'], 255)

    draw.rectangle([(2, SCORE_BACK_Y0), (config.SCORE_W - 3, SCORE_BACK_Y1)], outline=0)
    ui.draw_centered(draw, config.SCORE_W // 2, (SCORE_BACK_Y0 + SCORE_BACK_Y1) // 2,
                     'Back', f['btn'], 0)

    total = len(move_history)
    start = max(0, total - SCORE_ROWS * 2)
    if start % 2 == 1:
        start -= 1
    recent     = move_history[start:]
    start_full = start // 2 + 1

    y = SCORE_TITLE_H + 3
    for j in range(0, len(recent), 2):
        full_num = start_full + j // 2
        w = recent[j]     if j     < len(recent) else ''
        b = recent[j + 1] if j + 1 < len(recent) else ''
        draw.text((2, y), f'{full_num}. {w}  {b}', font=f['plain'], fill=0)
        y += SCORE_ROW_H
        if y >= SCORE_BACK_Y0 - 4:
            break

    return img


def hit_scoresheet_back(tx, ty) -> bool:
    return 0 <= tx <= config.SCORE_W - 1 and SCORE_BACK_Y0 <= ty <= SCORE_BACK_Y1
