"""Game analysis screen — step through the finished game move by move.

The right panel uses the no-title chrome layout:
  black header  → "Analyze" title + current move label
  top button    → "Next"  (advance one move; hidden when at the final position)
  bottom button → "End"   (always present)
"""

import chess
from PIL import Image
import ui
import config
import board_widget

# Board centred in the left panel (same geometry as screen_board.py)
_BOARD_X0 = (ui.VSEP_X - 8 * config.BOARD_SQ) // 2 + config.BOARD_OFFSET_X
_BOARD_Y0 = (ui.H - 8 * config.BOARD_SQ) // 2 + config.BOARD_OFFSET_Y


def _mark_square(draw, sq: int, player_white: bool, x0: int, y0: int,
                 sq_sz: int) -> None:
    """Draw corner brackets on *sq* to highlight it as part of the last move."""
    vfile = chess.square_file(sq) if player_white else 7 - chess.square_file(sq)
    vrank = chess.square_rank(sq) if player_white else 7 - chess.square_rank(sq)
    px = x0 + vfile * sq_sz
    py = y0 + (7 - vrank) * sq_sz
    # Two inset rectangles (black + white) for contrast on both square colours.
    draw.rectangle([(px + 1, py + 1), (px + sq_sz - 2, py + sq_sz - 2)],
                   outline=0, width=1)
    draw.rectangle([(px + 2, py + 2), (px + sq_sz - 3, py + sq_sz - 3)],
                   outline=255, width=1)


class AnalyzeScreen(ui.Screen):
    name = 'analyze'

    def build(self, board: chess.Board, move_idx: int, move_total: int,
              last_move: chess.Move | None = None,
              player_is_white: bool = True) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts

        at_end = (move_idx >= move_total)
        sub = 'Start' if move_idx == 0 else f'{move_idx}/{move_total}'

        ui.draw_chrome(
            draw, f,
            screen_title='Analyze',
            ok_active=True,
            ok_label='End' if at_end else 'Next',
            sec_label=None if at_end else 'End',
            no_title=True,
            nt_sub=sub,
        )

        draw.line([(ui.VSEP_X, 0), (ui.VSEP_X, ui.H - 1)], fill=0)
        board_widget.draw_board(draw, board, _BOARD_X0, _BOARD_Y0,
                                config.BOARD_SQ, f, player_white=player_is_white)

        if last_move is not None:
            _mark_square(draw, last_move.from_square, player_is_white,
                         _BOARD_X0, _BOARD_Y0, config.BOARD_SQ)
            _mark_square(draw, last_move.to_square, player_is_white,
                         _BOARD_X0, _BOARD_Y0, config.BOARD_SQ)

        return img

    def hit(self, lx: int, ly: int, move_idx: int = 0,
            move_total: int = 0, **kw) -> str | None:
        at_end = (move_idx >= move_total)
        if at_end:
            if ui.hit_ok(lx, ly, no_title=True):
                return 'end'
        else:
            if ui.hit_ok(lx, ly, split=True, no_title=True):
                return 'next'
            if ui.hit_sec(lx, ly, no_title=True):
                return 'end'
        return None


_screen = AnalyzeScreen()


def build_analyze_screen(board: chess.Board, move_idx: int, move_total: int,
                         last_move: chess.Move | None = None,
                         player_is_white: bool = True) -> Image.Image:
    return _screen.build(board, move_idx, move_total,
                         last_move=last_move, player_is_white=player_is_white)


def hit_analyze(lx: int, ly: int, move_idx: int, move_total: int) -> str | None:
    return _screen.hit(lx, ly, move_idx=move_idx, move_total=move_total)
