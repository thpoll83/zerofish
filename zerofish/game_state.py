"""Persist game state so power-loss interrupted games can be resumed.

Each game is saved to its own timestamped file in SAVE_DIR.
The old single-file save (~/.zerofish_save.json) is migrated automatically.
"""
import json
import os
from datetime import datetime

import chess
import config

SAVE_DIR = config.SAVE_DIR
_OLD_SAVE_PATH = os.path.expanduser('~/.zerofish_save.json')


def _date_from_path(path: str) -> str:
    """Extract YYYY-MM-DD from a filename like game_YYYYMMDD_HHMMSS.json."""
    name = os.path.basename(path)
    try:
        ts = name.removeprefix('game_').split('_')[0]
        if len(ts) == 8:
            return f'{ts[:4]}-{ts[4:6]}-{ts[6:8]}'
    except Exception:
        pass
    return '?'


def _migrate_old_save() -> None:
    """Move the legacy single-file save into the new save directory."""
    if not os.path.exists(_OLD_SAVE_PATH):
        return
    try:
        with open(_OLD_SAVE_PATH) as f:
            data = json.load(f)
        if data.get('ended_cleanly', True):
            os.remove(_OLD_SAVE_PATH)
            return
        os.makedirs(SAVE_DIR, exist_ok=True)
        mtime = os.path.getmtime(_OLD_SAVE_PATH)
        ts = datetime.fromtimestamp(mtime).strftime('%Y%m%d_%H%M%S')
        new_path = os.path.join(SAVE_DIR, f'game_{ts}.json')
        if not os.path.exists(new_path):
            data['start_date'] = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
            data.pop('ended_cleanly', None)
            data['ended_cleanly'] = False
            with open(new_path, 'w') as f:
                json.dump(data, f)
        os.remove(_OLD_SAVE_PATH)
    except Exception:
        pass


def save(board: chess.Board, move_history: list, player_is_white: bool,
         diff_sel: int, save_path: str | None = None) -> str:
    """Write game state to *save_path* (or a new timestamped file).

    Returns the path actually written so callers can track it.
    """
    os.makedirs(SAVE_DIR, exist_ok=True)
    if save_path is None:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        save_path = os.path.join(SAVE_DIR, f'game_{ts}.json')
    data = {
        'fen':            board.fen(),
        'move_history':   move_history,
        'player_is_white': player_is_white,
        'diff_sel':       diff_sel,
        'ended_cleanly':  False,
        'start_date':     _date_from_path(save_path),
    }
    try:
        with open(save_path, 'w') as f:
            json.dump(data, f)
    except OSError:
        pass
    return save_path


def list_saves() -> list:
    """Return unfinished save dicts sorted newest-first.

    Each dict: path, start_date, move_history, fen, player_is_white, diff_sel.
    """
    _migrate_old_save()
    if not os.path.isdir(SAVE_DIR):
        return []
    saves = []
    for fname in sorted(os.listdir(SAVE_DIR), reverse=True):
        if not fname.endswith('.json'):
            continue
        path = os.path.join(SAVE_DIR, fname)
        try:
            with open(path) as f:
                data = json.load(f)
            if data.get('ended_cleanly', True):
                continue
            chess.Board(data['fen'])  # sanity check
            saves.append({
                'path':            path,
                'start_date':      data.get('start_date', _date_from_path(path)),
                'move_history':    data.get('move_history', []),
                'fen':             data['fen'],
                'player_is_white': data.get('player_is_white', True),
                'diff_sel':        data.get('diff_sel', 1),
            })
        except Exception:
            pass
    return saves


def load(path: str) -> dict | None:
    """Load a specific save file; returns None on error."""
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        chess.Board(data['fen'])
        return data
    except Exception:
        return None


def clear(path: str) -> None:
    """Delete the save file (game ended cleanly)."""
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
