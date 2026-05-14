"""Game-session utilities shared between main.py screens.

Extracted from main.py to keep the main loop focused on UI flow.
"""

import atexit
import logging
import os
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

# ── Opening book reader cache ─────────────────────────────────────────────────
_book_reader = None
_book_path_cached: str | None = None


def _close_book() -> None:
    global _book_reader
    if _book_reader is not None:
        try:
            _book_reader.close()
        except Exception:
            pass
        _book_reader = None


atexit.register(_close_book)


def book_move(board: chess.Board, book_path: str) -> chess.Move | None:
    """Look up a move from a Polyglot opening book; return None if unavailable."""
    global _book_reader, _book_path_cached
    if not book_path:
        return None
    if book_path != _book_path_cached:
        _close_book()
        _book_path_cached = None
        if not os.path.exists(book_path):
            return None
        try:
            _book_reader = chess.polyglot.open_reader(book_path)
            _book_path_cached = book_path
        except Exception:
            return None
    if _book_reader is None:
        return None
    try:
        entry = _book_reader.find(board)
        return entry.move
    except Exception:
        return None


def engine_move(board: chess.Board, engine, engine_limit,
                book_path: str = '',
                on_thinking=None) -> tuple[str, float]:
    """Play one engine move and push it onto *board*.

    Tries the opening book first. When no book move is available, calls
    *on_thinking* (if provided) before starting the engine search, then
    delegates to Stockfish.

    Returns (san, elapsed_secs). elapsed_secs is 0.0 for book moves.
    Raises on engine error.
    """
    bm = book_move(board, book_path)
    if bm is not None and board.is_legal(bm):
        san = board.san(bm)
        board.push(bm)
        return san, 0.0
    if on_thinking is not None:
        on_thinking()
    t0 = time.time()
    set_cpu_governor('performance')
    try:
        result = engine.play(board, engine_limit)
    finally:
        set_cpu_governor('powersave')
    san = board.san(result.move)
    board.push(result.move)
    return san, time.time() - t0


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
    """Push the player move, check for game over, then get the engine's reply.

    transition_fn(epd, img, partial_count) — full display refresh
    show_fn(epd, img, partial_count)       — partial display update

    Returns (new_screen_id, new_move_label).
    """
    san = board.san(move)
    board.push(move)
    move_history.append(san)
    log.info('Player: %s', san)

    if board.is_game_over():
        log.info('Game over after player move: %s', board.result())
        line1, line2 = game_over_message(board, player_is_white)
        transition_fn(epd, build_game_over_screen(line1, line2), partial_count)
        return ui.SCREEN_GAME_OVER, cur_move_label

    sf_label = move_label(board)
    try:
        sf_san, elapsed = engine_move(
            board, engine, engine_think_limit,
            book_path=config.OPENING_BOOK_PATH,
            on_thinking=lambda: transition_fn(
                epd, build_thinking_screen(sf_label), partial_count),
        )
    except Exception as exc:
        log.error('Engine.play failed: %s', exc)
        transition_fn(epd, build_game_over_screen('Engine error', ''), partial_count)
        return ui.SCREEN_GAME_OVER, cur_move_label

    move_history.append(sf_san)
    if sf_time_acc is not None:
        sf_time_acc[0] += elapsed
    log.info('%s: %s', 'Book' if elapsed == 0.0 else 'Stockfish', sf_san)

    if board.is_game_over():
        log.info('Game over after engine move: %s', board.result())
        line1, line2 = game_over_message(board, player_is_white)
        transition_fn(epd, build_game_over_screen(line1, line2), partial_count)
        return ui.SCREEN_GAME_OVER, cur_move_label

    transition_fn(epd, build_sf_move_screen(sf_san, sf_label), partial_count)
    return ui.SCREEN_SF_MOVE, sf_label
