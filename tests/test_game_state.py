"""Tests for game_state save/load/clear persistence."""
import json
import chess
import game_state


def test_save_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr(game_state, 'SAVE_PATH', str(tmp_path / 'save.json'))

    board = chess.Board()
    board.push_uci('e2e4')
    game_state.save(board, ['e4'], True, 5)

    data = game_state.load()
    assert data is not None
    assert data['diff_sel'] == 5
    assert data['player_is_white'] is True
    assert data['move_history'] == ['e4']
    # The saved FEN should reconstruct the same position
    assert chess.Board(data['fen']) == board


def test_load_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(game_state, 'SAVE_PATH', str(tmp_path / 'nothing.json'))
    assert game_state.load() is None


def test_clear_marks_ended_cleanly(tmp_path, monkeypatch):
    path = str(tmp_path / 'save.json')
    monkeypatch.setattr(game_state, 'SAVE_PATH', path)

    game_state.save(chess.Board(), [], True, 1)
    game_state.clear()

    with open(path) as f:
        data = json.load(f)
    assert data['ended_cleanly'] is True


def test_load_after_clear_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(game_state, 'SAVE_PATH', str(tmp_path / 'save.json'))

    game_state.save(chess.Board(), [], True, 1)
    game_state.clear()
    assert game_state.load() is None


def test_load_corrupt_json(tmp_path, monkeypatch):
    path = str(tmp_path / 'save.json')
    monkeypatch.setattr(game_state, 'SAVE_PATH', path)
    path_obj = tmp_path / 'save.json'
    path_obj.write_text('not valid json')
    assert game_state.load() is None


def test_load_invalid_fen(tmp_path, monkeypatch):
    path = str(tmp_path / 'save.json')
    monkeypatch.setattr(game_state, 'SAVE_PATH', path)
    with open(path, 'w') as f:
        json.dump({'fen': 'garbage', 'ended_cleanly': False,
                   'move_history': [], 'player_is_white': True, 'diff_sel': 1}, f)
    assert game_state.load() is None


def test_clear_nonexistent_file(tmp_path, monkeypatch):
    monkeypatch.setattr(game_state, 'SAVE_PATH', str(tmp_path / 'nothing.json'))
    game_state.clear()   # should not raise


def test_roundtrip_mid_game(tmp_path, monkeypatch):
    monkeypatch.setattr(game_state, 'SAVE_PATH', str(tmp_path / 'save.json'))

    board = chess.Board()
    moves = []
    for uci in ('e2e4', 'e7e5', 'g1f3', 'b8c6', 'f1b5'):
        san = board.san(chess.Move.from_uci(uci))
        board.push_uci(uci)
        moves.append(san)

    game_state.save(board, moves, True, 10)
    data = game_state.load()

    assert data is not None
    assert data['move_history'] == moves
    assert chess.Board(data['fen']) == board
