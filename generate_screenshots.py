#!/usr/bin/env python3
"""Generate PNG screenshots of every ZeroFish screen.

Run from the repo root:
    python3 generate_screenshots.py

Output goes to docs/screenshots/.  Each image is scaled 3x so the tiny
250x122 px canvas is readable on a normal monitor.
"""
import os
import sys
import time
import types

# ── Hardware stubs (same technique as tests/conftest.py) ─────────────────────
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zerofish')
sys.path.insert(0, _SRC)

for _pkg in ('gpiozero', 'spidev', 'smbus'):
    sys.modules.setdefault(_pkg, types.ModuleType(_pkg))

_ec = types.ModuleType('TP_lib.epdconfig')
_ec.EPD_RST_PIN = 17; _ec.EPD_DC_PIN = 25; _ec.EPD_CS_PIN = 8
_ec.EPD_BUSY_PIN = 24; _ec.TRST = 22; _ec.INT = 27; _ec.address = 0x14
_ec.bus = types.SimpleNamespace(write_i2c_block_data=lambda *a, **kw: None,
                                 read_byte=lambda *a: 0)
_ec.digital_write = lambda *a: None; _ec.digital_read = lambda p: 0
_ec.delay_ms = lambda ms: None; _ec.spi_writebyte = lambda d: None
_ec.spi_writebyte2 = lambda d: None; _ec.i2c_writebyte = lambda *a: None
_ec.i2c_write = lambda r: None; _ec.i2c_readbyte = lambda r, n: [0] * n
_ec.module_init = lambda: 0; _ec.module_exit = lambda: None
_tp = types.ModuleType('TP_lib'); _tp.__path__ = [os.path.join(_SRC, 'TP_lib')]
sys.modules['TP_lib'] = _tp; sys.modules['TP_lib.epdconfig'] = _ec

# ── Imports (hardware-free from here on) ─────────────────────────────────────
import chess
from PIL import Image

from screen_splash        import build_splash_screen
from screen_main_menu     import build_main_menu_screen
from screen_difficulty    import build_difficulty_screen
from screen_color         import build_color_screen
from screen_thinking      import build_thinking_screen
from screen_sf_move       import build_sf_move_screen
from screen_player_move   import build_player_move_screen
from screen_promotion     import build_promotion_screen
from screen_disambig      import build_disambig_screen, disambig_rects
from screen_ingame_menu   import build_ingame_menu_screen
from screen_resign_confirm import build_resign_confirm_screen
from screen_time          import build_time_screen
from screen_board         import build_board_screen
from screen_scoresheet    import build_scoresheet_screen
from screen_game_over     import build_game_over_screen
from screen_resume        import build_resume_screen
from screen_puzzle             import build_puzzle_screen
from screen_puzzle_loading     import build_puzzle_loading_screen
from screen_puzzle_end_confirm import build_puzzle_end_confirm_screen
from screen_puzzle_hint        import build_puzzle_hint_screen
from screen_stats              import build_stats_screen
from screen_game_stats         import build_game_stats_screen
from screen_settings           import build_settings_screen
from screen_wifi               import build_wifi_screen, build_wifi_result_screen
from screen_analyze            import build_analyze_screen

SCALE  = 3
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs', 'screenshots')


def _save(name: str, img: Image.Image) -> None:
    rgb = img.convert('RGB')
    w, h = rgb.size
    scaled = rgb.resize((w * SCALE, h * SCALE), Image.NEAREST)
    path = os.path.join(OUTDIR, name)
    scaled.save(path)
    print(f'  {name}  ({w}x{h} → {w*SCALE}x{h*SCALE})')


def main() -> None:
    os.makedirs(OUTDIR, exist_ok=True)
    print(f'Writing screenshots to {OUTDIR}/')

    # Build a mid-game board for more interesting board/scoresheet shots
    board = chess.Board()
    ruy_lopez = ['e2e4', 'e7e5', 'g1f3', 'b8c6', 'f1b5', 'a7a6',
                 'b5a4', 'g8f6', 'e1g1', 'f8e7']
    move_history = []
    for uci in ruy_lopez:
        move = chess.Move.from_uci(uci)
        move_history.append(board.san(move))
        board.push(move)

    # Puzzle board: position after 1.e4 e5 Nf3 — Black to move
    puz_board = chess.Board()
    for uci in ('e2e4', 'e7e5', 'g1f3'):
        puz_board.push_uci(uci)

    # Multi-move puzzle board: mid-sequence (engine played d2d4, player's 2nd move)
    puz_board_move2 = chess.Board()
    for uci in ('e2e4', 'e7e5', 'd2d4'):
        puz_board_move2.push_uci(uci)

    # Hint screen data: puzzle start FEN is after the trigger move (1.e4 played)
    # so hint_moves[0] = 'e7e5' is legal (black to move).
    _hint_trigger_board = chess.Board()
    _hint_trigger_board.push_uci('e2e4')
    hint_fen_start = _hint_trigger_board.fen()   # after 1.e4, black to move

    # Board shown on hint screen = position at the point of failure
    # Single-move hint: wrong on very first move → board = hint_fen_start position
    hint_board_single = chess.Board(hint_fen_start)

    # Multi-move hint: wrong on move 2 (e7e5 + d2d4 already played)
    hint_board_mm = chess.Board(hint_fen_start)
    hint_board_mm.push_uci('e7e5')
    hint_board_mm.push_uci('d2d4')

    screens = [
        ('01_splash.png',
         build_splash_screen(('Stockfish 16', '64-bit'))),

        ('02_splash_loading.png',
         build_splash_screen(None)),

        ('03_main_menu.png',
         build_main_menu_screen(has_saves=True)),

        ('03b_stats.png',
         build_stats_screen()),

        ('03b2_game_stats.png',
         build_game_stats_screen()),

        ('03c_settings.png',
         build_settings_screen()),

        ('03d_wifi_list.png',
         build_wifi_screen(
             [{'ssid': 'HomeWifi',  'signal': 90, 'in_use': True,
               'has_password': True,  'ip': '192.168.1.42'},
              {'ssid': 'CafeNet',   'signal': 65, 'in_use': False,
               'has_password': False, 'ip': None},
              {'ssid': 'OfficeNet', 'signal': 50, 'in_use': False,
               'has_password': True,  'ip': None},
              {'ssid': 'WeakAP',    'signal': 20, 'in_use': False,
               'has_password': True,  'ip': None}],
             selected_idx=0, passwd='', kbd_page=0)),

        ('03e_wifi_connected.png',
         build_wifi_screen(
             [{'ssid': 'HomeWifi', 'signal': 90, 'in_use': True,
               'has_password': True, 'ip': '192.168.1.42'}],
             selected_idx=0, passwd='', kbd_page=0)),

        ('03f_wifi_open.png',
         build_wifi_screen(
             [{'ssid': 'CafeNet', 'signal': 65, 'in_use': False,
               'has_password': False, 'ip': None}],
             selected_idx=0, passwd='', kbd_page=0)),

        ('03g_wifi_keyboard.png',
         build_wifi_screen(
             [{'ssid': 'OfficeNet', 'signal': 50, 'in_use': False,
               'has_password': True, 'ip': None}],
             selected_idx=0, passwd='MyPass', kbd_page=0)),

        ('03h_wifi_disconnected.png',
         build_wifi_screen(
             [{'ssid': 'HomeWifi', 'signal': 90, 'in_use': False,
               'has_password': True, 'ip': None}],
             selected_idx=0, passwd='', kbd_page=0, status='disconnected')),

        ('03i_wifi_result.png',
         build_wifi_result_screen('OfficeNet',
                                  'Error: Secrets were required, but not provided.')),

        ('04_difficulty.png',
         build_difficulty_screen(selected=5)),

        ('05_side.png',
         build_color_screen(selected=0)),

        ('06_thinking.png',
         build_thinking_screen('#1')),

        ('07_sf_move.png',
         build_sf_move_screen('e4', '#1')),

        ('08_player_move.png',
         build_player_move_screen(None, None, None, inv_count=0, move_label='#2')),

        ('09_player_move_partial.png',
         build_player_move_screen(sel_piece=0, sel_file=4, sel_rank=None,
                                   inv_count=0, move_label='#2')),

        ('10_promotion.png',
         build_promotion_screen(selected=3, move_label='#7')),

        ('11_disambig.png',
         build_disambig_screen(['♜a1', '♜a3'],
                                disambig_rects(2), selected=0, move_label='#5')),

        ('12_ingame_menu.png',
         build_ingame_menu_screen(move_label='#5')),

        ('13_resign_confirm.png',
         build_resign_confirm_screen()),

        ('14_time.png',
         build_time_screen(game_start=time.time() - 183, sf_time=61.0)),

        ('15_board.png',
         build_board_screen(board, player_is_white=True)),

        ('16_scoresheet.png',
         build_scoresheet_screen(move_history, move_label='#5')),

        ('17_game_over_win.png',
         build_game_over_screen('You win!', 'Checkmate')),

        ('18_game_over_draw.png',
         build_game_over_screen('Draw', 'Stalemate')),

        ('19_resume_few.png',
         build_resume_screen(
             [{'start_date': '2026-05-01', 'move_history': ['e4', 'e5'],
               'diff_sel': 15, 'player_is_white': True},
              {'start_date': '2026-04-30', 'move_history': ['d4', 'Nf6', 'c4'],
               'diff_sel': 5, 'player_is_white': False},
              {'start_date': '2026-04-28', 'move_history': ['Nf3'],
               'diff_sel': 10, 'player_is_white': True}],
             page=0, sel=1)),

        ('20_resume_many.png',
         build_resume_screen(
             [{'start_date': f'2026-0{m}-{d:02d}', 'move_history': ['e4', 'e5']}
              for m, d in [(5,1),(4,30),(4,29),(4,28),(4,27),(4,26),(4,25)]],
             page=0, sel=None)),

        # ── Puzzle screens ──────────────────────────────────────────────────
        ('21_puzzle.png',
         build_puzzle_screen(puz_board, puzzle_num=1, total=200,
                              solved=0, wrong=0, diff_label='1540')),

        ('22_puzzle_progress.png',
         build_puzzle_screen(puz_board, puzzle_num=42, total=200,
                              solved=12, wrong=3, diff_label='1720',
                              last_result='solved')),

        ('22b_puzzle_wrong.png',
         build_puzzle_screen(puz_board, puzzle_num=42, total=200,
                              solved=12, wrong=3, diff_label='1720',
                              last_result='wrong')),

        ('22c_puzzle_skipped.png',
         build_puzzle_screen(puz_board, puzzle_num=43, total=200,
                              solved=12, wrong=3, diff_label='1600',
                              last_result='skipped')),

        ('23_puzzle_solve_input.png',
         build_player_move_screen(None, None, None, inv_count=0,
                                   move_label='Puzzle', sec_label='Back')),

        ('24_puzzle_solve_partial.png',
         build_player_move_screen(sel_piece=1, sel_file=5, sel_rank=None,
                                   inv_count=0, move_label='Puzzle',
                                   sec_label='Back')),

        ('25_puzzle_no_puzzles.png',
         build_puzzle_screen(None, puzzle_num=0, total=0,
                              solved=0, wrong=0, diff_label='')),

        ('26_puzzle_disambig.png',
         build_disambig_screen(['♞c3', '♞f3'],
                                disambig_rects(2), selected=0, move_label='Puzzle')),

        ('27_puzzle_loading.png',
         build_puzzle_loading_screen(has_existing=False,
                                      rows_scanned=40000, found=63)),

        ('28_puzzle_loading_existing.png',
         build_puzzle_loading_screen(has_existing=True,
                                      rows_scanned=0, found=0)),

        ('29_puzzle_promotion.png',
         build_promotion_screen(selected=3, move_label='Puzzle')),

        ('30_puzzle_end_confirm.png',
         build_puzzle_end_confirm_screen()),

        ('31_puzzle_multimove_1of2.png',
         build_puzzle_screen(puz_board, puzzle_num=5, total=200,
                              solved=2, wrong=1, diff_label='1200',
                              move_num=1, move_total=2, last_result='solved')),

        ('32_puzzle_multimove_2of2.png',
         build_puzzle_screen(puz_board_move2, puzzle_num=5, total=200,
                              solved=2, wrong=1, diff_label='1200',
                              move_num=2, move_total=2, last_result=None)),

        # ── Hint screens ────────────────────────────────────────────────────
        # Single-move puzzle: wrong on first (and only) move
        ('33_puzzle_hint_single.png',
         build_puzzle_hint_screen(hint_board_single,
                                   hint_fen=hint_fen_start,
                                   hint_moves=['e7e5'],
                                   hint_move_idx=0)),

        # Multi-move puzzle: wrong on move 2 (move 1 was e7e5, engine replied d2d4)
        ('34_puzzle_hint_multimove.png',
         build_puzzle_hint_screen(hint_board_mm,
                                   hint_fen=hint_fen_start,
                                   hint_moves=['e7e5', 'd2d4', 'e5d4'],
                                   hint_move_idx=2)),

    ]

    # ── Analyze screenshots (built after screens list, need extra boards) ────
    az_start = chess.Board()

    az_mid = chess.Board()
    az_mid_last = None
    for i, uci in enumerate(ruy_lopez[:5]):
        mv = chess.Move.from_uci(uci)
        if i == 4:
            az_mid_last = mv
        az_mid.push(mv)

    screens += [
        # Start position (move 0/10)
        ('35_analyze_start.png',
         build_analyze_screen(az_start, 0, len(move_history),
                               player_is_white=True,
                               played_san='', best_san='e4')),

        # After move 5 (e4 e5 Nf3 Nc6 Bb5) — last move highlighted
        ('36_analyze_mid.png',
         build_analyze_screen(az_mid, 5, len(move_history),
                               last_move=az_mid_last, player_is_white=True,
                               played_san='Bb5', best_san='a4')),

        # Final position (all 10 moves played) — only "End" button shown
        ('37_analyze_end.png',
         build_analyze_screen(board, len(move_history), len(move_history),
                               player_is_white=True,
                               played_san='Be7', best_san='')),
    ]

    for name, img in screens:
        _save(name, img)

    print(f'\n{len(screens)} screenshots saved.')


if __name__ == '__main__':
    main()
