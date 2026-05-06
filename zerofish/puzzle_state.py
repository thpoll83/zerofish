"""Load and persist chess puzzle data.

Puzzles are stored in PUZZLE_DIR/puzzles.json (downloaded by
deploy/download_puzzles.py).  Solved puzzle IDs are tracked in
PUZZLE_DIR/solved.json so they are never repeated.
"""

import json
import os

import config

PUZZLE_DIR   = config.PUZZLE_DIR
PUZZLE_FILE  = os.path.join(PUZZLE_DIR, 'puzzles.json')
SOLVED_FILE  = os.path.join(PUZZLE_DIR, 'solved.json')


def load_unsolved() -> list[dict]:
    """Return puzzles that have not yet been solved, in original order."""
    solved = _load_solved_ids()
    try:
        with open(PUZZLE_FILE) as f:
            data = json.load(f)
        return [p for p in data.get('puzzles', []) if p['id'] not in solved]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return []


def load_unsolved_by_rating(min_rating: int, max_rating: int) -> list[dict]:
    """Return unsolved puzzles whose Lichess rating falls within [min_rating, max_rating]."""
    return [p for p in load_unsolved()
            if min_rating <= p.get('rating', 0) <= max_rating]


def get_moves(puzzle: dict) -> list[str]:
    """Return the solution-move sequence for *puzzle*, handling old and new formats.

    Old format: ``{'solution': '<uci>'}`` — single-move string.
    New format: ``{'moves': ['<uci>', …]}`` — full alternating sequence.
    """
    if 'moves' in puzzle:
        return list(puzzle['moves'])
    sol = puzzle.get('solution', '')
    return [sol] if sol else []


def total_available() -> int:
    """Total puzzle count in the file (solved + unsolved)."""
    try:
        with open(PUZZLE_FILE) as f:
            data = json.load(f)
        return len(data.get('puzzles', []))
    except Exception:
        return 0


def mark_solved(puzzle_id: str) -> None:
    """Record *puzzle_id* as solved so it won't appear again."""
    solved = _load_solved_ids()
    solved.add(puzzle_id)
    os.makedirs(PUZZLE_DIR, exist_ok=True)
    try:
        with open(SOLVED_FILE, 'w') as f:
            json.dump(list(solved), f)
    except OSError:
        pass


def _load_solved_ids() -> set:
    try:
        with open(SOLVED_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()
