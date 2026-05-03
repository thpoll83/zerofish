#!/usr/bin/env python3
"""Generate PNG screenshots of every ZeroFish screen.

Run from the repo root:
    python3 generate_screenshots.py

Options (flags take precedence over env vars):
    --scale N          Pixel scale factor          [env: SCREENSHOT_SCALE,  default: 3]
    --outdir PATH      Output directory            [env: SCREENSHOT_OUTDIR, default: docs/screenshots]
"""
import argparse
import os
import sys
import time

import hardware_stubs
hardware_stubs.install()

import chess
from PIL import Image

from screen_splash         import build_splash_screen
from screen_difficulty     import build_difficulty_screen
from screen_color          import build_color_screen
from screen_thinking       import build_thinking_screen
from screen_sf_move        import build_sf_move_screen
from screen_player_move    import build_player_move_screen
from screen_promotion      import build_promotion_screen
from screen_disambig       import build_disambig_screen, disambig_rects
from screen_ingame_menu    import build_ingame_menu_screen
from screen_resign_confirm import build_resign_confirm_screen
from screen_time           import build_time_screen
from screen_board          import build_board_screen
from screen_scoresheet     import build_scoresheet_screen
from screen_game_over      import build_game_over_screen

_DEFAULT_OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'docs', 'screenshots')


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate ZeroFish screen screenshots.')
    parser.add_argument(
        '--scale', type=int,
        default=int(os.environ.get('SCREENSHOT_SCALE', 3)),
        help='Pixel scale factor (default: 3, env: SCREENSHOT_SCALE)',
    )
    parser.add_argument(
        '--outdir',
        default=os.environ.get('SCREENSHOT_OUTDIR', _DEFAULT_OUTDIR),
        help='Output directory (default: docs/screenshots, env: SCREENSHOT_OUTDIR)',
    )
    return parser.parse_args()


def _save(name: str, img: Image.Image, outdir: str, scale: int) -> None:
    rgb = img.convert('RGB')
    w, h = rgb.size
    scaled = rgb.resize((w * scale, h * scale), Image.NEAREST)
    path = os.path.join(outdir, name)
    scaled.save(path)
    print(f'  {name}  ({w}×{h} → {w*scale}×{h*scale})')


def main() -> None:
    args = _parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    print(f'Writing screenshots to {args.outdir}/  (scale={args.scale}×)')

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
    ]

    for name, img in screens:
        _save(name, img, args.outdir, args.scale)

    print(f'\n{len(screens)} screenshots saved.')


if __name__ == '__main__':
    main()
