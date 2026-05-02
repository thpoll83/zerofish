import chess
from PIL import Image, ImageDraw, ImageFont
import ui
import config

BOARD_X0 = (ui.VSEP_X - 8 * config.BOARD_SQ) // 2 + config.BOARD_OFFSET_X
BOARD_Y0 = (ui.H - 8 * config.BOARD_SQ) // 2 + config.BOARD_OFFSET_Y

# Hollow glyphs for white pieces (outline look), filled for black.
_WHITE_GLYPHS = {
    chess.PAWN:   '♙',
    chess.KNIGHT: '♘',
    chess.BISHOP: '♗',
    chess.ROOK:   '♖',
    chess.QUEEN:  '♕',
    chess.KING:   '♔',
}
_BLACK_GLYPHS = {
    chess.PAWN:   '♟',
    chess.KNIGHT: '♞',
    chess.BISHOP: '♝',
    chess.ROOK:   '♜',
    chess.QUEEN:  '♛',
    chess.KING:   '♚',
}

# White pawns rendered 1 pt smaller so the filled glyph + 4-direction outline
# doesn't appear larger than the other pieces.
_SIZE_WHITE_PAWN = config.SIZE_BOARD_PIECE - 1
_white_pawn_font: ImageFont.FreeTypeFont | None = None


def _get_white_pawn_font() -> ImageFont.FreeTypeFont:
    global _white_pawn_font
    if _white_pawn_font is None:
        path = next((p for p in config.FONT_PIECE_PATHS
                     if __import__('os').path.exists(p)), None)
        if path:
            _white_pawn_font = ImageFont.truetype(path, _SIZE_WHITE_PAWN)
        else:
            _white_pawn_font = ImageFont.load_default()
    return _white_pawn_font


def _hatch_square(draw, px, py, sq):
    """45° diagonal hatch lines (↘) every 3 px across the square."""
    for d in range(0, 2 * sq, 3):
        if d < sq:
            draw.line([(px + d, py), (px, py + d)], fill=0)
        else:
            draw.line([(px + sq - 1, py + d - sq + 1),
                       (px + d - sq + 1, py + sq - 1)], fill=0)


def build_board_screen(board, player_is_white=True) -> Image.Image:
    """Full-width chessboard in landscape; no title bar; Back button on right."""
    img  = Image.new('1', (ui.W, ui.H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts('board')

    # Right panel: separator + Back button
    draw.line([(ui.VSEP_X, 0), (ui.VSEP_X, ui.H - 1)], fill=0)
    ui.draw_btn(draw, [(ui.OK_X0, 6), (ui.OK_X1, ui.H - 6)], outline=0)
    ui.draw_centered(draw, (ui.OK_X0 + ui.OK_X1) // 2, ui.H // 2, 'Back', f['btn'], 0)

    SQ       = config.BOARD_SQ
    BOARD_PX = 8 * SQ
    pawn_font = _get_white_pawn_font()

    for visual_rank in range(8):
        for visual_file in range(8):
            if player_is_white:
                sq = chess.square(visual_file, visual_rank)
            else:
                sq = chess.square(7 - visual_file, 7 - visual_rank)

            px = BOARD_X0 + visual_file * SQ
            py = BOARD_Y0 + (7 - visual_rank) * SQ
            x1, y1 = px + SQ - 1, py + SQ - 1

            # a1 (visual 0,0 for white) is a dark square: (file+rank)%2==0 → dark
            is_dark = (visual_file + visual_rank) % 2 == 0
            if is_dark:
                _hatch_square(draw, px, py, SQ)
            # light squares stay white (image initialized to 255)

            piece = board.piece_at(sq)
            if piece:
                cx = (px + x1) // 2 + config.BOARD_PIECE_OFFSET_X
                cy = (py + y1) // 2 + config.BOARD_PIECE_OFFSET_Y
                if piece.color == chess.WHITE:
                    # Hollow glyph at 4 offsets in black = thin outline border.
                    # Filled glyph at center in white = solid white interior.
                    # Pawns use a smaller font so the filled glyph doesn't over-inflate.
                    is_pawn   = piece.piece_type == chess.PAWN
                    draw_cy   = cy if is_pawn else cy - 1  # non-pawn glyphs sit 1px low
                    out_font  = pawn_font if is_pawn else f['board']
                    fill_font = pawn_font if is_pawn else f['board']
                    outline_g = _WHITE_GLYPHS[piece.piece_type]
                    fill_g    = _BLACK_GLYPHS[piece.piece_type]
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        ui.draw_centered(draw, cx + dx, draw_cy + dy, outline_g, out_font, 0)
                    ui.draw_centered(draw, cx, draw_cy, fill_g, fill_font, 255)
                else:
                    # Black piece: solid black filled glyph
                    ui.draw_centered(draw, cx, cy, _BLACK_GLYPHS[piece.piece_type],
                                     f['board'], 0)

    draw.rectangle(
        [(BOARD_X0, BOARD_Y0), (BOARD_X0 + BOARD_PX - 1, BOARD_Y0 + BOARD_PX - 1)],
        outline=0,
    )

    return img


def hit_board_back(lx, ly) -> bool:
    return lx > ui.VSEP_X
