#!/usr/bin/env python3
"""Generate PNG screenshots of every ZeroFish screen.

Run from the repo root:
    python3 generate_screenshots.py

Output goes to docs/screenshots/.  Each image is scaled 3× so the tiny
250×122 px canvas is readable on a normal monitor.
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

SCALE  = 3
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs', 'screenshots')


def _save(name: str, img: Image.Image) -> None:
    rgb = img.convert('RGB')
    w, h = rgb.size
    scaled = rgb.resize((w * SCALE, h * SCALE), Image.NEAREST)
    path = os.path.join(OUTDIR, name)
    scaled.save(path)
    print(f'  {name}  ({w}×{h} → {w*SCALE}×{h*SCALE})')


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

    screens = [
        ('01_splash.png',
         build_splash_screen(('Stockfish 16', '64-bit'), has_resume=False)),

        ('02_splash_resume.png',
         build_splash_screen(('Stockfish 16', '64-bit'), has_resume=True)),

        ('03_difficulty.png',
         build_difficulty_screen(selected=5)),

        ('04_side.png',
         build_color_screen(selected=0)),

        ('05_thinking.png',
         build_thinking_screen('#1')),

        ('06_sf_move.png',
         build_sf_move_screen('e4', '#1')),

        ('07_player_move.png',
         build_player_move_screen(None, None, None, inv_count=0, move_label='#2')),

        ('08_player_move_partial.png',
         build_player_move_screen(sel_piece=0, sel_file=4, sel_rank=None,
                                   inv_count=0, move_label='#2')),

        ('09_promotion.png',
         build_promotion_screen(selected=3, move_label='#7')),

        ('10_disambig.png',
         build_disambig_screen(['♜a1', '♜a3'],
                                disambig_rects(2), selected=0, move_label='#5')),

        ('11_ingame_menu.png',
         build_ingame_menu_screen(move_label='#5')),

        ('12_resign_confirm.png',
         build_resign_confirm_screen()),

        ('13_time.png',
         build_time_screen(game_start=time.time() - 183, sf_time=61.0)),

        ('14_board.png',
         build_board_screen(board, player_is_white=True)),

        ('15_scoresheet.png',
         build_scoresheet_screen(move_history, move_label='#5')),

        ('16_game_over_win.png',
         build_game_over_screen('You win!', 'Checkmate')),

        ('17_game_over_draw.png',
         build_game_over_screen('Draw', 'Stalemate')),

        ('18_resume_few.png',
         build_resume_screen(
             [{'start_date': '2026-05-01', 'move_history': ['e4', 'e5'],
               'diff_sel': 15, 'player_is_white': True},
              {'start_date': '2026-04-30', 'move_history': ['d4', 'Nf6', 'c4'],
               'diff_sel': 5, 'player_is_white': False},
              {'start_date': '2026-04-28', 'move_history': ['Nf3'],
               'diff_sel': 10, 'player_is_white': True}],
             page=0, sel=1)),

        ('19_resume_many.png',
         build_resume_screen(
             [{'start_date': f'2026-0{m}-{d:02d}', 'move_history': ['e4', 'e5']}
              for m, d in [(5,1),(4,30),(4,29),(4,28),(4,27),(4,26),(4,25)]],
             page=0, sel=None)),
    ]

    for name, img in screens:
        _save(name, img)

    print(f'\n{len(screens)} screenshots saved.')


if __name__ == '__main__':
    main()
