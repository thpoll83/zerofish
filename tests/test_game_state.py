"""Tests for game_state save/load/clear persistence."""
import json
import os
import chess
import game_state


def test_save_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr(game_state, 'SAVE_DIR', str(tmp_path))

    board = chess.Board()
    board.push_uci('e2e4')
    path = game_state.save(board, ['e4'], True, 5)

    data = game_state.load(path)
    assert data is not None
    assert data['diff_sel'] == 5
    assert data['player_is_white'] is True
    assert data['move_history'] == ['e4']
    assert chess.Board(data['fen']) == board


def test_load_missing_file(tmp_path):
    assert game_state.load(str(tmp_path / 'nothing.json')) is None


def test_clear_deletes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(game_state, 'SAVE_DIR', str(tmp_path))
    path = game_state.save(chess.Board(), [], True, 1)
    assert os.path.exists(path)
    game_state.clear(path)
    assert not os.path.exists(path)


def test_load_after_clear_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(game_state, 'SAVE_DIR', str(tmp_path))
    path = game_state.save(chess.Board(), [], True, 1)
    game_state.clear(path)
    assert game_state.load(path) is None


def test_load_corrupt_json(tmp_path):
    path = tmp_path / 'save.json'
    path.write_text('not valid json')
    assert game_state.load(str(path)) is None


def test_load_invalid_fen(tmp_path):
    path = str(tmp_path / 'save.json')
    with open(path, 'w') as f:
        json.dump({'fen': 'garbage', 'ended_cleanly': False,
                   'move_history': [], 'player_is_white': True, 'diff_sel': 1}, f)
    assert game_state.load(path) is None


def test_clear_nonexistent_file(tmp_path):
    game_state.clear(str(tmp_path / 'nothing.json'))  # should not raise


def test_roundtrip_mid_game(tmp_path, monkeypatch):
    monkeypatch.setattr(game_state, 'SAVE_DIR', str(tmp_path))

    board = chess.Board()
    moves = []
    for uci in ('e2e4', 'e7e5', 'g1f3', 'b8c6', 'f1b5'):
        san = board.san(chess.Move.from_uci(uci))
        board.push_uci(uci)
        moves.append(san)

    path = game_state.save(board, moves, True, 10)
    data = game_state.load(path)

    assert data is not None
    assert data['move_history'] == moves
    assert chess.Board(data['fen']) == board
