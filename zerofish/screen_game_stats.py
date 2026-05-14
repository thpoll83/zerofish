"""Game statistics screen — page 2 of Stats, showing win/loss/draw totals."""

from PIL import Image
import ui
import game_state


class GameStatsScreen(ui.Screen):
    name = 'game_stats'

    def build(self) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts

        ui.draw_chrome(draw, f, 'Game Stats', ok_active=True, ok_label='Back')

        s = game_state.load_game_stats()
        wins     = s.get('wins', 0)
        losses   = s.get('losses', 0)
        draws    = s.get('draws', 0)
        resigned = s.get('resigned', 0)
        total    = wins + losses + draws + resigned

        hf = f['small']
        lh = 13
        x  = 4
        y  = ui.TITLE_H + 6

        draw.text((x, y), f'Total games: {total}', font=hf, fill=0)
        y += lh + 4
        draw.text((x, y), f'Wins:     {wins}', font=hf, fill=0)
        y += lh
        draw.text((x, y), f'Losses:   {losses}', font=hf, fill=0)
        y += lh
        draw.text((x, y), f'Draws:    {draws}', font=hf, fill=0)
        y += lh
        draw.text((x, y), f'Resigned: {resigned}', font=hf, fill=0)

        return img

    def hit(self, lx: int, ly: int, **kw) -> str | None:
        return 'back' if ui.hit_ok(lx, ly) else None


_screen = GameStatsScreen()


def build_game_stats_screen() -> Image.Image:
    return _screen.build()


def hit_game_stats(lx: int, ly: int) -> str | None:
    return _screen.hit(lx, ly)
