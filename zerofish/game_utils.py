"""Game-session utilities shared between main.py screens.

Extracted from main.py to keep the main loop focused on UI flow.
"""

import logging
import time

import chess
import chess.engine
import chess.polyglot

import config
import ui
from screen_thinking  import build_thinking_screen
from screen_sf_move   import build_sf_move_screen
from screen_game_over import build_game_over_screen, game_over_message

log = logging.getLogger('zerofish')


def book_move(board: chess.Board, book_path: str) -> chess.Move | None:
    """Look up a move from a Polyglot opening book; return None if unavailable."""
    if not book_path:
        return None
    try:
        with chess.polyglot.open_reader(book_path) as reader:
            entry = reader.find(board)
            return entry.move
    except Exception:
        return None


def skill_level(difficulty: int) -> int:
    return config.DIFF_SKILL_LEVELS.get(difficulty, 0)


def think_limit(difficulty: int) -> chess.engine.Limit:
    return chess.engine.Limit(time=config.DIFF_THINK_SECS.get(difficulty, 1.0))


def move_label(board: chess.Board) -> str:
    n = board.fullmove_number
    return f'#{n}' if board.turn == chess.WHITE else f'#…{n}'


def set_cpu_governor(gov: str) -> None:
    import subprocess
    try:
        subprocess.run(['sudo', '/usr/local/bin/zerofish-set-governor', gov],
                       check=False, capture_output=True, timeout=1)
    except subprocess.TimeoutExpired:
        log.warning('set_cpu_governor %s timed out', gov)
    except Exception as exc:
        log.warning('set_cpu_governor %s failed: %s', gov, exc)


def push_and_continue(board, move, move_history, engine, engine_think_limit,
                      epd, partial_count, player_is_white, inv_count,
                      cur_move_label, sf_time_acc=None,
                      *, transition_fn, show_fn):
    """Push the player move, check for game over, then get Stockfish's reply.

    transition_fn(epd, img, partial_count) — full display refresh
    show_fn(epd, img, partial_count)       — partial display update

    Returns (new_screen_id, new_move_label).
    """
    san = board.san(move)
    board.push(move)
    move_history.append(san)
    log.info('Player: %s', san)

    if board.is_game_over():
        log.info('Game over: %s', board.result())
        line1, line2 = game_over_message(board, player_is_white)
        transition_fn(epd, build_game_over_screen(line1, line2), partial_count)
        return ui.SCREEN_GAME_OVER, cur_move_label

    sf_label = move_label(board)

    # Opening book probe — skips engine thinking for known opening positions.
    bm = book_move(board, config.OPENING_BOOK_PATH)
    if bm is not None and board.is_legal(bm):
        sf_san = board.san(bm)
        board.push(bm)
        move_history.append(sf_san)
        log.info('Book move: %s', sf_san)
        if board.is_game_over():
            line1, line2 = game_over_message(board, player_is_white)
            transition_fn(epd, build_game_over_screen(line1, line2), partial_count)
            return ui.SCREEN_GAME_OVER, cur_move_label
        transition_fn(epd, build_sf_move_screen(sf_san, sf_label), partial_count)
        return ui.SCREEN_SF_MOVE, sf_label

    transition_fn(epd, build_thinking_screen(sf_label), partial_count)
    t0 = time.time()
    set_cpu_governor('performance')
    try:
        result = engine.play(board, engine_think_limit)
    except Exception as exc:
        log.error('Engine.play failed: %s', exc)
        transition_fn(epd, build_game_over_screen('Engine error', ''), partial_count)
        return ui.SCREEN_GAME_OVER, cur_move_label
    finally:
        set_cpu_governor('powersave')
    if sf_time_acc is not None:
        sf_time_acc[0] += time.time() - t0
    sf_san = board.san(result.move)
    board.push(result.move)
    move_history.append(sf_san)
    log.info('Stockfish: %s', sf_san)
    transition_fn(epd, build_sf_move_screen(sf_san, sf_label), partial_count)
    return ui.SCREEN_SF_MOVE, sf_label
