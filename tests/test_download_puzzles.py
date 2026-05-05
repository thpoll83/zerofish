"""Tests for deploy/download_puzzles.py helper functions.

Tests cover _load_solved_ids() and _existing_ids() — the two pure helper
functions that do not require network access or the zstandard package.
main() is not tested here because it requires a live network connection.
"""
import json
import os
import sys
import importlib
import types

import pytest

# Add deploy/ directory to sys.path so download_puzzles can be imported.
_DEPLOY_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'deploy')
)
if _DEPLOY_DIR not in sys.path:
    sys.path.insert(0, _DEPLOY_DIR)

# download_puzzles.py evaluates `int(sys.argv[1])` at import time when extra
# argv entries are present (e.g. when pytest passes test-file paths).
# Temporarily clean sys.argv so the import succeeds with the default TARGET.
_saved_argv = sys.argv[:]
sys.argv = sys.argv[:1]

import download_puzzles as _dp_module  # noqa: E402

sys.argv = _saved_argv


@pytest.fixture(autouse=True)
def _isolated_module(tmp_path, monkeypatch):
    """Redirect download_puzzles to use a fresh temporary directory.

    We patch PUZZLE_DIR and OUT_FILE on the already-imported module so each
    test gets its own clean temporary directory.
    """
    puzzle_dir = str(tmp_path / 'puzzles')
    out_file   = os.path.join(puzzle_dir, 'puzzles.json')
    os.makedirs(puzzle_dir, exist_ok=True)
    monkeypatch.setattr(_dp_module, 'PUZZLE_DIR', puzzle_dir)
    monkeypatch.setattr(_dp_module, 'OUT_FILE',   out_file)


def _get_dp():
    return _dp_module


# ---------------------------------------------------------------------------
# _load_solved_ids
# ---------------------------------------------------------------------------

def test_load_solved_ids_returns_empty_set_when_no_file(tmp_path):
    dp = _get_dp()
    # PUZZLE_DIR/solved.json does not exist (tmp dir is empty)
    assert dp._load_solved_ids() == set()


def test_load_solved_ids_reads_json_list(tmp_path):
    dp = _get_dp()
    solved_path = os.path.join(dp.PUZZLE_DIR, 'solved.json')
    with open(solved_path, 'w') as f:
        json.dump(['aaa', 'bbb', 'ccc'], f)
    result = dp._load_solved_ids()
    assert result == {'aaa', 'bbb', 'ccc'}


def test_load_solved_ids_returns_set_type(tmp_path):
    dp = _get_dp()
    solved_path = os.path.join(dp.PUZZLE_DIR, 'solved.json')
    with open(solved_path, 'w') as f:
        json.dump(['x'], f)
    assert isinstance(dp._load_solved_ids(), set)


def test_load_solved_ids_tolerates_corrupt_json(tmp_path):
    dp = _get_dp()
    solved_path = os.path.join(dp.PUZZLE_DIR, 'solved.json')
    with open(solved_path, 'w') as f:
        f.write('{{ not valid json')
    assert dp._load_solved_ids() == set()


def test_load_solved_ids_empty_list_gives_empty_set(tmp_path):
    dp = _get_dp()
    solved_path = os.path.join(dp.PUZZLE_DIR, 'solved.json')
    with open(solved_path, 'w') as f:
        json.dump([], f)
    assert dp._load_solved_ids() == set()


# ---------------------------------------------------------------------------
# _existing_ids
# ---------------------------------------------------------------------------

def test_existing_ids_returns_empty_set_when_no_file(tmp_path):
    dp = _get_dp()
    assert dp._existing_ids() == set()


def test_existing_ids_reads_puzzle_ids(tmp_path):
    dp = _get_dp()
    data = {
        'version': 1,
        'puzzles': [
            {'id': 'p1', 'fen': 'rnbq...', 'solution': 'e2e4', 'rating': 1500},
            {'id': 'p2', 'fen': 'rnbq...', 'solution': 'd2d4', 'rating': 1600},
        ],
    }
    with open(dp.OUT_FILE, 'w') as f:
        json.dump(data, f)
    result = dp._existing_ids()
    assert result == {'p1', 'p2'}


def test_existing_ids_returns_set_type(tmp_path):
    dp = _get_dp()
    data = {'version': 1, 'puzzles': [{'id': 'only', 'fen': '', 'solution': '', 'rating': 1500}]}
    with open(dp.OUT_FILE, 'w') as f:
        json.dump(data, f)
    assert isinstance(dp._existing_ids(), set)


def test_existing_ids_empty_puzzle_list(tmp_path):
    dp = _get_dp()
    with open(dp.OUT_FILE, 'w') as f:
        json.dump({'version': 1, 'puzzles': []}, f)
    assert dp._existing_ids() == set()


def test_existing_ids_missing_puzzles_key(tmp_path):
    dp = _get_dp()
    with open(dp.OUT_FILE, 'w') as f:
        json.dump({'version': 1}, f)
    assert dp._existing_ids() == set()


def test_existing_ids_tolerates_corrupt_json(tmp_path):
    dp = _get_dp()
    with open(dp.OUT_FILE, 'w') as f:
        f.write('not { valid')
    assert dp._existing_ids() == set()


def test_existing_ids_many_puzzles(tmp_path):
    dp = _get_dp()
    puzzles = [{'id': f'id{i}', 'fen': '', 'solution': '', 'rating': 1500}
               for i in range(50)]
    with open(dp.OUT_FILE, 'w') as f:
        json.dump({'version': 1, 'puzzles': puzzles}, f)
    result = dp._existing_ids()
    assert len(result) == 50
    assert f'id{0}' in result
    assert f'id{49}' in result


# ---------------------------------------------------------------------------
# Skip logic: solved ∪ existing = skip_ids (integration of the two helpers)
# ---------------------------------------------------------------------------

def test_skip_ids_union(tmp_path):
    """Solved IDs and existing IDs should union to the full skip set."""
    dp = _get_dp()
    # Write solved.json
    solved_path = os.path.join(dp.PUZZLE_DIR, 'solved.json')
    with open(solved_path, 'w') as f:
        json.dump(['sol1', 'sol2'], f)
    # Write puzzles.json with existing IDs
    with open(dp.OUT_FILE, 'w') as f:
        json.dump({'version': 1, 'puzzles': [
            {'id': 'ex1', 'fen': '', 'solution': '', 'rating': 1500},
            {'id': 'ex2', 'fen': '', 'solution': '', 'rating': 1500},
        ]}, f)

    solved   = dp._load_solved_ids()
    existing = dp._existing_ids()
    skip_ids = solved | existing
    assert skip_ids == {'sol1', 'sol2', 'ex1', 'ex2'}


def test_skip_ids_overlap_deduplicated(tmp_path):
    """An ID that appears in both solved and existing is counted only once."""
    dp = _get_dp()
    solved_path = os.path.join(dp.PUZZLE_DIR, 'solved.json')
    with open(solved_path, 'w') as f:
        json.dump(['dup'], f)
    with open(dp.OUT_FILE, 'w') as f:
        json.dump({'version': 1, 'puzzles': [
            {'id': 'dup', 'fen': '', 'solution': '', 'rating': 1500},
        ]}, f)

    skip_ids = dp._load_solved_ids() | dp._existing_ids()
    assert skip_ids == {'dup'}
    assert len(skip_ids) == 1


# ---------------------------------------------------------------------------
# Module-level constants sanity checks
# ---------------------------------------------------------------------------

def test_default_target_is_200():
    """TARGET defaults to 200 when no command-line argument is supplied."""
    dp = _get_dp()
    # TARGET is set at import time; with no extra argv it should be 200.
    assert dp.TARGET == 200


def test_collect_is_five_times_target():
    dp = _get_dp()
    assert dp.COLLECT == dp.TARGET * 5


def test_puzzle_url_is_lichess():
    dp = _get_dp()
    assert 'lichess.org' in dp.PUZZLE_URL
    assert dp.PUZZLE_URL.endswith('.zst')