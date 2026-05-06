"""Shared chess-board drawing component.

draw_board() renders an 8×8 board at an arbitrary pixel position so both the
full-screen board view and the compact puzzle board can reuse one implementation.
"""

import os
import chess
from PIL import ImageFont, ImageDraw
import config
import ui

WHITE_GLYPHS = {
    chess.PAWN:   '♙', chess.KNIGHT: '♘', chess.BISHOP: '♗',
    chess.ROOK:   '♖', chess.QUEEN:  '♕', chess.KING:   '♔',
}
BLACK_GLYPHS = {
    chess.PAWN:   '♟', chess.KNIGHT: '♞', chess.BISHOP: '♝',
    chess.ROOK:   '♜', chess.QUEEN:  '♛', chess.KING:   '♚',
}

_piece_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def get_piece_font(size: int = config.SIZE_BOARD_PIECE) -> ImageFont.FreeTypeFont:
    """Return (cached) piece font at *size* pt, falling back to default."""
    if size not in _piece_font_cache:
        path = next((p for p in config.FONT_PIECE_PATHS if os.path.exists(p)), None)
        _piece_font_cache[size] = (
            ImageFont.truetype(path, size) if path else ImageFont.load_default()
        )
    return _piece_font_cache[size]


def hatch_square(draw: ImageDraw.ImageDraw, px: int, py: int, sq: int) -> None:
    """Fill a dark square with a diagonal-line hatch pattern."""
    for d in range(0, 2 * sq, 3):
        if d < sq:
            draw.line([(px + d, py), (px, py + d)], fill=0)
        else:
            draw.line([(px + sq - 1, py + d - sq + 1),
                       (px + d - sq + 1, py + sq - 1)], fill=0)


def draw_board(
    draw: ImageDraw.ImageDraw,
    board: chess.Board,
    x0: int,
    y0: int,
    sq: int,
    fonts: dict,
    *,
    player_white: bool = True,
) -> None:
    """Draw the board at pixel origin (x0, y0) with squares of size sq.

    White pieces are rendered with an outline (4-direction offset) so they
    stand out against light squares; black pieces are drawn directly.
    player_white=True puts rank 1 at the bottom (standard orientation).
    """
    piece_font = get_piece_font(config.SIZE_BOARD_PIECE)
    pawn_font  = get_piece_font(config.SIZE_BOARD_PIECE - 1)

    board_px = 8 * sq

    for vrank in range(8):
        for vfile in range(8):
            if player_white:
                logical_sq = chess.square(vfile, vrank)
            else:
                logical_sq = chess.square(7 - vfile, 7 - vrank)

            px = x0 + vfile * sq
            py = y0 + (7 - vrank) * sq
            x1, y1 = px + sq - 1, py + sq - 1

            if (vfile + vrank) % 2 == 0:
                hatch_square(draw, px, py, sq)

            piece = board.piece_at(logical_sq)
            if piece:
                cx = (px + x1) // 2 + config.BOARD_PIECE_OFFSET_X
                cy = (py + y1) // 2 + config.BOARD_PIECE_OFFSET_Y
                if piece.color == chess.WHITE:
                    is_pawn  = piece.piece_type == chess.PAWN
                    out_font = pawn_font if is_pawn else piece_font
                    draw_cy  = cy if is_pawn else cy - 1
                    og = WHITE_GLYPHS[piece.piece_type]
                    fg = BLACK_GLYPHS[piece.piece_type]
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        ui.draw_centered(draw, cx + dx, draw_cy + dy, og, out_font, 0)
                    ui.draw_centered(draw, cx, draw_cy, fg, out_font, 255)
                else:
                    bf = piece_font if piece_font else fonts.get('small', fonts.get('btn'))
                    ui.draw_centered(draw, cx, cy,
                                     BLACK_GLYPHS[piece.piece_type], bf, 0)

    draw.rectangle([(x0, y0), (x0 + board_px - 1, y0 + board_px - 1)], outline=0)
