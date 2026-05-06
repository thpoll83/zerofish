import chess
from PIL import Image
import ui
import config
import board_widget

BOARD_X0 = (ui.VSEP_X - 8 * config.BOARD_SQ) // 2 + config.BOARD_OFFSET_X
BOARD_Y0 = (ui.H - 8 * config.BOARD_SQ) // 2 + config.BOARD_OFFSET_Y

_BACK_BTN_RECT = (ui.OK_X0, 6, ui.OK_X1, ui.H - 6)


class BoardScreen(ui.Screen):
    name = 'board'

    def __init__(self) -> None:
        self._back_btn = ui.Button(_BACK_BTN_RECT, 'Back', ui.Button.OUTLINE)

    def build(self, board: chess.Board, player_is_white: bool = True) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts
        draw.line([(ui.VSEP_X, 0), (ui.VSEP_X, ui.H - 1)], fill=0)
        self._back_btn.draw(draw, f['btn'])
        board_widget.draw_board(draw, board, BOARD_X0, BOARD_Y0,
                                config.BOARD_SQ, f, player_white=player_is_white)
        return img

    def hit(self, lx: int, ly: int, **kw) -> str | None:
        if lx > ui.VSEP_X:
            return 'back'
        return None


_screen = BoardScreen()


def build_board_screen(board: chess.Board, player_is_white: bool = True) -> Image.Image:
    return _screen.build(board, player_is_white)


def hit_board_back(lx: int, ly: int) -> bool:
    return _screen._back_btn.hit(lx, ly)
