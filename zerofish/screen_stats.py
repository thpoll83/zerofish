"""Stats screen: total and per-category puzzle statistics."""

from PIL import Image, ImageDraw
import ui
import puzzle_state

# Two-column layout within the left panel
_COL2_X = ui.VSEP_X // 2   # x-start of right stat column


class StatsScreen(ui.Screen):
    name = 'stats'

    def build(self) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts

        ui.draw_chrome(draw, f, 'Stats', ok_active=True, ok_label='Back')

        hf = f['small']
        lh = 12
        x  = 4
        y  = ui.TITLE_H + 4

        total = puzzle_state.total_solved()
        draw.text((x, y), f'Solved: {total}', font=hf, fill=0)
        y += lh + 4

        cats = puzzle_state.get_category_stats()
        for i, cat in enumerate(cats):
            col_x = _COL2_X if i % 2 else x
            col_y = y + (i // 2) * (lh + 2)
            s = cat['solved']
            a = cat['available']
            draw.text((col_x, col_y), f'{cat["label"]}: {s}/{s + a}', font=hf, fill=0)

        return img

    def hit(self, lx: int, ly: int, **kw) -> str | None:
        return 'back' if ui.hit_ok(lx, ly) else None


_screen = StatsScreen()


def build_stats_screen() -> Image.Image:
    return _screen.build()


def hit_stats(lx: int, ly: int) -> str | None:
    return _screen.hit(lx, ly)
