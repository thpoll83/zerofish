"""Tests for zerofish/puzzle_state.py.

Tests cover load_unsolved, total_available, mark_solved, and _load_solved_ids
using a temporary directory to avoid touching the real ~/.zerofish_puzzles.
"""
import json
import os
import sys
import types

import pytest

# conftest.py already adds zerofish/ to sys.path and stubs hardware.


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f)


# ---------------------------------------------------------------------------
# Helpers to patch puzzle_state's file paths within a tmp directory
# ---------------------------------------------------------------------------

@pytest.fixture()
def puz_dir(tmp_path, monkeypatch):
    """Redirect puzzle_state to use a fresh temporary directory."""
    import puzzle_state as ps

    puzzle_dir = str(tmp_path / 'puzzles')
    puzzle_file = os.path.join(puzzle_dir, 'puzzles.json')
    solved_file = os.path.join(puzzle_dir, 'solved.json')

    monkeypatch.setattr(ps, 'PUZZLE_DIR',  puzzle_dir)
    monkeypatch.setattr(ps, 'PUZZLE_FILE', puzzle_file)
    monkeypatch.setattr(ps, 'SOLVED_FILE', solved_file)

    os.makedirs(puzzle_dir, exist_ok=True)
    return types.SimpleNamespace(
        dir=puzzle_dir,
        puzzle_file=puzzle_file,
        solved_file=solved_file,
    )


# ---------------------------------------------------------------------------
# _load_solved_ids
# ---------------------------------------------------------------------------

def test_load_solved_ids_empty_when_no_file(puz_dir):
    import puzzle_state as ps
    assert ps._load_solved_ids() == set()


def test_load_solved_ids_returns_set_of_ids(puz_dir):
    import puzzle_state as ps
    _write_json(puz_dir.solved_file, ['abc', 'def', 'ghi'])
    assert ps._load_solved_ids() == {'abc', 'def', 'ghi'}


def test_load_solved_ids_tolerates_corrupt_json(puz_dir):
    import puzzle_state as ps
    with open(puz_dir.solved_file, 'w') as f:
        f.write('not-valid-json{{')
    assert ps._load_solved_ids() == set()


def test_load_solved_ids_empty_list_gives_empty_set(puz_dir):
    import puzzle_state as ps
    _write_json(puz_dir.solved_file, [])
    assert ps._load_solved_ids() == set()


# ---------------------------------------------------------------------------
# load_unsolved
# ---------------------------------------------------------------------------

def _make_puzzle(pid, rating=1500):
    return {
        'id': pid,
        'fen': 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        'solution': 'e2e4',
        'rating': rating,
    }


def test_load_unsolved_no_file_returns_empty_list(puz_dir):
    import puzzle_state as ps
    assert ps.load_unsolved() == []


def test_load_unsolved_returns_all_when_none_solved(puz_dir):
    import puzzle_state as ps
    puzzles = [_make_puzzle('p1'), _make_puzzle('p2'), _make_puzzle('p3')]
    _write_json(puz_dir.puzzle_file, {'version': 1, 'puzzles': puzzles})
    result = ps.load_unsolved()
    assert len(result) == 3
    assert [p['id'] for p in result] == ['p1', 'p2', 'p3']


def test_load_unsolved_excludes_solved_puzzles(puz_dir):
    import puzzle_state as ps
    puzzles = [_make_puzzle('p1'), _make_puzzle('p2'), _make_puzzle('p3')]
    _write_json(puz_dir.puzzle_file, {'version': 1, 'puzzles': puzzles})
    _write_json(puz_dir.solved_file, ['p1', 'p3'])
    result = ps.load_unsolved()
    assert len(result) == 1
    assert result[0]['id'] == 'p2'


def test_load_unsolved_all_solved_returns_empty(puz_dir):
    import puzzle_state as ps
    puzzles = [_make_puzzle('p1'), _make_puzzle('p2')]
    _write_json(puz_dir.puzzle_file, {'version': 1, 'puzzles': puzzles})
    _write_json(puz_dir.solved_file, ['p1', 'p2'])
    assert ps.load_unsolved() == []


def test_load_unsolved_corrupt_puzzle_file_returns_empty(puz_dir):
    import puzzle_state as ps
    with open(puz_dir.puzzle_file, 'w') as f:
        f.write('{bad json')
    assert ps.load_unsolved() == []


def test_load_unsolved_missing_puzzles_key_returns_empty(puz_dir):
    import puzzle_state as ps
    _write_json(puz_dir.puzzle_file, {'version': 1})
    assert ps.load_unsolved() == []


def test_load_unsolved_preserves_order(puz_dir):
    import puzzle_state as ps
    puzzles = [_make_puzzle(f'p{i}') for i in range(5)]
    _write_json(puz_dir.puzzle_file, {'version': 1, 'puzzles': puzzles})
    result = ps.load_unsolved()
    assert [p['id'] for p in result] == [f'p{i}' for i in range(5)]


# ---------------------------------------------------------------------------
# total_available
# ---------------------------------------------------------------------------

def test_total_available_no_file_returns_zero(puz_dir):
    import puzzle_state as ps
    assert ps.total_available() == 0


def test_total_available_counts_all_puzzles(puz_dir):
    import puzzle_state as ps
    puzzles = [_make_puzzle(f'p{i}') for i in range(7)]
    _write_json(puz_dir.puzzle_file, {'version': 1, 'puzzles': puzzles})
    assert ps.total_available() == 7


def test_total_available_includes_solved(puz_dir):
    import puzzle_state as ps
    puzzles = [_make_puzzle('p1'), _make_puzzle('p2'), _make_puzzle('p3')]
    _write_json(puz_dir.puzzle_file, {'version': 1, 'puzzles': puzzles})
    _write_json(puz_dir.solved_file, ['p1'])
    # total_available does NOT subtract solved — it counts raw storage
    assert ps.total_available() == 3


def test_total_available_empty_list_returns_zero(puz_dir):
    import puzzle_state as ps
    _write_json(puz_dir.puzzle_file, {'version': 1, 'puzzles': []})
    assert ps.total_available() == 0


def test_total_available_corrupt_file_returns_zero(puz_dir):
    import puzzle_state as ps
    with open(puz_dir.puzzle_file, 'w') as f:
        f.write('not json')
    assert ps.total_available() == 0


# ---------------------------------------------------------------------------
# mark_solved
# ---------------------------------------------------------------------------

def test_mark_solved_creates_solved_file(puz_dir):
    import puzzle_state as ps
    ps.mark_solved('abc123')
    assert os.path.exists(puz_dir.solved_file)
    with open(puz_dir.solved_file) as f:
        data = json.load(f)
    assert 'abc123' in data


def test_mark_solved_accumulates_multiple_ids(puz_dir):
    import puzzle_state as ps
    ps.mark_solved('id1')
    ps.mark_solved('id2')
    ps.mark_solved('id3')
    solved = ps._load_solved_ids()
    assert solved == {'id1', 'id2', 'id3'}


def test_mark_solved_idempotent(puz_dir):
    import puzzle_state as ps
    ps.mark_solved('dup')
    ps.mark_solved('dup')
    solved = ps._load_solved_ids()
    assert solved == {'dup'}


def test_mark_solved_integrates_with_load_unsolved(puz_dir):
    import puzzle_state as ps
    puzzles = [_make_puzzle('p1'), _make_puzzle('p2')]
    _write_json(puz_dir.puzzle_file, {'version': 1, 'puzzles': puzzles})

    ps.mark_solved('p1')
    result = ps.load_unsolved()
    assert len(result) == 1
    assert result[0]['id'] == 'p2'


def test_mark_solved_creates_puzzle_dir_if_missing(tmp_path, monkeypatch):
    import puzzle_state as ps
    new_dir = str(tmp_path / 'new' / 'nested' / 'dir')
    monkeypatch.setattr(ps, 'PUZZLE_DIR',  new_dir)
    monkeypatch.setattr(ps, 'SOLVED_FILE', os.path.join(new_dir, 'solved.json'))
    ps.mark_solved('x')
    assert os.path.exists(os.path.join(new_dir, 'solved.json'))