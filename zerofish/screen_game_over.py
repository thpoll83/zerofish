import chess
from PIL import Image, ImageDraw
import ui


def game_over_message(board, player_is_white) -> tuple[str, str]:
    outcome = board.outcome()
    if outcome is None:
        return 'Game Over', board.result()
    term = outcome.termination
    if term == chess.Termination.CHECKMATE:
        return ('You win!' if outcome.winner == player_is_white else 'You lose'), 'Checkmate'
    if term == chess.Termination.STALEMATE:
        return 'Draw', 'Stalemate'
    if term == chess.Termination.INSUFFICIENT_MATERIAL:
        return 'Draw', 'Insuf. material'
    if term in (chess.Termination.FIFTY_MOVES, chess.Termination.SEVENTYFIVE_MOVES):
        return 'Draw', '50-move rule'
    if term in (chess.Termination.THREEFOLD_REPETITION, chess.Termination.FIVEFOLD_REPETITION):
        return 'Draw', 'Repetition'
    return 'Game Over', board.result()


class GameOverScreen(ui.Screen):
    name = 'game_over'

    def build(self, line1: str, line2: str) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts
        ui.draw_chrome(draw, f, 'Game Over', ok_active=True)
        cx = ui.VSEP_X // 2
        cy = (ui.TITLE_H + ui.H) // 2
        ui.draw_centered(draw, cx, cy - 14, line1, f['result'], 0)
        if line2:
            ui.draw_centered(draw, cx, cy + 22, line2, f['small'], 0)
        return img

    def hit(self, lx: int, ly: int, **kw) -> str | None:
        if ui.hit_ok(lx, ly):
            return 'ok'
        return None


_screen = GameOverScreen()


def build_game_over_screen(line1: str, line2: str) -> Image.Image:
    return _screen.build(line1, line2)
