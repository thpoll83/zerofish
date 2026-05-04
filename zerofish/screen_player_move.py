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
_PM_GAP_ROW  = 2
_PM_YOFFSET  = 2
PM_ROW_H     = (ui.H - _PM_YOFFSET - 2 * _PM_GAP_ROW) // 3  # = 38 px
PM_ROW1_Y    = _PM_YOFFSET
PM_ROW2_Y    = PM_ROW1_Y + PM_ROW_H + _PM_GAP_ROW           # = 42
PM_ROW3_Y    = PM_ROW2_Y + PM_ROW_H + _PM_GAP_ROW           # = 82
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


class PlayerMoveScreen(ui.Screen):
    name = 'player_move'

    def __init__(self) -> None:
        self._piece_btns = [ui.Button(pm_piece_rect(i), PIECE_SYMBOLS[i],
                                     text_offset=(1, 1))
                            for i in range(len(PIECES))]
        self._file_btns  = [ui.Button(pm_file_rect(i),  FILES[i])
                            for i in range(len(FILES))]
        self._rank_btns  = [ui.Button(pm_rank_rect(i),  RANKS[i])
                            for i in range(len(RANKS))]

    def build(self, sel_piece=None, sel_file=None, sel_rank=None,
              inv_count=0, move_label='') -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts
        ok_ready = (sel_piece is not None and sel_file is not None
                    and sel_rank is not None)
        inv_str = f'Inv:{inv_count}' if inv_count else ''
        ui.draw_chrome(draw, f, move_label, ok_active=ok_ready,
                       sec_label='...', no_title=True, nt_sub=inv_str)

        for i, btn in enumerate(self._piece_btns):
            btn.style = ui.Button.FILLED if i == sel_piece else ui.Button.OUTLINE
            btn.draw(draw, f['piece'])

        for i, btn in enumerate(self._file_btns):
            btn.style = ui.Button.FILLED if i == sel_file else ui.Button.OUTLINE
            btn.draw(draw, f['btn'])

        for i, btn in enumerate(self._rank_btns):
            btn.style = ui.Button.FILLED if i == sel_rank else ui.Button.OUTLINE
            btn.draw(draw, f['btn'])

        return img

    def hit(self, lx: int, ly: int,
            sel_piece=None, sel_file=None, sel_rank=None) -> str | None:
        if ui.hit_sec(lx, ly, no_title=True):
            return 'menu'
        for i, btn in enumerate(self._piece_btns):
            if btn.hit(lx, ly):
                return f'piece:{i}'
        for i, btn in enumerate(self._file_btns):
            if btn.hit(lx, ly):
                return f'file:{i}'
        for i, btn in enumerate(self._rank_btns):
            if btn.hit(lx, ly):
                return f'rank:{i}'
        if (ui.hit_ok(lx, ly, split=True, no_title=True)
                and sel_piece is not None
                and sel_file  is not None
                and sel_rank  is not None):
            return 'ok'
        return None


_screen = PlayerMoveScreen()


def build_player_move_screen(sel_piece, sel_file, sel_rank,
                              inv_count=0, move_label='') -> Image.Image:
    return _screen.build(sel_piece, sel_file, sel_rank, inv_count, move_label)


def hit_pm_piece(idx: int, lx: int, ly: int) -> bool:
    return _screen._piece_btns[idx].hit(lx, ly)


def hit_pm_file(idx: int, lx: int, ly: int) -> bool:
    return _screen._file_btns[idx].hit(lx, ly)


def hit_pm_rank(idx: int, lx: int, ly: int) -> bool:
    return _screen._rank_btns[idx].hit(lx, ly)


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
