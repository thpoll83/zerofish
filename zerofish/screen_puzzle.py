"""Puzzle screen: board in the centre-left area, puzzle info + controls on the right."""

import os
import chess
from PIL import Image, ImageDraw, ImageFont
import ui
import config

# ── Board position ────────────────────────────────────────────────────────────
# The board is shifted right of centre so the stats column on its left is wide
# enough for two-line labels.  Shift = half of the centred-gap (18 px), giving
# a 54 px stats column and an 18 px gap between board and right-panel separator.
_SQ      = config.BOARD_SQ
_BOARD_W = 8 * _SQ                                         # 120 px

_CENTRED_GAP = (ui.VSEP_X - _BOARD_W) // 2                # 36 px (each side when centred)
_BOARD_X0    = _CENTRED_GAP + _CENTRED_GAP // 2 + config.BOARD_OFFSET_X  # 54 px
_BOARD_Y0    = (ui.H - _BOARD_W) // 2 + config.BOARD_OFFSET_Y             # 1 px

_WHITE_GLYPHS = {
    chess.PAWN:   '♙', chess.KNIGHT: '♘', chess.BISHOP: '♗',
    chess.ROOK:   '♖', chess.QUEEN:  '♕', chess.KING:   '♔',
}
_BLACK_GLYPHS = {
    chess.PAWN:   '♟', chess.KNIGHT: '♞', chess.BISHOP: '♝',
    chess.ROOK:   '♜', chess.QUEEN:  '♛', chess.KING:   '♚',
}

# ── Stats column (x = 0 … _BOARD_X0 - 2) ─────────────────────────────────────
# Three two-line items (label + value) left-aligned: Rating, Solved, result.
_STATS_LX  = 3           # left edge of stats text
_STATS_LS  = 14          # line spacing inside each two-line block
_STATS_YS  = [20, 60, 100]       # y-centres of the three blocks

# ── Rank labels (right of board, inside the gap) ─────────────────────────────
# The 18 px gap between the board's right edge and the vertical separator line
# is used for rank numbers (1–8), one per row, to make board orientation clear.
_RANK_LABEL_X = _BOARD_X0 + _BOARD_W + (ui.VSEP_X - _BOARD_X0 - _BOARD_W) // 2  # ≈ 183

# ── Right-panel layout ────────────────────────────────────────────────────────
_HDR_H    = 36
_HDR_CY1  = _HDR_H // 4          # 9
_HDR_CY2  = _HDR_H * 3 // 4      # 27
_RX0      = ui.OK_X0              # 195
_RX1      = ui.OK_X1              # 247
_RCX      = (_RX0 + _RX1) // 2   # 221

_BTN_Y_SOLVE = (_HDR_H + 4,  _HDR_H + 4 + 24)    # (40, 64)
_BTN_Y_SKIP  = (_HDR_H + 32, _HDR_H + 32 + 24)   # (68, 92)
_BTN_Y_END   = (_HDR_H + 60, _HDR_H + 60 + 24)   # (96, 120)

_SOLVE_BTN = ui.Button((_RX0, _BTN_Y_SOLVE[0], _RX1, _BTN_Y_SOLVE[1]), 'Move', ui.Button.BAR)
_SKIP_BTN  = ui.Button((_RX0, _BTN_Y_SKIP[0],  _RX1, _BTN_Y_SKIP[1]),  'Skip',  ui.Button.BAR)
_END_BTN   = ui.Button((_RX0, _BTN_Y_END[0],   _RX1, _BTN_Y_END[1]),   'End',   ui.Button.BAR)

_NO_PUZZLE_MSG = ['No puzzles', 'Try another', 'difficulty']

_RESULT_GLYPHS = {'solved': '✓', 'skipped': '−', 'wrong': '✗'}
_RESULT_CX     = _BOARD_X0 // 2                      # 27 px — centre of stats column
_RESULT_SIZE   = round(config.SIZE_BTN * 1.7)         # ≈ 31 pt

_result_font_cache: ImageFont.FreeTypeFont | None = None


def _get_result_font() -> ImageFont.FreeTypeFont:
    global _result_font_cache
    if _result_font_cache is None:
        path = next((p for p in config.FONT_RESULT_PATHS if os.path.exists(p)), None)
        _result_font_cache = (ImageFont.truetype(path, _RESULT_SIZE)
                              if path else ImageFont.load_default())
    return _result_font_cache


def _piece_font() -> ImageFont.FreeTypeFont | None:
    path = next((p for p in config.FONT_PIECE_PATHS
                 if os.path.exists(p)), None)
    return ImageFont.truetype(path, config.SIZE_BOARD_PIECE) if path else None


_piece_font_cache: ImageFont.FreeTypeFont | None = None


def _get_piece_font():
    global _piece_font_cache
    if _piece_font_cache is None:
        _piece_font_cache = _piece_font()
    return _piece_font_cache


def _hatch_square(draw, px, py):
    sq = _SQ
    for d in range(0, 2 * sq, 3):
        if d < sq:
            draw.line([(px + d, py), (px, py + d)], fill=0)
        else:
            draw.line([(px + sq - 1, py + d - sq + 1),
                       (px + d - sq + 1, py + sq - 1)], fill=0)


def draw_puzzle_board(draw, board: chess.Board, fonts: dict) -> None:
    """Draw the puzzle board (pieces + outline + rank labels) at the standard position."""
    pf = _get_piece_font()
    white_down = (board.turn == chess.WHITE)
    pawn_sz   = config.SIZE_BOARD_PIECE - 1
    pawn_path = next((p for p in config.FONT_PIECE_PATHS if os.path.exists(p)), None)
    pawn_font = (ImageFont.truetype(pawn_path, pawn_sz)
                 if pawn_path else ImageFont.load_default())
    bf = pf if pf else fonts['small']

    for vrank in range(8):
        for vfile in range(8):
            sq = (chess.square(vfile, vrank) if white_down
                  else chess.square(7 - vfile, 7 - vrank))
            px = _BOARD_X0 + vfile * _SQ
            py = _BOARD_Y0 + (7 - vrank) * _SQ
            x1, y1 = px + _SQ - 1, py + _SQ - 1
            if (vfile + vrank) % 2 == 0:
                _hatch_square(draw, px, py)
            piece = board.piece_at(sq)
            if piece:
                cx = (px + x1) // 2 + config.BOARD_PIECE_OFFSET_X
                cy = (py + y1) // 2 + config.BOARD_PIECE_OFFSET_Y
                if piece.color == chess.WHITE:
                    is_pawn  = piece.piece_type == chess.PAWN
                    out_font = pawn_font if is_pawn else bf
                    draw_cy  = cy if is_pawn else cy - 1
                    og = _WHITE_GLYPHS[piece.piece_type]
                    fg = _BLACK_GLYPHS[piece.piece_type]
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        ui.draw_centered(draw, cx + dx, draw_cy + dy, og, out_font, 0)
                    ui.draw_centered(draw, cx, draw_cy, fg, out_font, 255)
                else:
                    ui.draw_centered(draw, cx, cy,
                                     _BLACK_GLYPHS[piece.piece_type], bf, 0)

    draw.rectangle(
        [(_BOARD_X0, _BOARD_Y0),
         (_BOARD_X0 + _BOARD_W - 1, _BOARD_Y0 + _BOARD_W - 1)],
        outline=0,
    )
    sf = fonts['small']
    for vrank in range(8):
        rank_num = (vrank + 1) if white_down else (8 - vrank)
        ly = _BOARD_Y0 + (7 - vrank) * _SQ + _SQ // 2
        ui.draw_centered(draw, _RANK_LABEL_X, ly, str(rank_num), sf, 0)


def _draw_stat(draw, lx: int, cy: int, label: str, value: str, font) -> None:
    """Draw a two-line stat (label above, value below) left-aligned at lx,
    vertically centred around cy using line spacing _STATS_LS."""
    for i, text in enumerate((label, value)):
        bb = draw.textbbox((0, 0), text, font=font)
        y_anc = cy + (i - 1) * _STATS_LS   # i=0 → cy-LS (label), i=1 → cy (value)
        draw.text((lx - bb[0], y_anc - bb[1]), text, font=font, fill=0)


class PuzzleScreen(ui.Screen):
    name = 'puzzle'

    def build(self, board: chess.Board | None,
              puzzle_num: int, total: int,
              solved: int, wrong: int,
              diff_label: str,
              move_num: int = 1, move_total: int = 1,
              last_result: str | None = None) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts

        # ── Right panel header (black fill, white text) ───────────────────────
        draw.line([(ui.VSEP_X, 0), (ui.VSEP_X, ui.H - 1)], fill=0)
        draw.rectangle([(ui.VSEP_X, 0), (ui.W - 1, _HDR_H - 1)], fill=0)

        if board is not None:
            ui.draw_centered(draw, _RCX, _HDR_CY1, f'P#{puzzle_num}', f['title'], 255)
            ui.draw_centered(draw, _RCX, _HDR_CY2,
                             f'{move_num}/{move_total}', f['title'], 255)
        else:
            ui.draw_centered(draw, _RCX, _HDR_CY1, 'No', f['title'], 255)
            ui.draw_centered(draw, _RCX, _HDR_CY2, 'puzzles', f['title'], 255)

        # ── Right panel buttons ───────────────────────────────────────────────
        if board is not None:
            _SOLVE_BTN.draw(draw, f['btn'])
            _SKIP_BTN.draw(draw, f['btn'])
        _END_BTN.draw(draw, f['btn'])

        # ── Left area ─────────────────────────────────────────────────────────
        if board is not None:
            draw_puzzle_board(draw, board, f)

            # Stats column (left of board)
            sf = f['small']
            for (label, value), cy in zip(
                [('Rating:', str(diff_label)),
                 ('Solved:', f'{solved}/{solved + wrong}')],
                _STATS_YS,
            ):
                _draw_stat(draw, _STATS_LX, cy, label, value, sf)

            # 3rd slot: partial-move progress (N✓) or last-puzzle result glyph
            if move_total > 1 and move_num > 1:
                glyph = f'{move_num - 1}✓'   # "N✓"
            else:
                glyph = _RESULT_GLYPHS.get(last_result or '', '')
            if glyph:
                ui.draw_centered(draw, _RESULT_CX, _STATS_YS[2] - 2,
                                 glyph, _get_result_font(), 0)

        else:
            # No-puzzle message centred in the left area
            sf = f['small']
            cy_start = (ui.H - len(_NO_PUZZLE_MSG) * 16) // 2
            for i, line in enumerate(_NO_PUZZLE_MSG):
                ui.draw_centered(draw, ui.VSEP_X // 2, cy_start + i * 16, line, sf, 0)

        return img

    def hit(self, lx: int, ly: int, board_available: bool = True) -> str | None:
        if _END_BTN.hit(lx, ly):
            return 'end'
        if board_available:
            if _SOLVE_BTN.hit(lx, ly):
                return 'solve'
            if _SKIP_BTN.hit(lx, ly):
                return 'skip'
        return None


_screen = PuzzleScreen()


def build_puzzle_screen(board, puzzle_num: int, total: int,
                        solved: int, wrong: int,
                        diff_label: str,
                        move_num: int = 1, move_total: int = 1,
                        last_result: str | None = None) -> Image.Image:
    return _screen.build(board, puzzle_num, total, solved, wrong, diff_label,
                         move_num, move_total, last_result)


def hit_puzzle(lx: int, ly: int, board_available: bool = True) -> str | None:
    return _screen.hit(lx, ly, board_available=board_available)
