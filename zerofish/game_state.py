"""Persist game state so a power-loss interrupted game can be resumed."""
import json
import os

import chess
import config

SAVE_PATH = config.SAVE_PATH


def save(board: chess.Board, move_history: list, player_is_white: bool, diff_sel: int) -> None:
    data = {
        'fen':            board.fen(),
        'move_history':   move_history,
        'player_is_white': player_is_white,
        'diff_sel':       diff_sel,
        'ended_cleanly':  False,
    }
    try:
        with open(SAVE_PATH, 'w') as f:
            json.dump(data, f)
    except OSError:
        pass


def load() -> dict | None:
    """Return saved game dict if an unfinished game exists, else None."""
    if not os.path.exists(SAVE_PATH):
        return None
    try:
        with open(SAVE_PATH) as f:
            data = json.load(f)
        if data.get('ended_cleanly', True):
            return None
        # Quick sanity check on required keys
        chess.Board(data['fen'])
        return data
    except Exception:
        return None


def clear() -> None:
    """Mark the save as cleanly ended (keeps file, avoids FS churn)."""
    if not os.path.exists(SAVE_PATH):
        return
    try:
        with open(SAVE_PATH) as f:
            data = json.load(f)
        data['ended_cleanly'] = True
        with open(SAVE_PATH, 'w') as f:
            json.dump(data, f)
    except Exception:
        pass
