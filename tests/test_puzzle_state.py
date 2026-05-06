"""Tests for puzzle_state.py (load/persist puzzle data)."""

import json
import os
import pytest
import puzzle_state


def _write_puzzles(path, puzzles):
    with open(path, 'w') as f:
        json.dump({'version': 1, 'puzzles': puzzles}, f)


def _write_solved(path, ids):
    with open(path, 'w') as f:
        json.dump(list(ids), f)


def _patch(monkeypatch, tmp_path):
    """Point puzzle_state at a temporary directory and return (puzzle_file, solved_file)."""
    puzzle_dir = str(tmp_path)
    puzzle_file = os.path.join(puzzle_dir, 'puzzles.json')
    solved_file = os.path.join(puzzle_dir, 'solved.json')
    monkeypatch.setattr(puzzle_state, 'PUZZLE_DIR',  puzzle_dir)
    monkeypatch.setattr(puzzle_state, 'PUZZLE_FILE', puzzle_file)
    monkeypatch.setattr(puzzle_state, 'SOLVED_FILE', solved_file)
    return puzzle_file, solved_file


# ── load_unsolved ─────────────────────────────────────────────────────────────

def test_load_unsolved_no_file(monkeypatch, tmp_path):
    _patch(monkeypatch, tmp_path)
    assert puzzle_state.load_unsolved() == []


def test_load_unsolved_empty_puzzles(monkeypatch, tmp_path):
    pf, _ = _patch(monkeypatch, tmp_path)
    _write_puzzles(pf, [])
    assert puzzle_state.load_unsolved() == []


def test_load_unsolved_all_unsolved(monkeypatch, tmp_path):
    pf, _ = _patch(monkeypatch, tmp_path)
    puzzles = [
        {'id': 'a1', 'fen': 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1',
         'solution': 'e7e5', 'rating': 1500},
        {'id': 'b2', 'fen': 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1',
         'solution': 'd7d5', 'rating': 1600},
    ]
    _write_puzzles(pf, puzzles)
    result = puzzle_state.load_unsolved()
    assert len(result) == 2
    assert result[0]['id'] == 'a1'
    assert result[1]['id'] == 'b2'


def test_load_unsolved_filters_solved(monkeypatch, tmp_path):
    pf, sf = _patch(monkeypatch, tmp_path)
    puzzles = [
        {'id': 'a1', 'fen': 'fen1', 'solution': 'e2e4', 'rating': 1500},
        {'id': 'b2', 'fen': 'fen2', 'solution': 'd2d4', 'rating': 1600},
        {'id': 'c3', 'fen': 'fen3', 'solution': 'c2c4', 'rating': 1700},
    ]
    _write_puzzles(pf, puzzles)
    _write_solved(sf, {'a1', 'c3'})
    result = puzzle_state.load_unsolved()
    assert len(result) == 1
    assert result[0]['id'] == 'b2'


def test_load_unsolved_all_solved(monkeypatch, tmp_path):
    pf, sf = _patch(monkeypatch, tmp_path)
    puzzles = [
        {'id': 'x', 'fen': 'fen1', 'solution': 'e2e4', 'rating': 1500},
    ]
    _write_puzzles(pf, puzzles)
    _write_solved(sf, {'x'})
    assert puzzle_state.load_unsolved() == []


def test_load_unsolved_malformed_json(monkeypatch, tmp_path):
    pf, _ = _patch(monkeypatch, tmp_path)
    with open(pf, 'w') as f:
        f.write('NOT VALID JSON{{{')
    assert puzzle_state.load_unsolved() == []


def test_load_unsolved_missing_puzzles_key(monkeypatch, tmp_path):
    pf, _ = _patch(monkeypatch, tmp_path)
    with open(pf, 'w') as f:
        json.dump({'version': 1}, f)
    assert puzzle_state.load_unsolved() == []


def test_load_unsolved_preserves_order(monkeypatch, tmp_path):
    pf, sf = _patch(monkeypatch, tmp_path)
    puzzles = [{'id': f'p{i}', 'fen': f'fen{i}', 'solution': 'e2e4', 'rating': 1500}
               for i in range(5)]
    _write_puzzles(pf, puzzles)
    _write_solved(sf, {'p1', 'p3'})
    result = puzzle_state.load_unsolved()
    assert [p['id'] for p in result] == ['p0', 'p2', 'p4']


# ── total_available ───────────────────────────────────────────────────────────

def test_total_available_no_file(monkeypatch, tmp_path):
    _patch(monkeypatch, tmp_path)
    assert puzzle_state.total_available() == 0


def test_total_available_empty(monkeypatch, tmp_path):
    pf, _ = _patch(monkeypatch, tmp_path)
    _write_puzzles(pf, [])
    assert puzzle_state.total_available() == 0


def test_total_available_counts_all(monkeypatch, tmp_path):
    pf, sf = _patch(monkeypatch, tmp_path)
    puzzles = [{'id': f'p{i}', 'fen': 'f', 'solution': 'e2e4', 'rating': 1500}
               for i in range(7)]
    _write_puzzles(pf, puzzles)
    # Even if some are solved, total_available counts all in the file
    _write_solved(sf, {'p0', 'p1', 'p2'})
    assert puzzle_state.total_available() == 7


def test_total_available_malformed_json(monkeypatch, tmp_path):
    pf, _ = _patch(monkeypatch, tmp_path)
    with open(pf, 'w') as f:
        f.write('{broken}')
    assert puzzle_state.total_available() == 0


# ── mark_solved ───────────────────────────────────────────────────────────────

def test_mark_solved_creates_solved_file(monkeypatch, tmp_path):
    _, sf = _patch(monkeypatch, tmp_path)
    assert not os.path.exists(sf)
    puzzle_state.mark_solved('abc')
    assert os.path.exists(sf)
    with open(sf) as f:
        data = json.load(f)
    assert 'abc' in data


def test_mark_solved_adds_to_existing(monkeypatch, tmp_path):
    _, sf = _patch(monkeypatch, tmp_path)
    _write_solved(sf, {'id1'})
    puzzle_state.mark_solved('id2')
    with open(sf) as f:
        data = set(json.load(f))
    assert data == {'id1', 'id2'}


def test_mark_solved_idempotent(monkeypatch, tmp_path):
    _, sf = _patch(monkeypatch, tmp_path)
    puzzle_state.mark_solved('x')
    puzzle_state.mark_solved('x')
    with open(sf) as f:
        data = json.load(f)
    assert data.count('x') == 1


def test_mark_solved_creates_dir_if_missing(monkeypatch, tmp_path):
    nested = tmp_path / 'sub' / 'puzzles'
    pf = str(nested / 'puzzles.json')
    sf = str(nested / 'solved.json')
    monkeypatch.setattr(puzzle_state, 'PUZZLE_DIR',  str(nested))
    monkeypatch.setattr(puzzle_state, 'PUZZLE_FILE', pf)
    monkeypatch.setattr(puzzle_state, 'SOLVED_FILE', sf)
    puzzle_state.mark_solved('newid')
    assert os.path.exists(sf)


def test_mark_solved_then_load_unsolved_excludes_it(monkeypatch, tmp_path):
    pf, _ = _patch(monkeypatch, tmp_path)
    puzzles = [
        {'id': 'keep', 'fen': 'f1', 'solution': 'e2e4', 'rating': 1500},
        {'id': 'done', 'fen': 'f2', 'solution': 'd2d4', 'rating': 1600},
    ]
    _write_puzzles(pf, puzzles)
    puzzle_state.mark_solved('done')
    result = puzzle_state.load_unsolved()
    assert len(result) == 1
    assert result[0]['id'] == 'keep'


# ── _load_solved_ids (private, tested indirectly + directly) ──────────────────

def test_load_solved_ids_no_file(monkeypatch, tmp_path):
    _patch(monkeypatch, tmp_path)
    assert puzzle_state._load_solved_ids() == set()


def test_load_solved_ids_returns_set(monkeypatch, tmp_path):
    _, sf = _patch(monkeypatch, tmp_path)
    _write_solved(sf, ['a', 'b', 'c'])
    result = puzzle_state._load_solved_ids()
    assert isinstance(result, set)
    assert result == {'a', 'b', 'c'}


def test_load_solved_ids_malformed_json(monkeypatch, tmp_path):
    _, sf = _patch(monkeypatch, tmp_path)
    with open(sf, 'w') as f:
        f.write('!!! not json')
    assert puzzle_state._load_solved_ids() == set()