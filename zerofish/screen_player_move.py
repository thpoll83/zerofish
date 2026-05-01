import chess
from PIL import Image, ImageDraw
import ui
from screen_promotion import PROMO_PIECE_TYPES

PIECES        = ['P', 'N', 'B', 'R', 'Q', 'K']
PIECE_SYMBOLS = ['♟', '♞', '♝', '♜', '♛', '♚']
FILES         = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
RANKS         = ['1', '2', '3', '4', '5', '6', '7', '8']

PM_MARGIN    = 2
PM_GAP       = 1
_PM_GAP_ROW  = 2                                   # gap between rows
_PM_YOFFSET  = 2                                   # top padding keeps black headline clear
PM_ROW_H     = (ui.H - _PM_YOFFSET - 2 * _PM_GAP_ROW) // 3  # = 38 px
PM_ROW1_Y    = _PM_YOFFSET
PM_ROW2_Y    = PM_ROW1_Y + PM_ROW_H + _PM_GAP_ROW # = 42
PM_ROW3_Y    = PM_ROW2_Y + PM_ROW_H + _PM_GAP_ROW # = 82
PM_MAX_X   = ui.VSEP_X - 3
PM_PIECE_W = (PM_MAX_X - PM_MARGIN - 5 * PM_GAP) // 6
PM_FILE_W  = (PM_MAX_X - PM_MARGIN - 7 * PM_GAP) // 8


def pm_piece_rect(idx) -> tuple[int, int, int, int]:
    x0 = PM_MARGIN + idx * (PM_PIECE_W + PM_GAP)
    return (x0, PM_ROW1_Y, x0 + PM_PIECE_W - 1, PM_ROW1_Y + PM_ROW_H - 1)


def pm_file_rect(idx) -> tuple[int, int, int, int]:
    x0 = PM_MARGIN + idx * (PM_FILE_W + PM_GAP)
    return (x0, PM_ROW2_Y, x0 + PM_FILE_W - 1, PM_ROW2_Y + PM_ROW_H - 1)


def pm_rank_rect(idx) -> tuple[int, int, int, int]:
    x0 = PM_MARGIN + idx * (PM_FILE_W + PM_GAP)
    return (x0, PM_ROW3_Y, x0 + PM_FILE_W - 1, PM_ROW3_Y + PM_ROW_H - 1)


def hit_pm_piece(idx, lx, ly) -> bool:
    x0, y0, x1, y1 = pm_piece_rect(idx)
    return x0 <= lx <= x1 and y0 <= ly <= y1


def hit_pm_file(idx, lx, ly) -> bool:
    x0, y0, x1, y1 = pm_file_rect(idx)
    return x0 <= lx <= x1 and y0 <= ly <= y1


def hit_pm_rank(idx, lx, ly) -> bool:
    x0, y0, x1, y1 = pm_rank_rect(idx)
    return x0 <= lx <= x1 and y0 <= ly <= y1


def build_player_move_screen(sel_piece, sel_file, sel_rank,
                              inv_count=0, move_label='') -> Image.Image:
    img  = Image.new('1', (ui.W, ui.H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts('player_move')
    ok_ready = (sel_piece is not None and sel_file is not None and sel_rank is not None)
    inv_str  = f'Inv:{inv_count}' if inv_count else ''
    ui.draw_chrome(draw, f, move_label, ok_active=ok_ready, sec_label='...',
                   no_title=True, nt_sub=inv_str)

    def _row(items, rects_fn, selected_idx, font=None, off_x=0, off_y=0):
        _f = font or f['btn']
        for i, label in enumerate(items):
            x0, y0, x1, y1 = rects_fn(i)
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            if i == selected_idx:
                ui.draw_btn(draw, [(x0, y0), (x1, y1)], fill=0)
                ui.draw_centered(draw, cx+off_x, cy+off_y, label, _f, 255)
            else:
                ui.draw_btn(draw, [(x0, y0), (x1, y1)], outline=0)
                ui.draw_centered(draw, cx+off_x, cy+off_y, label, _f, 0)

    _row(PIECE_SYMBOLS, pm_piece_rect, sel_piece, f['piece'], 1, 1)
    _row(FILES,         pm_file_rect,  sel_file,  f['btn'], 0, 0)
    _row(RANKS,         pm_rank_rect,  sel_rank,  f['btn'], 0, 0)
    return img


def find_candidates(board, piece_idx, file_idx, rank_idx, promo_idx=None) -> list:
    piece_type = [chess.PAWN, chess.KNIGHT, chess.BISHOP,
                  chess.ROOK, chess.QUEEN, chess.KING][piece_idx]
    target     = chess.square(file_idx, rank_idx)
    promo_type = PROMO_PIECE_TYPES[promo_idx] if promo_idx is not None else chess.QUEEN
    out = []
    for m in board.legal_moves:
        if board.piece_type_at(m.from_square) != piece_type:
            continue
        if m.to_square != target:
            continue
        if m.promotion and m.promotion != promo_type:
            continue
        out.append(m)
    return out


def needs_promotion(board, piece_idx, file_idx, rank_idx) -> bool:
    if piece_idx != 0:
        return False
    target = chess.square(file_idx, rank_idx)
    return any(
        board.piece_type_at(m.from_square) == chess.PAWN
        and m.to_square == target
        and m.promotion is not None
        for m in board.legal_moves
    )
