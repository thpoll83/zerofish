import chess
from PIL import Image, ImageDraw
import ui
import config

BOARD_X0 = (ui.VSEP_X - 8 * config.BOARD_SQ) // 2 + config.BOARD_OFFSET_X
BOARD_Y0 = (ui.H - 8 * config.BOARD_SQ) // 2 + config.BOARD_OFFSET_Y

# Unicode chess piece glyphs: hollow for white, filled for black
_BOARD_GLYPHS = {
    chess.PAWN:   {chess.WHITE: '♙', chess.BLACK: '♟'},
    chess.KNIGHT: {chess.WHITE: '♘', chess.BLACK: '♞'},
    chess.BISHOP: {chess.WHITE: '♗', chess.BLACK: '♝'},
    chess.ROOK:   {chess.WHITE: '♖', chess.BLACK: '♜'},
    chess.QUEEN:  {chess.WHITE: '♕', chess.BLACK: '♛'},
    chess.KING:   {chess.WHITE: '♔', chess.BLACK: '♚'},
}


def build_board_screen(board, player_is_white=True) -> Image.Image:
    """Full-width chessboard in landscape; no title bar; Back button on right."""
    img  = Image.new('1', (ui.W, ui.H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts('board')

    # Right panel: separator + Back button
    draw.line([(ui.VSEP_X, 0), (ui.VSEP_X, ui.H - 1)], fill=0)
    ui.draw_btn(draw, [(ui.OK_X0, 6), (ui.OK_X1, ui.H - 6)], outline=0)
    ui.draw_centered(draw, (ui.OK_X0 + ui.OK_X1) // 2, ui.H // 2, 'Back', f['btn'], 0)

    # Chessboard — show from player's perspective
    SQ   = config.BOARD_SQ
    BOARD_PX = 8 * SQ
    for visual_rank in range(8):       # 0 = bottom row for this player
        for visual_file in range(8):   # 0 = left file for this player
            if player_is_white:
                sq = chess.square(visual_file, visual_rank)
            else:
                sq = chess.square(7 - visual_file, 7 - visual_rank)

            px = BOARD_X0 + visual_file * SQ
            py = BOARD_Y0 + (7 - visual_rank) * SQ   # rank 0 at bottom → highest py
            x1, y1 = px + SQ - 1, py + SQ - 1

            # a1 (visual 0,0 for white) is a dark square: (file+rank)%2==0 → dark
            is_dark = (visual_file + visual_rank) % 2 == 0
            # No per-square outline — both light and dark squares fill their
            # full SQ×SQ area so neither appears larger than the other.
            draw.rectangle([(px, py), (x1, y1)], fill=0 if is_dark else 255)

            piece = board.piece_at(sq)
            if piece:
                glyph = _BOARD_GLYPHS[piece.piece_type][piece.color]
                fill  = 255 if is_dark else 0
                cx = (px + x1) // 2 + config.BOARD_PIECE_OFFSET_X
                cy = (py + y1) // 2 + config.BOARD_PIECE_OFFSET_Y
                ui.draw_centered(draw, cx, cy, glyph, f['board'], fill)

    # Single border around the whole board
    draw.rectangle(
        [(BOARD_X0, BOARD_Y0), (BOARD_X0 + BOARD_PX - 1, BOARD_Y0 + BOARD_PX - 1)],
        outline=0,
    )

    return img


def hit_board_back(lx, ly) -> bool:
    return lx > ui.VSEP_X
