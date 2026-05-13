"""Game analysis screen — step through the finished game move by move.

The right panel uses the no-title chrome layout:
  black header  → "Replay" title + current move label
  top button    → "Next"  (advance one move; hidden when at the final position)
  bottom button → "End"   (always present)

The left panel is split:
  narrow text column (x=0..69)  → "Played:" / "Best:" SANs
  board (x=70..189, sq=15 px)   → current position
"""

import chess
from PIL import Image
import ui
import config
import board_widget

_TEXT_COL_W = 70          # width of the left text column
_BOARD_X0   = _TEXT_COL_W + config.BOARD_OFFSET_X
_BOARD_Y0   = (ui.H - 8 * config.BOARD_SQ) // 2 + config.BOARD_OFFSET_Y
_COL_CX     = _TEXT_COL_W // 2        # centre x of the text column
_DIV_Y      = ui.H // 2               # horizontal divider between Played / Best


def _mark_square(draw, sq: int, player_white: bool, x0: int, y0: int,
                 sq_sz: int) -> None:
    """Draw corner brackets on *sq* to highlight it as part of the last move."""
    vfile = chess.square_file(sq) if player_white else 7 - chess.square_file(sq)
    vrank = chess.square_rank(sq) if player_white else 7 - chess.square_rank(sq)
    px = x0 + vfile * sq_sz
    py = y0 + (7 - vrank) * sq_sz
    draw.rectangle([(px + 1, py + 1), (px + sq_sz - 2, py + sq_sz - 2)],
                   outline=0, width=1)
    draw.rectangle([(px + 2, py + 2), (px + sq_sz - 3, py + sq_sz - 3)],
                   outline=255, width=1)


def _draw_text_column(draw, f, played_san: str, best_san: str) -> None:
    """Draw the "Played:" and "Best:" text in the left column."""
    lbl  = f['small']
    move = f['btn_diff']

    played_text = played_san if played_san else '—'
    best_text   = best_san   if best_san   else '—'

    # Top half: Played
    ui.draw_centered(draw, _COL_CX, 14, 'Played:', lbl, 0)
    ui.draw_centered(draw, _COL_CX, 36, played_text, move, 0)

    # Divider
    draw.line([(_TEXT_COL_W - 1, _DIV_Y), (0, _DIV_Y)], fill=0)

    # Bottom half: Best
    ui.draw_centered(draw, _COL_CX, _DIV_Y + 14, 'Best:', lbl, 0)
    ui.draw_centered(draw, _COL_CX, _DIV_Y + 36, best_text, move, 0)


class AnalyzeScreen(ui.Screen):
    name = 'analyze'

    def build(self, board: chess.Board, move_idx: int, move_total: int,
              last_move: chess.Move | None = None,
              player_is_white: bool = True,
              played_san: str = '',
              best_san: str = '') -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts

        at_end = (move_idx >= move_total)
        sub = 'Start' if move_idx == 0 else f'{move_idx}/{move_total}'

        ui.draw_chrome(
            draw, f,
            screen_title='Replay',
            ok_active=True,
            ok_label='End' if at_end else 'Next',
            sec_label=None if at_end else 'End',
            no_title=True,
            nt_sub=sub,
        )

        draw.line([(ui.VSEP_X, 0), (ui.VSEP_X, ui.H - 1)], fill=0)

        _draw_text_column(draw, f, played_san, best_san)

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
                         player_is_white: bool = True,
                         played_san: str = '',
                         best_san: str = '') -> Image.Image:
    return _screen.build(board, move_idx, move_total,
                         last_move=last_move, player_is_white=player_is_white,
                         played_san=played_san, best_san=best_san)


def hit_analyze(lx: int, ly: int, move_idx: int, move_total: int) -> str | None:
    return _screen.hit(lx, ly, move_idx=move_idx, move_total=move_total)
