#!/usr/bin/env python3
"""ZeroFish — chess computer for the WaveShare 2.13" Touch e-Paper HAT V4.

Landscape orientation: hold the device with the short edge at top/bottom
(rotated 90° clockwise from portrait, USB port on the left side).
Score sheet uses portrait orientation (USB at bottom).
"""

import os
import sys
import time
import random
import logging
import threading

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, 'Touch_e-Paper_Code', 'python', 'lib'))

from TP_lib import epd2in13_V4, gt1151
from PIL import Image, ImageDraw, ImageFont
import chess
import chess.engine

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
log = logging.getLogger('zerofish')

VERSION = '0.1'
STOCKFISH_PATH = '/usr/games/stockfish'

W, H = 250, 122   # landscape: 250 wide × 122 tall

_FONT_DIR = os.path.join(_REPO, 'Touch_e-Paper_Code', 'python', 'pic')

_PIECE_FONT_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSerif.ttf',
]

# ── Shared landscape layout ────────────────────────────────────────────────────
TITLE_H = 21

VSEP_X = 192
OK_X0  = 195
OK_X1  = 247
OK_Y0  = TITLE_H + 6      # 27
OK_Y1  = H - 6            # 116

_OK_MID     = OK_Y0 + (OK_Y1 - OK_Y0) // 2
OK_Y1_SPLIT = _OK_MID - 2
SEC_Y0      = _OK_MID + 2
SEC_Y1      = OK_Y1

# ── Difficulty screen ─────────────────────────────────────────────────────────
BTN_MARGIN = 2
BTN_W      = 36
BTN_GAP    = 2
BTN_H      = 38
ROW1_Y     = TITLE_H + 4
ROW2_Y     = ROW1_Y + BTN_H + 4

# ── Color screen ──────────────────────────────────────────────────────────────
COLORS        = ['White', 'Black', 'Random']
COLOR_BTN_GAP = 3
COLOR_BTN_W   = (VSEP_X - 2 - 2 * COLOR_BTN_GAP) // 3
COLOR_BTN_H   = 55
COLOR_BTN_Y0  = TITLE_H + (H - TITLE_H - COLOR_BTN_H) // 2
COLOR_BTN_Y1  = COLOR_BTN_Y0 + COLOR_BTN_H - 1
COLOR_BTN_X   = [2 + i * (COLOR_BTN_W + COLOR_BTN_GAP) for i in range(3)]

# ── Player move input screen ──────────────────────────────────────────────────
PIECES       = ['P', 'N', 'B', 'R', 'Q', 'K']
PIECE_SYMBOLS = ['♟', '♞', '♝', '♜', '♛', '♚']
FILES        = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
RANKS        = ['1', '2', '3', '4', '5', '6', '7', '8']

PM_MARGIN  = 2
PM_GAP     = 2
PM_ROW_H   = 28
PM_ROW1_Y  = TITLE_H + 5
PM_ROW2_Y  = PM_ROW1_Y + PM_ROW_H + 3
PM_ROW3_Y  = PM_ROW2_Y + PM_ROW_H + 3
PM_MAX_X   = VSEP_X - 3
PM_PIECE_W = (PM_MAX_X - PM_MARGIN - 5 * PM_GAP) // 6
PM_FILE_W  = (PM_MAX_X - PM_MARGIN - 7 * PM_GAP) // 8

# ── Promotion screen ──────────────────────────────────────────────────────────
PROMO_GLYPHS      = ['♞', '♝', '♜', '♛']
PROMO_PIECE_TYPES = [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]

PROMO_BTN_W   = 40
PROMO_BTN_H   = 60
PROMO_BTN_GAP = 4
_PROMO_TOT_W  = 4 * PROMO_BTN_W + 3 * PROMO_BTN_GAP
PROMO_BTN_X0  = (VSEP_X - _PROMO_TOT_W) // 2
PROMO_BTN_Y0  = TITLE_H + (H - TITLE_H - PROMO_BTN_H) // 2
PROMO_BTN_Y1  = PROMO_BTN_Y0 + PROMO_BTN_H - 1

# ── In-game menu (2×2 grid) ───────────────────────────────────────────────────
# Button order: 0=Resign  1=Board  (row 0)
#               2=Score   3=Back   (row 1)
IGMENU_BTN_LABELS = ['Resign', 'Board', 'Score', 'Back']
IGMENU_COLS    = 2
IGMENU_BTN_GAP = 4
IGMENU_X0      = 5
IGMENU_X1      = VSEP_X - 5                                    # 187
IGMENU_BTN_W   = (IGMENU_X1 - IGMENU_X0 - IGMENU_BTN_GAP) // 2  # 89
IGMENU_BTN_H   = 46
_IGMENU_TOT_H  = 2 * IGMENU_BTN_H + IGMENU_BTN_GAP             # 96
IGMENU_Y0      = TITLE_H + (H - TITLE_H - _IGMENU_TOT_H) // 2  # 23

# ── Board screen ──────────────────────────────────────────────────────────────
BOARD_SQ = 15                        # square size in pixels
BOARD_PX = 8 * BOARD_SQ             # 120 px — board side length
BOARD_X0 = (VSEP_X - BOARD_PX) // 2 # 36 — left edge of board
BOARD_Y0 = (H - BOARD_PX) // 2      # 1  — top edge of board

# Unicode chess piece glyphs: hollow for white, filled for black
_BOARD_GLYPHS = {
    chess.PAWN:   {chess.WHITE: '♙', chess.BLACK: '♟'},
    chess.KNIGHT: {chess.WHITE: '♘', chess.BLACK: '♞'},
    chess.BISHOP: {chess.WHITE: '♗', chess.BLACK: '♝'},
    chess.ROOK:   {chess.WHITE: '♖', chess.BLACK: '♜'},
    chess.QUEEN:  {chess.WHITE: '♕', chess.BLACK: '♛'},
    chess.KING:   {chess.WHITE: '♔', chess.BLACK: '♚'},
}

# ── Portrait score sheet (122 × 250) ──────────────────────────────────────────
SCORE_W       = 122
SCORE_H       = 250
SCORE_TITLE_H = 21
SCORE_ROW_H   = 13
SCORE_ROWS    = 15
SCORE_BACK_H  = 22
SCORE_BACK_Y0 = SCORE_H - SCORE_BACK_H   # 228
SCORE_BACK_Y1 = SCORE_H - 1              # 249

# ── SAN glyph map (landscape screens only) ────────────────────────────────────
_SAN_TO_GLYPH = {'N': '♞', 'B': '♝', 'R': '♜', 'Q': '♛', 'K': '♚'}

# ── Screens ───────────────────────────────────────────────────────────────────
SCREEN_DIFFICULTY  = 0
SCREEN_COLOR       = 1
SCREEN_THINKING    = 2
SCREEN_SF_MOVE     = 3
SCREEN_PLAYER_MOVE = 4
SCREEN_GAME_OVER   = 5
SCREEN_PROMOTION   = 6
SCREEN_DISAMBIG    = 7
SCREEN_INGAME_MENU = 8
SCREEN_SCORESHEET  = 9
SCREEN_BOARD       = 10
# ─────────────────────────────────────────────────────────────────────────────


def _to_landscape(tx: int, ty: int) -> tuple[int, int]:
    return (249 - ty, tx)


def _hit_ok(lx: int, ly: int, split: bool = False) -> bool:
    y1 = OK_Y1_SPLIT if split else OK_Y1
    return OK_X0 <= lx <= OK_X1 and OK_Y0 <= ly <= y1


def _hit_sec(lx: int, ly: int) -> bool:
    return OK_X0 <= lx <= OK_X1 and SEC_Y0 <= ly <= SEC_Y1


def _load_fonts() -> dict:
    try:
        bold = os.path.join(_FONT_DIR, 'Roboto-Bold.ttf')
        reg  = os.path.join(_FONT_DIR, 'Roboto-Regular.ttf')
        fonts = {
            'title':  ImageFont.truetype(bold, 15),
            'ver':    ImageFont.truetype(reg,  10),
            'btn':    ImageFont.truetype(bold, 14),
            'ok':     ImageFont.truetype(bold, 16),
            'move':   ImageFont.truetype(bold, 42),
            'result': ImageFont.truetype(bold, 28),
            'small':  ImageFont.truetype(reg,  11),
        }
        for path in _PIECE_FONT_PATHS:
            if os.path.exists(path):
                fonts['piece']      = ImageFont.truetype(path, 24)
                fonts['move_piece'] = ImageFont.truetype(path, 42)
                fonts['promo']      = ImageFont.truetype(path, 36)
                fonts['board']      = ImageFont.truetype(path, 10)
                break
        else:
            fonts['piece']      = fonts['btn']
            fonts['move_piece'] = fonts['move']
            fonts['promo']      = fonts['move']
            fonts['board']      = fonts['btn']
        return fonts
    except Exception:
        f = ImageFont.load_default()
        return {k: f for k in (
            'title', 'ver', 'btn', 'ok', 'move', 'result', 'small',
            'piece', 'move_piece', 'promo', 'board',
        )}


def _draw_centered(draw, cx, cy, text, font, fill):
    bb = draw.textbbox((0, 0), text, font=font)
    draw.text(
        (cx - (bb[2] - bb[0]) // 2 - bb[0],
         cy - (bb[3] - bb[1]) // 2 - bb[1]),
        text, font=font, fill=fill,
    )


def _draw_chrome(draw, f, screen_title='', ok_active=False, sec_label=None):
    draw.rectangle([(0, 0), (W - 1, TITLE_H - 1)], fill=0)
    label = f'ZeroFish: {screen_title}' if screen_title else 'ZeroFish'
    draw.text((4, 3), label, font=f['title'], fill=255)
    ver = f'v{VERSION}'
    vw = draw.textbbox((0, 0), ver, font=f['ver'])[2]
    draw.text((W - vw - 4, 5), ver, font=f['ver'], fill=255)

    draw.line([(VSEP_X, TITLE_H), (VSEP_X, H - 1)], fill=0)

    cx    = (OK_X0 + OK_X1) // 2
    ok_y1 = OK_Y1_SPLIT if sec_label else OK_Y1
    ok_cy = (OK_Y0 + ok_y1) // 2
    if ok_active:
        draw.rectangle([(OK_X0, OK_Y0), (OK_X1, ok_y1)], fill=0)
        _draw_centered(draw, cx, ok_cy, 'OK', f['ok'], 255)
    else:
        draw.rectangle([(OK_X0, OK_Y0), (OK_X1, ok_y1)], outline=0)
        _draw_centered(draw, cx, ok_cy, 'OK', f['ok'], 0)

    if sec_label:
        sec_cy = (SEC_Y0 + SEC_Y1) // 2
        draw.rectangle([(OK_X0, SEC_Y0), (OK_X1, SEC_Y1)], outline=0)
        _draw_centered(draw, cx, sec_cy, sec_label, f['btn'], 0)


def _san_with_glyph(san: str) -> str:
    if san and san[0] in _SAN_TO_GLYPH:
        san = _SAN_TO_GLYPH[san[0]] + san[1:]
    eq = san.find('=')
    if eq != -1 and eq + 1 < len(san) and san[eq + 1] in _SAN_TO_GLYPH:
        san = san[:eq + 1] + _SAN_TO_GLYPH[san[eq + 1]] + san[eq + 2:]
    return san


def _move_label(board: chess.Board) -> str:
    n = board.fullmove_number
    return f'#{n}' if board.turn == chess.WHITE else f'…#{n}'


# ── Difficulty screen ─────────────────────────────────────────────────────────

def _diff_rect(level):
    col = (level - 1) % 5
    y0  = ROW1_Y if level <= 5 else ROW2_Y
    x0  = BTN_MARGIN + col * (BTN_W + BTN_GAP)
    return (x0, y0, x0 + BTN_W - 1, y0 + BTN_H - 1)


def _hit_diff(level, lx, ly):
    x0, y0, x1, y1 = _diff_rect(level)
    return x0 <= lx <= x1 and y0 <= ly <= y1


def build_difficulty_screen(selected=None):
    img = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)
    f = _load_fonts()
    _draw_chrome(draw, f, 'Select Difficulty', ok_active=(selected is not None))
    for lvl in range(1, 11):
        x0, y0, x1, y1 = _diff_rect(lvl)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        if lvl == selected:
            draw.rectangle([(x0, y0), (x1, y1)], fill=0)
            _draw_centered(draw, cx, cy, str(lvl), f['btn'], 255)
        else:
            draw.rectangle([(x0, y0), (x1, y1)], outline=0)
            _draw_centered(draw, cx, cy, str(lvl), f['btn'], 0)
    return img


# ── Color screen ──────────────────────────────────────────────────────────────

def _hit_color(idx, lx, ly):
    x0 = COLOR_BTN_X[idx]
    return x0 <= lx <= x0 + COLOR_BTN_W - 1 and COLOR_BTN_Y0 <= ly <= COLOR_BTN_Y1


def build_color_screen(selected=None):
    img = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)
    f = _load_fonts()
    _draw_chrome(draw, f, 'Select Side', ok_active=(selected is not None),
                 sec_label='Back')
    for i, label in enumerate(COLORS):
        x0 = COLOR_BTN_X[i]
        x1 = x0 + COLOR_BTN_W - 1
        cx, cy = (x0 + x1) // 2, (COLOR_BTN_Y0 + COLOR_BTN_Y1) // 2
        if i == selected:
            draw.rectangle([(x0, COLOR_BTN_Y0), (x1, COLOR_BTN_Y1)], fill=0)
            _draw_centered(draw, cx, cy, label, f['btn'], 255)
        else:
            draw.rectangle([(x0, COLOR_BTN_Y0), (x1, COLOR_BTN_Y1)], outline=0)
            _draw_centered(draw, cx, cy, label, f['btn'], 0)
    return img


# ── Thinking screen ───────────────────────────────────────────────────────────

def build_thinking_screen():
    img = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)
    f = _load_fonts()
    _draw_chrome(draw, f, 'Thinking…')
    _draw_centered(draw, VSEP_X // 2, (TITLE_H + H) // 2, '…', f['move'], 0)
    return img


# ── Stockfish move screen ─────────────────────────────────────────────────────

def build_sf_move_screen(san, move_label):
    img = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)
    f = _load_fonts()
    _draw_chrome(draw, f, move_label, ok_active=True)
    cx = VSEP_X // 2
    _draw_centered(draw, cx, (TITLE_H + H) // 2 - 4, _san_with_glyph(san), f['move_piece'], 0)
    return img


# ── Game over screen ──────────────────────────────────────────────────────────

def _game_over_message(board, player_is_white):
    outcome = board.outcome()
    if outcome is None:
        return 'Game Over', board.result()
    term = outcome.termination
    if term == chess.Termination.CHECKMATE:
        return ('You win!' if outcome.winner == player_is_white else 'You lose'), 'Checkmate'
    if term == chess.Termination.STALEMATE:
        return 'Draw', 'Stalemate'
    if term == chess.Termination.INSUFFICIENT_MATERIAL:
        return 'Draw', 'Insuf. material'
    if term in (chess.Termination.FIFTY_MOVES, chess.Termination.SEVENTYFIVE_MOVES):
        return 'Draw', '50-move rule'
    if term in (chess.Termination.THREEFOLD_REPETITION, chess.Termination.FIVEFOLD_REPETITION):
        return 'Draw', 'Repetition'
    return 'Game Over', board.result()


def build_game_over_screen(line1, line2):
    img = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)
    f = _load_fonts()
    _draw_chrome(draw, f, 'Game Over', ok_active=True)
    cx = VSEP_X // 2
    cy = (TITLE_H + H) // 2
    _draw_centered(draw, cx, cy - 14, line1, f['result'], 0)
    if line2:
        _draw_centered(draw, cx, cy + 22, line2, f['small'], 0)
    return img


# ── Player move input screen ──────────────────────────────────────────────────

def _pm_piece_rect(idx):
    x0 = PM_MARGIN + idx * (PM_PIECE_W + PM_GAP)
    return (x0, PM_ROW1_Y, x0 + PM_PIECE_W - 1, PM_ROW1_Y + PM_ROW_H - 1)


def _pm_file_rect(idx):
    x0 = PM_MARGIN + idx * (PM_FILE_W + PM_GAP)
    return (x0, PM_ROW2_Y, x0 + PM_FILE_W - 1, PM_ROW2_Y + PM_ROW_H - 1)


def _pm_rank_rect(idx):
    x0 = PM_MARGIN + idx * (PM_FILE_W + PM_GAP)
    return (x0, PM_ROW3_Y, x0 + PM_FILE_W - 1, PM_ROW3_Y + PM_ROW_H - 1)


def _hit_pm_piece(idx, lx, ly):
    x0, y0, x1, y1 = _pm_piece_rect(idx)
    return x0 <= lx <= x1 and y0 <= ly <= y1


def _hit_pm_file(idx, lx, ly):
    x0, y0, x1, y1 = _pm_file_rect(idx)
    return x0 <= lx <= x1 and y0 <= ly <= y1


def _hit_pm_rank(idx, lx, ly):
    x0, y0, x1, y1 = _pm_rank_rect(idx)
    return x0 <= lx <= x1 and y0 <= ly <= y1


def build_player_move_screen(sel_piece, sel_file, sel_rank, inv_count=0, move_label=''):
    img = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)
    f = _load_fonts()
    ok_ready = (sel_piece is not None and sel_file is not None and sel_rank is not None)
    base = f'Inv:{inv_count} {move_label}' if inv_count else move_label
    _draw_chrome(draw, f, base, ok_active=ok_ready, sec_label='More')

    def _row(items, rects_fn, selected_idx, font=None):
        _f = font or f['btn']
        for i, label in enumerate(items):
            x0, y0, x1, y1 = rects_fn(i)
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            if i == selected_idx:
                draw.rectangle([(x0, y0), (x1, y1)], fill=0)
                _draw_centered(draw, cx, cy, label, _f, 255)
            else:
                draw.rectangle([(x0, y0), (x1, y1)], outline=0)
                _draw_centered(draw, cx, cy, label, _f, 0)

    _row(PIECE_SYMBOLS, _pm_piece_rect, sel_piece, f['piece'])
    _row(FILES,         _pm_file_rect,  sel_file)
    _row(RANKS,         _pm_rank_rect,  sel_rank)
    return img


# ── Promotion screen ──────────────────────────────────────────────────────────

def _promo_rect(idx):
    x0 = PROMO_BTN_X0 + idx * (PROMO_BTN_W + PROMO_BTN_GAP)
    return (x0, PROMO_BTN_Y0, x0 + PROMO_BTN_W - 1, PROMO_BTN_Y1)


def _hit_promo(idx, lx, ly):
    x0, y0, x1, y1 = _promo_rect(idx)
    return x0 <= lx <= x1 and y0 <= ly <= y1


def build_promotion_screen(selected=None, move_label=''):
    img = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)
    f = _load_fonts()
    _draw_chrome(draw, f, f'Promote {move_label}', ok_active=(selected is not None))
    for i, glyph in enumerate(PROMO_GLYPHS):
        x0, y0, x1, y1 = _promo_rect(i)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        if i == selected:
            draw.rectangle([(x0, y0), (x1, y1)], fill=0)
            _draw_centered(draw, cx, cy, glyph, f['promo'], 255)
        else:
            draw.rectangle([(x0, y0), (x1, y1)], outline=0)
            _draw_centered(draw, cx, cy, glyph, f['promo'], 0)
    return img


# ── Disambiguation screen ─────────────────────────────────────────────────────

def _disambig_rects(n):
    gap   = 8
    btn_w = min(70, (VSEP_X - 10 - (n - 1) * gap) // n)
    btn_h = 50
    total = n * btn_w + (n - 1) * gap
    x0    = (VSEP_X - total) // 2
    y0    = TITLE_H + (H - TITLE_H - btn_h) // 2
    return [(x0 + i * (btn_w + gap), y0,
             x0 + i * (btn_w + gap) + btn_w - 1, y0 + btn_h - 1)
            for i in range(n)]


def _hit_disambig(idx, rects, lx, ly):
    x0, y0, x1, y1 = rects[idx]
    return x0 <= lx <= x1 and y0 <= ly <= y1


def build_disambig_screen(labels, rects, selected=None, move_label=''):
    img = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)
    f = _load_fonts()
    _draw_chrome(draw, f, f'Which? {move_label}', ok_active=(selected is not None))
    for i, label in enumerate(labels):
        x0, y0, x1, y1 = rects[i]
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        if i == selected:
            draw.rectangle([(x0, y0), (x1, y1)], fill=0)
            _draw_centered(draw, cx, cy, label, f['piece'], 255)
        else:
            draw.rectangle([(x0, y0), (x1, y1)], outline=0)
            _draw_centered(draw, cx, cy, label, f['piece'], 0)
    return img


# ── In-game menu screen (2×2) ─────────────────────────────────────────────────

def _igmenu_rect(idx):
    col = idx % IGMENU_COLS
    row = idx // IGMENU_COLS
    x0  = IGMENU_X0 + col * (IGMENU_BTN_W + IGMENU_BTN_GAP)
    y0  = IGMENU_Y0 + row * (IGMENU_BTN_H + IGMENU_BTN_GAP)
    return (x0, y0, x0 + IGMENU_BTN_W - 1, y0 + IGMENU_BTN_H - 1)


def _hit_igmenu(idx, lx, ly):
    x0, y0, x1, y1 = _igmenu_rect(idx)
    return x0 <= lx <= x1 and y0 <= ly <= y1


def build_ingame_menu_screen(move_label=''):
    img = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)
    f = _load_fonts()
    _draw_chrome(draw, f, move_label or 'Menu')
    for i, label in enumerate(IGMENU_BTN_LABELS):
        x0, y0, x1, y1 = _igmenu_rect(i)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        draw.rectangle([(x0, y0), (x1, y1)], outline=0)
        _draw_centered(draw, cx, cy, label, f['btn'], 0)
    return img


# ── Board screen ──────────────────────────────────────────────────────────────

def build_board_screen(board, player_is_white=True):
    """Full-width chessboard in landscape; no title bar; Back button on right."""
    img = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)
    f = _load_fonts()

    # Right panel: separator + Back button
    draw.line([(VSEP_X, 0), (VSEP_X, H - 1)], fill=0)
    draw.rectangle([(OK_X0, 6), (OK_X1, H - 6)], outline=0)
    _draw_centered(draw, (OK_X0 + OK_X1) // 2, H // 2, 'Back', f['btn'], 0)

    # Chessboard — show from player's perspective
    SQ = BOARD_SQ
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
            if is_dark:
                draw.rectangle([(px, py), (x1, y1)], fill=0)
            else:
                draw.rectangle([(px, py), (x1, y1)], fill=255, outline=0)

            piece = board.piece_at(sq)
            if piece:
                glyph = _BOARD_GLYPHS[piece.piece_type][piece.color]
                fill  = 255 if is_dark else 0
                _draw_centered(draw, (px + x1) // 2, (py + y1) // 2,
                               glyph, f['board'], fill)

    return img


def _hit_board_back(lx, ly):
    return lx > VSEP_X


# ── Score sheet screen (portrait 122 × 250) ───────────────────────────────────

def build_scoresheet_screen(move_history, move_label=''):
    """Portrait image — raw SAN, no glyphs (unreadable at small size)."""
    img = Image.new('1', (SCORE_W, SCORE_H), 255)
    draw = ImageDraw.Draw(img)
    f = _load_fonts()

    draw.rectangle([(0, 0), (SCORE_W - 1, SCORE_TITLE_H - 1)], fill=0)
    title = f'Score {move_label}' if move_label else 'Score Sheet'
    _draw_centered(draw, SCORE_W // 2, SCORE_TITLE_H // 2, title, f['title'], 255)

    draw.rectangle([(2, SCORE_BACK_Y0), (SCORE_W - 3, SCORE_BACK_Y1)], outline=0)
    _draw_centered(draw, SCORE_W // 2, (SCORE_BACK_Y0 + SCORE_BACK_Y1) // 2,
                   'Back', f['btn'], 0)

    total = len(move_history)
    start = max(0, total - SCORE_ROWS * 2)
    if start % 2 == 1:
        start -= 1
    recent = move_history[start:]
    start_full = start // 2 + 1

    y = SCORE_TITLE_H + 3
    for j in range(0, len(recent), 2):
        full_num = start_full + j // 2
        w = recent[j]                              if j     < len(recent) else ''
        b = recent[j + 1]                          if j + 1 < len(recent) else ''
        draw.text((2, y), f'{full_num}. {w}  {b}', font=f['small'], fill=0)
        y += SCORE_ROW_H
        if y >= SCORE_BACK_Y0 - 4:
            break

    return img


def _hit_scoresheet_back(tx, ty):
    return 0 <= tx <= SCORE_W - 1 and SCORE_BACK_Y0 <= ty <= SCORE_BACK_Y1


# ── Game logic ────────────────────────────────────────────────────────────────

def _skill_level(difficulty):
    return round((difficulty - 1) * 20 / 9)


# Time budget per move, scaled by difficulty.
# Difficulties 1-5 stay at 1 s; 6-10 scale up with no artificial ceiling
# at the top end (60 s ≈ effectively unlimited for a human-paced game).
_THINK_SECONDS = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0,
                  6: 3.0, 7: 5.0, 8: 10.0, 9: 20.0, 10: 60.0}


def _think_limit(difficulty):
    return chess.engine.Limit(time=_THINK_SECONDS.get(difficulty, 1.0))


def _find_candidates(board, piece_idx, file_idx, rank_idx, promo_idx=None):
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


def _needs_promotion(board, piece_idx, file_idx, rank_idx) -> bool:
    if piece_idx != 0:
        return False
    target = chess.square(file_idx, rank_idx)
    return any(
        board.piece_type_at(m.from_square) == chess.PAWN
        and m.to_square == target
        and m.promotion is not None
        for m in board.legal_moves
    )


# ── Display helpers ───────────────────────────────────────────────────────────

def _transition(epd, img, partial_count):
    epd.init(epd.FULL_UPDATE)
    epd.displayPartBaseImage(epd.getbuffer(img))
    epd.init(epd.PART_UPDATE)
    partial_count[0] = 0


def _show(epd, img, partial_count):
    buf = epd.getbuffer(img)
    partial_count[0] += 1
    if partial_count[0] % 5 == 0:
        log.info('Full refresh to clear ghosting')
        epd.init(epd.FULL_UPDATE)
        epd.displayPartBaseImage(buf)
        epd.init(epd.PART_UPDATE)
    else:
        epd.displayPartial_Wait(buf)


def _push_and_continue(board, move, move_history, engine, think_limit,
                        epd, partial_count, player_is_white, inv_count, cur_move_label):
    """Push player move → check game over → Stockfish reply.
    Returns (new_screen, new_move_label).
    """
    san = board.san(move)
    board.push(move)
    move_history.append(san)
    log.info('Player: %s', san)

    if board.is_game_over():
        log.info('Game over: %s', board.result())
        line1, line2 = _game_over_message(board, player_is_white)
        _transition(epd, build_game_over_screen(line1, line2), partial_count)
        return SCREEN_GAME_OVER, cur_move_label

    sf_label = _move_label(board)
    _transition(epd, build_thinking_screen(), partial_count)
    result  = engine.play(board, think_limit)
    sf_san  = board.san(result.move)
    board.push(result.move)
    move_history.append(sf_san)
    log.info('Stockfish: %s', sf_san)
    _transition(epd, build_sf_move_screen(sf_san, sf_label), partial_count)
    return SCREEN_SF_MOVE, sf_label


def _reset_game_state():
    """Return a dict of zeroed game-state variables for a new game."""
    return dict(board=None, engine=None, inv_count=0, move_history=[],
                cur_move_label='', sel_piece=None, sel_file=None, sel_rank=None,
                prom_piece=None, prom_file=None, prom_rank=None, sel_promo=None,
                disambig_candidates=[], disambig_labels=[], disambig_rects=[],
                sel_disambig=None)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    epd = epd2in13_V4.EPD()
    gt  = gt1151.GT1151()
    dev = gt1151.GT_Development()
    old = gt1151.GT_Development()

    log.info('ZeroFish v%s starting', VERSION)

    epd.init(epd.FULL_UPDATE)
    gt.GT_Init()
    epd.Clear(0xFF)
    epd.displayPartBaseImage(epd.getbuffer(build_difficulty_screen()))
    epd.init(epd.PART_UPDATE)

    screen        = SCREEN_DIFFICULTY
    diff_sel      = None
    color_sel     = None
    partial_count = [0]

    # Game state
    board               = None
    engine              = None
    think_limit         = chess.engine.Limit(time=1.0)
    player_is_white     = True
    sel_piece           = None
    sel_file            = None
    sel_rank            = None
    inv_count           = 0
    cur_move_label      = ''
    move_history        = []
    prom_piece          = prom_file = prom_rank = None
    sel_promo           = None
    disambig_candidates = []
    disambig_labels     = []
    disambig_rects      = []
    sel_disambig        = None

    running = True
    def irq_poll():
        while running:
            dev.Touch = 1 if gt.digital_read(gt.INT) == 0 else 0
    threading.Thread(target=irq_poll, daemon=True).start()

    log.info('Ready')

    try:
        while True:
            had_irq = (dev.Touch == 1)
            gt.GT_Scan(dev, old)

            same_coords = (old.X[0] == dev.X[0]
                           and old.Y[0] == dev.Y[0]
                           and old.S[0] == dev.S[0])
            if same_coords:
                if had_irq and not dev.TouchpointFlag:
                    old.X[0] = old.Y[0] = old.S[0] = 0
                    dev.X[0] = dev.Y[0] = dev.S[0] = 0
                time.sleep(0.01)
                continue
            if not dev.TouchpointFlag:
                time.sleep(0.01)
                continue

            dev.TouchpointFlag = 0

            lx, ly = _to_landscape(dev.X[0], dev.Y[0])   # landscape coords
            tx, ty = dev.X[0], dev.Y[0]                   # portrait / raw

            # ── Difficulty ────────────────────────────────────────────────────
            if screen == SCREEN_DIFFICULTY:
                for lvl in range(1, 11):
                    if _hit_diff(lvl, lx, ly) and lvl != diff_sel:
                        diff_sel = lvl
                        _show(epd, build_difficulty_screen(diff_sel), partial_count)
                        break
                if _hit_ok(lx, ly) and diff_sel is not None:
                    screen = SCREEN_COLOR
                    color_sel = None
                    _transition(epd, build_color_screen(), partial_count)

            # ── Side selection ────────────────────────────────────────────────
            elif screen == SCREEN_COLOR:
                if _hit_sec(lx, ly):
                    screen = SCREEN_DIFFICULTY
                    _transition(epd, build_difficulty_screen(diff_sel), partial_count)
                else:
                    for i in range(len(COLORS)):
                        if _hit_color(i, lx, ly) and i != color_sel:
                            color_sel = i
                            _show(epd, build_color_screen(color_sel), partial_count)
                            break
                    if _hit_ok(lx, ly, split=True) and color_sel is not None:
                        if color_sel == 2:
                            player_is_white = random.choice([True, False])
                        else:
                            player_is_white = (color_sel == 0)
                        log.info('Starting — player %s, diff %d',
                                 'White' if player_is_white else 'Black', diff_sel)
                        board        = chess.Board()
                        inv_count    = 0
                        move_history = []
                        engine       = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
                        engine.configure({'Skill Level': _skill_level(diff_sel)})
                        think_limit  = _think_limit(diff_sel)
                        log.info('Think limit: %.1fs', _THINK_SECONDS.get(diff_sel, 1.0))

                        if player_is_white:
                            cur_move_label = _move_label(board)
                            sel_piece = sel_file = sel_rank = None
                            screen = SCREEN_PLAYER_MOVE
                            _transition(epd,
                                        build_player_move_screen(None, None, None, 0,
                                                                  cur_move_label),
                                        partial_count)
                        else:
                            sf_label = _move_label(board)
                            _transition(epd, build_thinking_screen(), partial_count)
                            result = engine.play(board, think_limit)
                            sf_san = board.san(result.move)
                            board.push(result.move)
                            move_history.append(sf_san)
                            log.info('Stockfish: %s', sf_san)
                            cur_move_label = sf_label
                            screen = SCREEN_SF_MOVE
                            _transition(epd,
                                        build_sf_move_screen(sf_san, sf_label),
                                        partial_count)

            # ── Stockfish move ────────────────────────────────────────────────
            elif screen == SCREEN_SF_MOVE:
                if _hit_ok(lx, ly):
                    if board.is_game_over():
                        line1, line2 = _game_over_message(board, player_is_white)
                        screen = SCREEN_GAME_OVER
                        _transition(epd, build_game_over_screen(line1, line2), partial_count)
                    else:
                        cur_move_label = _move_label(board)
                        sel_piece = sel_file = sel_rank = None
                        screen = SCREEN_PLAYER_MOVE
                        _transition(epd,
                                    build_player_move_screen(None, None, None,
                                                              inv_count, cur_move_label),
                                    partial_count)

            # ── Player move input ─────────────────────────────────────────────
            elif screen == SCREEN_PLAYER_MOVE:
                if _hit_sec(lx, ly):
                    screen = SCREEN_INGAME_MENU
                    _transition(epd, build_ingame_menu_screen(cur_move_label), partial_count)
                else:
                    changed = False
                    for i in range(len(PIECES)):
                        if _hit_pm_piece(i, lx, ly) and i != sel_piece:
                            sel_piece = i; changed = True; break
                    if not changed:
                        for i in range(len(FILES)):
                            if _hit_pm_file(i, lx, ly) and i != sel_file:
                                sel_file = i; changed = True; break
                    if not changed:
                        for i in range(len(RANKS)):
                            if _hit_pm_rank(i, lx, ly) and i != sel_rank:
                                sel_rank = i; changed = True; break

                    if changed:
                        _show(epd,
                              build_player_move_screen(sel_piece, sel_file, sel_rank,
                                                        inv_count, cur_move_label),
                              partial_count)
                    elif (_hit_ok(lx, ly, split=True)
                            and sel_piece is not None
                            and sel_file  is not None
                            and sel_rank  is not None):
                        if _needs_promotion(board, sel_piece, sel_file, sel_rank):
                            prom_piece, prom_file, prom_rank = sel_piece, sel_file, sel_rank
                            sel_promo = None
                            screen = SCREEN_PROMOTION
                            _transition(epd, build_promotion_screen(None, cur_move_label),
                                        partial_count)
                        else:
                            candidates = _find_candidates(board, sel_piece, sel_file, sel_rank)
                            if not candidates:
                                inv_count += 1
                                sel_piece = sel_file = sel_rank = None
                                _show(epd,
                                      build_player_move_screen(None, None, None,
                                                                inv_count, cur_move_label),
                                      partial_count)
                            elif len(candidates) == 1:
                                screen, cur_move_label = _push_and_continue(
                                    board, candidates[0], move_history, engine,
                                    think_limit, epd, partial_count,
                                    player_is_white, inv_count, cur_move_label)
                                if screen == SCREEN_PLAYER_MOVE:
                                    sel_piece = sel_file = sel_rank = None
                            else:
                                disambig_candidates = candidates
                                disambig_labels = [
                                    PIECE_SYMBOLS[sel_piece]
                                    + chess.square_name(m.from_square)
                                    for m in candidates
                                ]
                                disambig_rects = _disambig_rects(len(candidates))
                                sel_disambig = None
                                screen = SCREEN_DISAMBIG
                                _transition(epd,
                                            build_disambig_screen(disambig_labels,
                                                                   disambig_rects,
                                                                   None, cur_move_label),
                                            partial_count)

            # ── Pawn promotion ────────────────────────────────────────────────
            elif screen == SCREEN_PROMOTION:
                changed = False
                for i in range(4):
                    if _hit_promo(i, lx, ly) and i != sel_promo:
                        sel_promo = i; changed = True; break
                if changed:
                    _show(epd, build_promotion_screen(sel_promo, cur_move_label),
                          partial_count)
                elif _hit_ok(lx, ly) and sel_promo is not None:
                    candidates = _find_candidates(board, prom_piece, prom_file,
                                                   prom_rank, sel_promo)
                    if not candidates:
                        log.warning('Promotion move not found')
                        sel_promo = None
                        _show(epd, build_promotion_screen(None, cur_move_label),
                              partial_count)
                    elif len(candidates) == 1:
                        sel_piece = sel_file = sel_rank = None
                        prom_piece = prom_file = prom_rank = sel_promo = None
                        screen, cur_move_label = _push_and_continue(
                            board, candidates[0], move_history, engine,
                            think_limit, epd, partial_count,
                            player_is_white, inv_count, cur_move_label)
                    else:
                        disambig_candidates = candidates
                        disambig_labels = [
                            PIECE_SYMBOLS[prom_piece]
                            + chess.square_name(m.from_square)
                            for m in candidates
                        ]
                        disambig_rects = _disambig_rects(len(candidates))
                        sel_disambig = None
                        prom_piece = prom_file = prom_rank = sel_promo = None
                        screen = SCREEN_DISAMBIG
                        _transition(epd,
                                    build_disambig_screen(disambig_labels,
                                                           disambig_rects,
                                                           None, cur_move_label),
                                    partial_count)

            # ── Disambiguation ────────────────────────────────────────────────
            elif screen == SCREEN_DISAMBIG:
                changed = False
                for i in range(len(disambig_candidates)):
                    if _hit_disambig(i, disambig_rects, lx, ly) and i != sel_disambig:
                        sel_disambig = i; changed = True; break
                if changed:
                    _show(epd,
                          build_disambig_screen(disambig_labels, disambig_rects,
                                                 sel_disambig, cur_move_label),
                          partial_count)
                elif _hit_ok(lx, ly) and sel_disambig is not None:
                    move = disambig_candidates[sel_disambig]
                    sel_disambig = None
                    sel_piece = sel_file = sel_rank = None
                    screen, cur_move_label = _push_and_continue(
                        board, move, move_history, engine,
                        think_limit, epd, partial_count,
                        player_is_white, inv_count, cur_move_label)

            # ── In-game menu (2×2) ────────────────────────────────────────────
            elif screen == SCREEN_INGAME_MENU:
                if _hit_igmenu(0, lx, ly):       # Resign → game over screen
                    log.info('Player resigned')
                    screen = SCREEN_GAME_OVER
                    _transition(epd, build_game_over_screen('Resigned', ''), partial_count)

                elif _hit_igmenu(1, lx, ly):      # Board
                    screen = SCREEN_BOARD
                    _transition(epd, build_board_screen(board, player_is_white),
                                partial_count)

                elif _hit_igmenu(2, lx, ly):      # Score sheet
                    screen = SCREEN_SCORESHEET
                    _transition(epd,
                                build_scoresheet_screen(move_history, cur_move_label),
                                partial_count)

                elif _hit_igmenu(3, lx, ly):      # Back → player move
                    screen = SCREEN_PLAYER_MOVE
                    _transition(epd,
                                build_player_move_screen(sel_piece, sel_file, sel_rank,
                                                          inv_count, cur_move_label),
                                partial_count)

            # ── Board display ─────────────────────────────────────────────────
            elif screen == SCREEN_BOARD:
                if _hit_board_back(lx, ly):
                    screen = SCREEN_INGAME_MENU
                    _transition(epd, build_ingame_menu_screen(cur_move_label), partial_count)

            # ── Score sheet (portrait) ────────────────────────────────────────
            elif screen == SCREEN_SCORESHEET:
                if _hit_scoresheet_back(tx, ty):
                    screen = SCREEN_INGAME_MENU
                    _transition(epd, build_ingame_menu_screen(cur_move_label), partial_count)

            # ── Game over ─────────────────────────────────────────────────────
            elif screen == SCREEN_GAME_OVER:
                if _hit_ok(lx, ly):
                    if engine:
                        engine.quit()
                        engine = None
                    board        = None
                    inv_count    = 0
                    move_history = []
                    diff_sel     = None
                    color_sel    = None
                    sel_piece    = sel_file = sel_rank = None
                    screen = SCREEN_DIFFICULTY
                    _transition(epd, build_difficulty_screen(), partial_count)

            time.sleep(0.1)

    except KeyboardInterrupt:
        log.info('Shutting down')
    finally:
        running = False
        if engine:
            engine.quit()
        epd.sleep()
        time.sleep(2)
        epd.Dev_exit()


if __name__ == '__main__':
    main()
