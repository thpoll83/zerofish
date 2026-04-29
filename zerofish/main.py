#!/usr/bin/env python3
"""ZeroFish — chess computer for the WaveShare 2.13" Touch e-Paper HAT V4.

Landscape orientation: hold the device with the short edge at top/bottom
(rotated 90° clockwise from portrait, USB port on the left side).
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

# Landscape: 250 wide × 122 tall (device rotated 90° CW from portrait)
W, H = 250, 122

_FONT_DIR = os.path.join(_REPO, 'Touch_e-Paper_Code', 'python', 'pic')

# System fonts that include Unicode chess piece glyphs (♟♞♝♜♛♚)
_PIECE_FONT_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSerif.ttf',
]

# ── Shared layout ─────────────────────────────────────────────────────────────
TITLE_H = 21

VSEP_X = 192
OK_X0  = 195
OK_X1  = 247
OK_Y0  = TITLE_H + 6
OK_Y1  = H - 6

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
PIECES = ['P', 'N', 'B', 'R', 'Q', 'K']
# Filled Unicode chess glyphs — one per piece, same order as PIECES
PIECE_SYMBOLS = ['♟', '♞', '♝', '♜', '♛', '♚']
FILES  = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
RANKS  = ['1', '2', '3', '4', '5', '6', '7', '8']

PM_MARGIN  = 2
PM_GAP     = 2
PM_ROW_H   = 28
PM_ROW1_Y  = TITLE_H + 5                      # pieces
PM_ROW2_Y  = PM_ROW1_Y + PM_ROW_H + 3         # files
PM_ROW3_Y  = PM_ROW2_Y + PM_ROW_H + 3         # ranks

# 3 px clearance so buttons never touch the vertical separator
PM_MAX_X   = VSEP_X - 3

# 6 piece buttons
PM_PIECE_W = (PM_MAX_X - PM_MARGIN - 5 * PM_GAP) // 6

# 8 file/rank buttons
PM_FILE_W  = (PM_MAX_X - PM_MARGIN - 7 * PM_GAP) // 8

# ── Screens ───────────────────────────────────────────────────────────────────
SCREEN_DIFFICULTY  = 0
SCREEN_COLOR       = 1
SCREEN_THINKING    = 2
SCREEN_SF_MOVE     = 3
SCREEN_PLAYER_MOVE = 4
SCREEN_GAME_OVER   = 5
# ─────────────────────────────────────────────────────────────────────────────


def _to_landscape(tx: int, ty: int) -> tuple[int, int]:
    return (249 - ty, tx)


def _hit_ok(lx: int, ly: int) -> bool:
    return OK_X0 <= lx <= OK_X1 and OK_Y0 <= ly <= OK_Y1


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
                fonts['piece'] = ImageFont.truetype(path, 20)
                break
        else:
            fonts['piece'] = fonts['btn']
        return fonts
    except Exception:
        f = ImageFont.load_default()
        return {k: f for k in ('title', 'ver', 'btn', 'ok', 'move', 'result', 'small', 'piece')}


def _draw_centered(draw, cx, cy, text, font, fill):
    bb = draw.textbbox((0, 0), text, font=font)
    draw.text(
        (cx - (bb[2] - bb[0]) // 2 - bb[0],
         cy - (bb[3] - bb[1]) // 2 - bb[1]),
        text, font=font, fill=fill,
    )


def _draw_chrome(draw, f, screen_title='', ok_active=False):
    draw.rectangle([(0, 0), (W - 1, TITLE_H - 1)], fill=0)
    label = f'ZeroFish: {screen_title}' if screen_title else 'ZeroFish'
    draw.text((4, 3), label, font=f['title'], fill=255)
    ver = f'v{VERSION}'
    vw = draw.textbbox((0, 0), ver, font=f['ver'])[2]
    draw.text((W - vw - 4, 5), ver, font=f['ver'], fill=255)

    draw.line([(VSEP_X, TITLE_H), (VSEP_X, H - 1)], fill=0)

    cx = (OK_X0 + OK_X1) // 2
    cy = (OK_Y0 + OK_Y1) // 2
    if ok_active:
        draw.rectangle([(OK_X0, OK_Y0), (OK_X1, OK_Y1)], fill=0)
        _draw_centered(draw, cx, cy, 'OK', f['ok'], 255)
    else:
        draw.rectangle([(OK_X0, OK_Y0), (OK_X1, OK_Y1)], outline=0)
        _draw_centered(draw, cx, cy, 'OK', f['ok'], 0)


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
    _draw_chrome(draw, f, 'Select Side', ok_active=(selected is not None))
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
    _draw_chrome(draw, f, 'Thinking…', ok_active=False)
    _draw_centered(draw, VSEP_X // 2, (TITLE_H + H) // 2, '…', f['move'], 0)
    return img


# ── Stockfish move screen ─────────────────────────────────────────────────────

def build_sf_move_screen(san, move_num):
    img = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)
    f = _load_fonts()
    _draw_chrome(draw, f, 'Stockfish', ok_active=True)

    cx = VSEP_X // 2
    # Large move notation, centred in content area
    _draw_centered(draw, cx, (TITLE_H + H) // 2 - 4, san, f['move'], 0)
    # Small move number at bottom left
    draw.text((4, H - 14), f'move {move_num}', font=f['small'], fill=0)
    return img


# ── Game over screen ──────────────────────────────────────────────────────────

def _game_over_message(board, player_is_white):
    outcome = board.outcome()
    if outcome is None:
        return 'Game Over', board.result()
    term = outcome.termination
    if term == chess.Termination.CHECKMATE:
        line1 = 'You win!' if (outcome.winner == player_is_white) else 'You lose'
        return line1, 'Checkmate'
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
    _draw_centered(draw, cx, cy + 22, line2, f['small'],  0)
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


def build_player_move_screen(sel_piece, sel_file, sel_rank, inv_count=0):
    """sel_piece/file/rank are indices (int) or None."""
    img = Image.new('1', (W, H), 255)
    draw = ImageDraw.Draw(img)
    f = _load_fonts()
    ok_ready = (sel_piece is not None and sel_file is not None and sel_rank is not None)
    title = f'Your Move Inv:{inv_count}' if inv_count else 'Your Move'
    _draw_chrome(draw, f, title, ok_active=ok_ready)

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


# ── Game logic ────────────────────────────────────────────────────────────────

def _skill_level(difficulty):
    return round((difficulty - 1) * 20 / 9)


def _find_move(board, piece_idx, file_idx, rank_idx):
    """Return the unique legal move for piece+target, or None."""
    piece_type = [chess.PAWN, chess.KNIGHT, chess.BISHOP,
                  chess.ROOK, chess.QUEEN, chess.KING][piece_idx]
    target = chess.square(file_idx, rank_idx)

    matches = []
    for m in board.legal_moves:
        if board.piece_type_at(m.from_square) != piece_type:
            continue
        if m.to_square != target:
            continue
        # Skip non-queen pawn promotions
        if m.promotion and m.promotion != chess.QUEEN:
            continue
        matches.append(m)

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        log.warning('Ambiguous move — taking first match')
        return matches[0]
    return None


# ── Display helpers ───────────────────────────────────────────────────────────

def _transition(epd, img, partial_count):
    """Full refresh — used for every screen change."""
    epd.init(epd.FULL_UPDATE)
    epd.displayPartBaseImage(epd.getbuffer(img))
    epd.init(epd.PART_UPDATE)
    partial_count[0] = 0


def _show(epd, img, partial_count):
    """Partial refresh with periodic full refresh to clear ghosting."""
    buf = epd.getbuffer(img)
    partial_count[0] += 1
    if partial_count[0] % 5 == 0:
        log.info('Full refresh to clear ghosting')
        epd.init(epd.FULL_UPDATE)
        epd.displayPartBaseImage(buf)
        epd.init(epd.PART_UPDATE)
    else:
        epd.displayPartial_Wait(buf)


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

    screen         = SCREEN_DIFFICULTY
    diff_sel       = None
    color_sel      = None
    partial_count  = [0]

    # Game state (set after setup screens)
    board           = None
    engine          = None
    player_is_white = True
    sel_piece       = None
    sel_file        = None
    sel_rank        = None
    inv_count       = 0

    running = True
    def irq_poll():
        while running:
            dev.Touch = 1 if gt.digital_read(gt.INT) == 0 else 0
    threading.Thread(target=irq_poll, daemon=True).start()

    log.info('Ready')

    try:
        while True:
            gt.GT_Scan(dev, old)
            if (old.X[0] == dev.X[0] and old.Y[0] == dev.Y[0]
                    and old.S[0] == dev.S[0]):
                continue
            if not dev.TouchpointFlag:
                continue
            dev.TouchpointFlag = 0

            lx, ly = _to_landscape(dev.X[0], dev.Y[0])

            # ── Setup: difficulty ─────────────────────────────────────────────
            if screen == SCREEN_DIFFICULTY:
                for lvl in range(1, 11):
                    if _hit_diff(lvl, lx, ly) and lvl != diff_sel:
                        diff_sel = lvl
                        log.info('Difficulty → %d', diff_sel)
                        _show(epd, build_difficulty_screen(diff_sel), partial_count)
                        break
                if _hit_ok(lx, ly) and diff_sel is not None:
                    screen = SCREEN_COLOR
                    color_sel = None
                    _transition(epd, build_color_screen(), partial_count)

            # ── Setup: side ───────────────────────────────────────────────────
            elif screen == SCREEN_COLOR:
                for i in range(len(COLORS)):
                    if _hit_color(i, lx, ly) and i != color_sel:
                        color_sel = i
                        log.info('Side → %s', COLORS[color_sel])
                        _show(epd, build_color_screen(color_sel), partial_count)
                        break
                if _hit_ok(lx, ly) and color_sel is not None:
                    # ── Start game ─────────────────────────────────────────
                    if color_sel == 2:  # Random
                        player_is_white = random.choice([True, False])
                    else:
                        player_is_white = (color_sel == 0)
                    log.info('Starting game — player is %s, difficulty %d',
                             'White' if player_is_white else 'Black', diff_sel)

                    board     = chess.Board()
                    inv_count = 0
                    engine    = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
                    engine.configure({'Skill Level': _skill_level(diff_sel)})

                    if player_is_white:
                        # Player moves first
                        sel_piece = sel_file = sel_rank = None
                        screen = SCREEN_PLAYER_MOVE
                        _transition(epd, build_player_move_screen(None, None, None, inv_count),
                                    partial_count)
                    else:
                        # Stockfish moves first
                        _transition(epd, build_thinking_screen(), partial_count)
                        result  = engine.play(board, chess.engine.Limit(time=1.0))
                        sf_san  = board.san(result.move)
                        board.push(result.move)
                        log.info('Stockfish: %s', sf_san)
                        screen = SCREEN_SF_MOVE
                        _transition(epd, build_sf_move_screen(sf_san, board.fullmove_number),
                                    partial_count)

            # ── Stockfish move — wait for player to confirm ───────────────────
            elif screen == SCREEN_SF_MOVE:
                if _hit_ok(lx, ly):
                    if board.is_game_over():
                        line1, line2 = _game_over_message(board, player_is_white)
                        screen = SCREEN_GAME_OVER
                        _transition(epd, build_game_over_screen(line1, line2), partial_count)
                    else:
                        sel_piece = sel_file = sel_rank = None
                        screen = SCREEN_PLAYER_MOVE
                        _transition(epd, build_player_move_screen(None, None, None, inv_count),
                                    partial_count)

            # ── Player move input ─────────────────────────────────────────────
            elif screen == SCREEN_PLAYER_MOVE:
                changed = False
                for i in range(len(PIECES)):
                    if _hit_pm_piece(i, lx, ly) and i != sel_piece:
                        sel_piece = i
                        changed = True
                        break
                if not changed:
                    for i in range(len(FILES)):
                        if _hit_pm_file(i, lx, ly) and i != sel_file:
                            sel_file = i
                            changed = True
                            break
                if not changed:
                    for i in range(len(RANKS)):
                        if _hit_pm_rank(i, lx, ly) and i != sel_rank:
                            sel_rank = i
                            changed = True
                            break
                if changed:
                    _show(epd, build_player_move_screen(sel_piece, sel_file, sel_rank, inv_count),
                          partial_count)

                if (_hit_ok(lx, ly)
                        and sel_piece is not None
                        and sel_file  is not None
                        and sel_rank  is not None):
                    move = _find_move(board, sel_piece, sel_file, sel_rank)
                    if move is None:
                        log.warning('Illegal move: %s%s%s — try again',
                                    PIECES[sel_piece], FILES[sel_file], RANKS[sel_rank])
                        inv_count += 1
                        sel_piece = sel_file = sel_rank = None
                        _show(epd, build_player_move_screen(None, None, None, inv_count),
                              partial_count)
                    else:
                        player_san = board.san(move)
                        board.push(move)
                        log.info('Player: %s', player_san)

                        if board.is_game_over():
                            log.info('Game over: %s', board.result())
                            line1, line2 = _game_over_message(board, player_is_white)
                            screen = SCREEN_GAME_OVER
                            _transition(epd, build_game_over_screen(line1, line2), partial_count)
                        else:
                            # Stockfish replies
                            _transition(epd, build_thinking_screen(), partial_count)
                            result  = engine.play(board, chess.engine.Limit(time=1.0))
                            sf_san  = board.san(result.move)
                            board.push(result.move)
                            log.info('Stockfish: %s', sf_san)
                            screen = SCREEN_SF_MOVE
                            _transition(epd,
                                        build_sf_move_screen(sf_san, board.fullmove_number),
                                        partial_count)

            # ── Game over — OK restarts from difficulty selection ─────────────
            elif screen == SCREEN_GAME_OVER:
                if _hit_ok(lx, ly):
                    if engine:
                        engine.quit()
                        engine = None
                    board     = None
                    inv_count = 0
                    diff_sel  = None
                    color_sel = None
                    sel_piece = sel_file = sel_rank = None
                    screen = SCREEN_DIFFICULTY
                    _transition(epd, build_difficulty_screen(), partial_count)

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
