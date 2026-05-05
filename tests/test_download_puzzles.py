"""Tests for the helper functions in deploy/download_puzzles.py.

The module is not on sys.path (it lives in deploy/, not zerofish/), so we
import it explicitly via importlib.  Only the pure, file-I/O helper functions
are tested here — main() requires network access and is excluded.
"""

import importlib.util
import json
import os
import sys
import pytest


def _load_module(tmp_puzzle_dir: str):
    """Load deploy/download_puzzles.py with PUZZLE_DIR / OUT_FILE redirected."""
    import types

    repo_root = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    )
    module_path = os.path.join(repo_root, 'deploy', 'download_puzzles.py')

    spec = importlib.util.spec_from_file_location('download_puzzles', module_path)
    mod  = importlib.util.module_from_spec(spec)

    # Stub sys.argv so TARGET = 200 (default) and no argv[1] side-effect
    orig_argv = sys.argv[:]
    sys.argv = ['download_puzzles.py']

    # Stub chess if not already importable (download_puzzles imports it at module level)
    chess_was_present = 'chess' in sys.modules
    if not chess_was_present:
        sys.modules.setdefault('chess', types.ModuleType('chess'))

    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = orig_argv
        if not chess_was_present:
            sys.modules.pop('chess', None)

    # Redirect the module's globals to the temp directory
    mod.PUZZLE_DIR = tmp_puzzle_dir
    mod.OUT_FILE   = os.path.join(tmp_puzzle_dir, 'puzzles.json')

    return mod


@pytest.fixture
def dp(tmp_path):
    """Return the download_puzzles module pointing at a temp directory."""
    return _load_module(str(tmp_path))


# ── _load_solved_ids ──────────────────────────────────────────────────────────

def test_dp_load_solved_ids_no_file(dp):
    assert dp._load_solved_ids() == set()


def test_dp_load_solved_ids_returns_set(dp, tmp_path):
    solved_file = os.path.join(dp.PUZZLE_DIR, 'solved.json')
    with open(solved_file, 'w') as f:
        json.dump(['id1', 'id2', 'id3'], f)
    result = dp._load_solved_ids()
    assert isinstance(result, set)
    assert result == {'id1', 'id2', 'id3'}


def test_dp_load_solved_ids_malformed_json(dp):
    solved_file = os.path.join(dp.PUZZLE_DIR, 'solved.json')
    os.makedirs(dp.PUZZLE_DIR, exist_ok=True)
    with open(solved_file, 'w') as f:
        f.write('!!! not json')
    assert dp._load_solved_ids() == set()


def test_dp_load_solved_ids_empty_list(dp):
    solved_file = os.path.join(dp.PUZZLE_DIR, 'solved.json')
    os.makedirs(dp.PUZZLE_DIR, exist_ok=True)
    with open(solved_file, 'w') as f:
        json.dump([], f)
    assert dp._load_solved_ids() == set()


def test_dp_load_solved_ids_deduplicates(dp):
    """Even if JSON contains duplicates (shouldn't happen), set removes them."""
    solved_file = os.path.join(dp.PUZZLE_DIR, 'solved.json')
    os.makedirs(dp.PUZZLE_DIR, exist_ok=True)
    with open(solved_file, 'w') as f:
        json.dump(['x', 'x', 'y'], f)
    result = dp._load_solved_ids()
    assert result == {'x', 'y'}


# ── _existing_ids ─────────────────────────────────────────────────────────────

def test_dp_existing_ids_no_file(dp):
    assert dp._existing_ids() == set()


def test_dp_existing_ids_returns_set(dp):
    puzzles = [
        {'id': 'aaa', 'fen': 'f1', 'solution': 'e2e4', 'rating': 1500},
        {'id': 'bbb', 'fen': 'f2', 'solution': 'd2d4', 'rating': 1600},
    ]
    os.makedirs(dp.PUZZLE_DIR, exist_ok=True)
    with open(dp.OUT_FILE, 'w') as f:
        json.dump({'version': 1, 'puzzles': puzzles}, f)
    result = dp._existing_ids()
    assert result == {'aaa', 'bbb'}


def test_dp_existing_ids_empty_puzzles_key(dp):
    os.makedirs(dp.PUZZLE_DIR, exist_ok=True)
    with open(dp.OUT_FILE, 'w') as f:
        json.dump({'version': 1, 'puzzles': []}, f)
    assert dp._existing_ids() == set()


def test_dp_existing_ids_missing_puzzles_key(dp):
    os.makedirs(dp.PUZZLE_DIR, exist_ok=True)
    with open(dp.OUT_FILE, 'w') as f:
        json.dump({'version': 1}, f)
    assert dp._existing_ids() == set()


def test_dp_existing_ids_malformed_json(dp):
    os.makedirs(dp.PUZZLE_DIR, exist_ok=True)
    with open(dp.OUT_FILE, 'w') as f:
        f.write('{bad json')
    assert dp._existing_ids() == set()


# ── Interaction between solved and existing ───────────────────────────────────

def test_dp_skip_ids_union_of_solved_and_existing(dp):
    """Verify the union logic used in main(): solved ∪ existing = skip_ids."""
    os.makedirs(dp.PUZZLE_DIR, exist_ok=True)
    # Write puzzles.json with two puzzles
    with open(dp.OUT_FILE, 'w') as f:
        json.dump({'version': 1, 'puzzles': [
            {'id': 'ex1', 'fen': 'f', 'solution': 'e2e4', 'rating': 1500},
        ]}, f)
    # Write solved.json with one solved id (not in existing)
    solved_file = os.path.join(dp.PUZZLE_DIR, 'solved.json')
    with open(solved_file, 'w') as f:
        json.dump(['sol1'], f)

    solved   = dp._load_solved_ids()
    existing = dp._existing_ids()
    skip_ids = solved | existing
    assert skip_ids == {'sol1', 'ex1'}


# ── Module constants ──────────────────────────────────────────────────────────

def test_dp_collect_is_five_times_target(dp):
    """COLLECT should be TARGET * 5 for the sampling strategy."""
    assert dp.COLLECT == dp.TARGET * 5


def test_dp_default_target_is_200():
    """Default TARGET when no argv[1] is given should be 200."""
    import types
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        m = _load_module(td)
    assert m.TARGET == 200