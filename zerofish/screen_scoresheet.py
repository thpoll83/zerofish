from PIL import Image, ImageDraw
import ui
import config

SCORE_TITLE_H = 21
SCORE_ROW_H   = 13
SCORE_ROWS    = 15
SCORE_BACK_Y0 = config.SCORE_H - config.SCORE_BACK_H
SCORE_BACK_Y1 = config.SCORE_H - 1
SCORE_MORE_X0 = config.SCORE_W // 2 + 2   # left edge of More button (split layout)


class ScoresheetScreen(ui.Screen):
    name = 'scoresheet'

    def build(self, move_history, move_label='', score_end=None) -> Image.Image:
        """Portrait image — raw SAN, no glyphs (unreadable at small size).

        score_end: exclusive end index into move_history for the displayed window.
                   None means show the most recent moves.
        """
        img, draw = self.new_image(portrait=True)
        f = self.fonts

        draw.rectangle([(0, 0), (config.SCORE_W - 1, SCORE_TITLE_H - 1)], fill=0)
        ui.draw_centered(draw, config.SCORE_W // 2, SCORE_TITLE_H // 2,
                         'Score Sheet', f['title'], 255)

        total    = len(move_history)
        has_more = total > SCORE_ROWS * 2

        btn_cy = (SCORE_BACK_Y0 + SCORE_BACK_Y1) // 2
        if has_more:
            back_x1 = SCORE_MORE_X0 - 3
            draw.rectangle([(2, SCORE_BACK_Y0), (back_x1, SCORE_BACK_Y1)], outline=0)
            ui.draw_centered(draw, (2 + back_x1) // 2, btn_cy, 'Back', f['btn'], 0)
            draw.rectangle([(SCORE_MORE_X0, SCORE_BACK_Y0), (config.SCORE_W - 3, SCORE_BACK_Y1)],
                           outline=0)
            ui.draw_centered(draw, (SCORE_MORE_X0 + config.SCORE_W - 3) // 2, btn_cy,
                             'More', f['btn'], 0)
        else:
            draw.rectangle([(2, SCORE_BACK_Y0), (config.SCORE_W - 3, SCORE_BACK_Y1)], outline=0)
            ui.draw_centered(draw, config.SCORE_W // 2, btn_cy, 'Back', f['btn'], 0)

        se    = score_end if score_end is not None else total
        start = max(0, se - SCORE_ROWS * 2)
        if start % 2 == 1:
            start -= 1
        recent     = move_history[start:se]
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

    def hit(self, tx: int, ty: int, move_history=(), **kw) -> str | None:
        if SCORE_BACK_Y0 <= ty <= SCORE_BACK_Y1:
            has_more = len(move_history) > SCORE_ROWS * 2
            if has_more and tx >= SCORE_MORE_X0:
                return 'more'
            x1 = (SCORE_MORE_X0 - 3) if has_more else (config.SCORE_W - 3)
            if 2 <= tx <= x1:
                return 'back'
        return None


_screen = ScoresheetScreen()


def build_scoresheet_screen(move_history, move_label='', score_end=None) -> Image.Image:
    return _screen.build(move_history, move_label=move_label, score_end=score_end)


def next_score_end(move_history, score_end=None):
    """Compute the new score_end after pressing More.

    Scrolls back by SCORE_ROWS-2 full moves (2-move overlap with the previous
    window).  Returns None when the result wraps back to the most recent view.
    """
    total = len(move_history)
    se    = score_end if score_end is not None else total
    start = max(0, se - SCORE_ROWS * 2)
    if start % 2 == 1:
        start -= 1
    if start == 0:
        return None   # already at the beginning — wrap to most recent
    return se - (SCORE_ROWS - 2) * 2


def hit_scoresheet_back(tx: int, ty: int, has_more: bool = False) -> bool:
    x1 = (SCORE_MORE_X0 - 3) if has_more else (config.SCORE_W - 3)
    return 2 <= tx <= x1 and SCORE_BACK_Y0 <= ty <= SCORE_BACK_Y1


def hit_scoresheet_more(tx: int, ty: int) -> bool:
    return SCORE_MORE_X0 <= tx <= config.SCORE_W - 3 and SCORE_BACK_Y0 <= ty <= SCORE_BACK_Y1
