"""Puzzle hint screen: shown after a wrong move.

Displays the board at the point of failure and, on the left side,
the solution for the current move (plus any already-accomplished moves).
The player presses OK to advance to the next puzzle.
"""

import os
import chess
from PIL import Image, ImageDraw, ImageFont
import ui
import config
from screen_puzzle import (draw_puzzle_board, _STATS_LX,
                           _RESULT_CX, _STATS_YS, _get_result_font)

_hint_font_cache: ImageFont.FreeTypeFont | None = None


def _get_hint_font() -> ImageFont.FreeTypeFont:
    """Small DejaVu font that covers ✓ (U+2713)."""
    global _hint_font_cache
    if _hint_font_cache is None:
        path = next((p for p in config.FONT_RESULT_PATHS if os.path.exists(p)), None)
        _hint_font_cache = (ImageFont.truetype(path, config.SIZE_LABEL)
                            if path else ImageFont.load_default())
    return _hint_font_cache


def _hint_lines(hint_fen: str, hint_moves: list[str],
                hint_move_idx: int) -> tuple[list[str], str | None]:
    """Return (accomplished_sans, current_san) from the stored hint info.

    accomplished_sans — player moves already done correctly, in order
    current_san       — the correct move the player just failed
    """
    accomplished: list[str] = []
    current: str | None = None
    try:
        b = chess.Board(hint_fen)
        for i, uci in enumerate(hint_moves):
            if i > hint_move_idx:
                break
            move = chess.Move.from_uci(uci)
            san  = b.san(move)
            b.push(move)
            if i % 2 == 0:      # player move (even index)
                if i < hint_move_idx:
                    accomplished.append(san)
                else:           # i == hint_move_idx
                    current = san
    except Exception:
        pass
    return accomplished, current


class PuzzleHintScreen(ui.Screen):
    name = 'puzzle_hint'

    def build(self, board: chess.Board | None,
              hint_fen: str, hint_moves: list[str],
              hint_move_idx: int) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts

        # Right panel: no-title chrome, "Hint" header, OK button
        ui.draw_chrome(draw, f, 'Hint', ok_active=True, no_title=True)

        # Board
        if board is not None:
            draw_puzzle_board(draw, board, f)

        # Hint text in the stats column (left of board)
        hf  = _get_hint_font()
        lh  = config.SIZE_LABEL + 3      # line height in pixels
        x   = _STATS_LX
        accomplished, current = _hint_lines(hint_fen, hint_moves, hint_move_idx)

        y = 5
        draw.text((x, y), 'Hint:', font=hf, fill=0)
        y += lh + 2

        for san in accomplished:
            draw.text((x, y), f'{san}✓', font=hf, fill=0)   # "e5✓"
            y += lh

        if current:
            draw.text((x, y), current, font=hf, fill=0)

        # ✗ glyph in the same bottom-left position as the puzzle screen result
        ui.draw_centered(draw, _RESULT_CX, _STATS_YS[2] - 2, '✗', _get_result_font(), 0)

        return img

    def hit(self, lx: int, ly: int) -> str | None:
        return 'ok' if ui.hit_ok(lx, ly, no_title=True) else None


_screen = PuzzleHintScreen()


def build_puzzle_hint_screen(board: chess.Board | None,
                              hint_fen: str,
                              hint_moves: list[str],
                              hint_move_idx: int) -> Image.Image:
    return _screen.build(board, hint_fen, hint_moves, hint_move_idx)


def hit_puzzle_hint(lx: int, ly: int) -> str | None:
    return _screen.hit(lx, ly)
