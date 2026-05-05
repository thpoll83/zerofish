"""Puzzle screen: board on the left, puzzle info + controls on the right."""

import chess
from PIL import Image, ImageDraw, ImageFont
import ui
import config

# ── Board rendering constants (same formula as screen_board.py) ───────────────
_SQ       = config.BOARD_SQ
_BOARD_W  = 8 * _SQ                                   # 120 px
_BOARD_X0 = (ui.VSEP_X - _BOARD_W) // 2 + config.BOARD_OFFSET_X  # = 36
_BOARD_Y0 = (ui.H - _BOARD_W) // 2 + config.BOARD_OFFSET_Y       # = 1

_WHITE_GLYPHS = {
    chess.PAWN:   '♙', chess.KNIGHT: '♘', chess.BISHOP: '♗',
    chess.ROOK:   '♖', chess.QUEEN:  '♕', chess.KING:   '♔',
}
_BLACK_GLYPHS = {
    chess.PAWN:   '♟', chess.KNIGHT: '♞', chess.BISHOP: '♝',
    chess.ROOK:   '♜', chess.QUEEN:  '♛', chess.KING:   '♚',
}

# ── Stats strip (left of board, x = 0 … _BOARD_X0-2) ─────────────────────────
_STATS_CX  = (_BOARD_X0 - 2) // 2     # horizontal centre ≈ 17
_STATS_YS  = [12, 43, 74, 105]        # y-centres for D / S / W / # lines

# ── Right-panel layout ────────────────────────────────────────────────────────
_HDR_H    = 36                         # height of black header block
_HDR_CY1  = _HDR_H // 4               # = 9   (centre line 1)
_HDR_CY2  = _HDR_H * 3 // 4           # = 27  (centre line 2)
_RX0      = ui.OK_X0                   # = 195
_RX1      = ui.OK_X1                   # = 247
_RCX      = (_RX0 + _RX1) // 2        # = 221

_BTN_Y_SOLVE  = (_HDR_H + 4,  _HDR_H + 4 + 24)   # (y0, y1) = (40, 64)
_BTN_Y_SKIP   = (_HDR_H + 32, _HDR_H + 32 + 24)  # (68, 92)
_BTN_Y_END    = (_HDR_H + 60, _HDR_H + 60 + 24)  # (96, 120)

_SOLVE_BTN = ui.Button((_RX0, _BTN_Y_SOLVE[0], _RX1, _BTN_Y_SOLVE[1]), 'Solve', ui.Button.BAR)
_SKIP_BTN  = ui.Button((_RX0, _BTN_Y_SKIP[0],  _RX1, _BTN_Y_SKIP[1]),  'Skip',  ui.Button.OUTLINE)
_END_BTN   = ui.Button((_RX0, _BTN_Y_END[0],   _RX1, _BTN_Y_END[1]),   'End',   ui.Button.OUTLINE)

_NO_PUZZLE_MSG = ['No puzzles!', 'Run deploy/', 'download_puzzles.py']


def _piece_font() -> ImageFont.FreeTypeFont | None:
    path = next((p for p in config.FONT_PIECE_PATHS
                 if __import__('os').path.exists(p)), None)
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


class PuzzleScreen(ui.Screen):
    name = 'puzzle'

    def build(self, board: chess.Board | None,
              puzzle_num: int, total: int,
              solved: int, wrong: int,
              diff_label: str) -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts
        pf = _get_piece_font()

        # ── Right panel header (black fill, white text) ───────────────────────
        draw.line([(ui.VSEP_X, 0), (ui.VSEP_X, ui.H - 1)], fill=0)
        draw.rectangle([(ui.VSEP_X, 0), (ui.W - 1, _HDR_H - 1)], fill=0)

        if board is not None:
            ui.draw_centered(draw, _RCX, _HDR_CY1, f'P#{puzzle_num}', f['title'], 255)
            mover = 'White' if board.turn == chess.WHITE else 'Black'
            ui.draw_centered(draw, _RCX, _HDR_CY2, mover, f['title'], 255)
        else:
            ui.draw_centered(draw, _RCX, _HDR_CY1, 'No', f['title'], 255)
            ui.draw_centered(draw, _RCX, _HDR_CY2, 'puzzles', f['title'], 255)

        # ── Right panel buttons ───────────────────────────────────────────────
        if board is not None:
            _SOLVE_BTN.draw(draw, f['btn'])
            _SKIP_BTN.draw(draw, f['btn'])
        _END_BTN.draw(draw, f['btn'])

        # ── Left panel: board ─────────────────────────────────────────────────
        if board is not None:
            white_down = (board.turn == chess.WHITE)
            pawn_sz = config.SIZE_BOARD_PIECE - 1
            pawn_path = next((p for p in config.FONT_PIECE_PATHS
                              if __import__('os').path.exists(p)), None)
            pawn_font = (ImageFont.truetype(pawn_path, pawn_sz)
                         if pawn_path else ImageFont.load_default())
            bf = pf if pf else f['small']

            for vrank in range(8):
                for vfile in range(8):
                    if white_down:
                        sq = chess.square(vfile, vrank)
                    else:
                        sq = chess.square(7 - vfile, 7 - vrank)
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

            # ── Stats strip (left of board) ───────────────────────────────────
            sf = f['small']
            labels = [f'D:{diff_label}', f'S:{solved}', f'W:{wrong}', f'#{total}']
            for label, y in zip(labels, _STATS_YS):
                ui.draw_centered(draw, _STATS_CX, y, label, sf, 0)

        else:
            # No-puzzle message centered in left panel
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
                        diff_label: str) -> Image.Image:
    return _screen.build(board, puzzle_num, total, solved, wrong, diff_label)


def hit_puzzle(lx: int, ly: int, board_available: bool = True) -> str | None:
    return _screen.hit(lx, ly, board_available=board_available)
