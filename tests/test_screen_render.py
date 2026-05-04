"""
Tests that every build_*_screen() function returns a valid PIL image
with the correct dimensions.

No hardware or fonts are required: ui.load_fonts() falls back to
ImageFont.load_default() if the truetype files are absent.
"""
import time
import chess
from PIL import Image

from screen_difficulty   import build_difficulty_screen
from screen_color        import build_color_screen
from screen_player_move  import build_player_move_screen
from screen_promotion    import build_promotion_screen
from screen_splash       import build_splash_screen
from screen_sf_move      import build_sf_move_screen
from screen_thinking     import build_thinking_screen
from screen_game_over    import build_game_over_screen
from screen_ingame_menu  import build_ingame_menu_screen
from screen_scoresheet   import build_scoresheet_screen
from screen_disambig     import build_disambig_screen, disambig_rects
from screen_time         import build_time_screen
from screen_board        import build_board_screen
from screen_resign_confirm import build_resign_confirm_screen
import config

LANDSCAPE = (config.DISPLAY_W, config.DISPLAY_H)   # 250 × 122
PORTRAIT  = (config.SCORE_W,   config.SCORE_H)     # 122 × 250


def _ok(img, expected_size=LANDSCAPE):
    assert isinstance(img, Image.Image)
    assert img.size == expected_size


# ── Difficulty ────────────────────────────────────────────────────────────────

def test_difficulty_no_selection():
    _ok(build_difficulty_screen())


def test_difficulty_with_selection():
    for lvl in (1, 8, 15):
        _ok(build_difficulty_screen(lvl))


# ── Side selection ────────────────────────────────────────────────────────────

def test_color_no_selection():
    _ok(build_color_screen())


def test_color_with_selection():
    for i in range(3):
        _ok(build_color_screen(i))


# ── Player move input ─────────────────────────────────────────────────────────

def test_player_move_nothing_selected():
    _ok(build_player_move_screen(None, None, None, 0, '#1'))


def test_player_move_all_selected():
    _ok(build_player_move_screen(0, 4, 3, 0, '#1'))


def test_player_move_partial_selection():
    _ok(build_player_move_screen(0, None, None, 2, '#3'))


def test_player_move_with_invalid_count():
    _ok(build_player_move_screen(None, None, None, 5, '#2'))


# ── Promotion ─────────────────────────────────────────────────────────────────

def test_promotion_no_selection():
    _ok(build_promotion_screen())


def test_promotion_with_selection():
    for i in range(4):
        _ok(build_promotion_screen(i, '#5'))


# ── Splash ────────────────────────────────────────────────────────────────────

def test_splash_no_resume():
    _ok(build_splash_screen(('Stockfish 16', '64-bit'), has_resume=False))


def test_splash_with_resume():
    _ok(build_splash_screen(('Stockfish 16', '64-bit'), has_resume=True))


def test_splash_no_sf_info():
    # None = loading state: renders without buttons or SF info lines
    _ok(build_splash_screen(None))


# ── Stockfish move ────────────────────────────────────────────────────────────

def test_sf_move_pawn():
    _ok(build_sf_move_screen('e4', '#1'))


def test_sf_move_knight():
    _ok(build_sf_move_screen('Nf3', '#2'))


def test_sf_move_long_san():
    _ok(build_sf_move_screen('Qxd5+', '#10'))


# ── Thinking ─────────────────────────────────────────────────────────────────

def test_thinking_screen():
    _ok(build_thinking_screen('#3'))


def test_thinking_screen_empty_label():
    _ok(build_thinking_screen())


# ── Game over ─────────────────────────────────────────────────────────────────

def test_game_over_win():
    _ok(build_game_over_screen('You win!', 'Checkmate'))


def test_game_over_draw():
    _ok(build_game_over_screen('Draw', 'Stalemate'))


def test_game_over_no_line2():
    _ok(build_game_over_screen('Game Over', ''))


# ── In-game menu ──────────────────────────────────────────────────────────────

def test_ingame_menu():
    _ok(build_ingame_menu_screen('#5'))


def test_ingame_menu_empty_label():
    _ok(build_ingame_menu_screen())


# ── Score sheet (portrait) ────────────────────────────────────────────────────

def test_scoresheet_empty():
    _ok(build_scoresheet_screen([]), PORTRAIT)


def test_scoresheet_few_moves():
    _ok(build_scoresheet_screen(['e4', 'e5', 'Nf3', 'Nc6']), PORTRAIT)


def test_scoresheet_many_moves():
    # More than 15 full moves (30 half-moves) to test the trim logic
    moves = [f'm{i}' for i in range(40)]
    _ok(build_scoresheet_screen(moves), PORTRAIT)


def test_scoresheet_odd_length():
    # Odd number of half-moves (last move is white's)
    _ok(build_scoresheet_screen(['e4', 'e5', 'Nf3']), PORTRAIT)


# ── Disambiguation ────────────────────────────────────────────────────────────

def test_disambig_two_options():
    rects = disambig_rects(2)
    _ok(build_disambig_screen(['a1', 'a2'], rects))


def test_disambig_three_options():
    rects = disambig_rects(3)
    _ok(build_disambig_screen(['a1', 'a3', 'a5'], rects, selected=1, move_label='#4'))


# ── Time ─────────────────────────────────────────────────────────────────────

def test_time_screen():
    game_start = time.time() - 120.0
    _ok(build_time_screen(game_start, 45.0))


def test_time_screen_zero():
    _ok(build_time_screen(0, 0.0))


# ── Board view ────────────────────────────────────────────────────────────────

def test_board_screen_start_white():
    _ok(build_board_screen(chess.Board(), player_is_white=True))


def test_board_screen_start_black():
    _ok(build_board_screen(chess.Board(), player_is_white=False))


def test_board_screen_mid_game():
    board = chess.Board()
    for uci in ('e2e4', 'e7e5', 'g1f3', 'b8c6'):
        board.push_uci(uci)
    _ok(build_board_screen(board))


# ── Resign confirm ────────────────────────────────────────────────────────────

def test_resign_confirm_screen():
    _ok(build_resign_confirm_screen())
