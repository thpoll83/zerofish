"""Tests for pure-logic helpers: san_with_glyph and game_over_message."""
import chess
import ui
from screen_game_over import game_over_message


# ── san_with_glyph ────────────────────────────────────────────────────────────

def test_pawn_move_unchanged():
    assert ui.san_with_glyph('e4') == 'e4'


def test_pawn_capture_unchanged():
    assert ui.san_with_glyph('exd5') == 'exd5'


def test_knight_substituted():
    assert ui.san_with_glyph('Nf3') == '♞f3'


def test_bishop_substituted():
    assert ui.san_with_glyph('Bc4') == '♝c4'


def test_rook_substituted():
    assert ui.san_with_glyph('Rd1') == '♜d1'


def test_queen_substituted():
    assert ui.san_with_glyph('Qxd5') == '♛xd5'


def test_king_substituted():
    assert ui.san_with_glyph('Ke1') == '♚e1'


def test_promotion_queen():
    assert ui.san_with_glyph('e8=Q') == 'e8=♛'


def test_promotion_knight():
    assert ui.san_with_glyph('a1=N') == 'a1=♞'


def test_promotion_rook():
    assert ui.san_with_glyph('h8=R') == 'h8=♜'


def test_empty_string():
    assert ui.san_with_glyph('') == ''


def test_check_annotation_preserved():
    result = ui.san_with_glyph('Nf3+')
    assert result == '♞f3+'


def test_castling_unchanged():
    assert ui.san_with_glyph('O-O')   == 'O-O'
    assert ui.san_with_glyph('O-O-O') == 'O-O-O'


# ── game_over_message ─────────────────────────────────────────────────────────

def test_checkmate_player_loses():
    # Fool's mate: black checkmated white — player is white, so player loses
    board = chess.Board('rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3')
    assert board.is_checkmate()
    line1, line2 = game_over_message(board, player_is_white=True)
    assert line1 == 'You lose'
    assert line2 == 'Checkmate'


def test_checkmate_player_wins():
    # Same position; now player is black — black gave checkmate, so player wins
    board = chess.Board('rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3')
    line1, line2 = game_over_message(board, player_is_white=False)
    assert line1 == 'You win!'
    assert line2 == 'Checkmate'


def test_stalemate():
    # Black king on a8 is stalemated (Ka6, Qb6)
    board = chess.Board('k7/8/KQ6/8/8/8/8/8 b - - 0 1')
    assert board.is_stalemate()
    line1, line2 = game_over_message(board, player_is_white=True)
    assert line1 == 'Draw'
    assert line2 == 'Stalemate'


def test_insufficient_material():
    # King vs King — dead draw
    board = chess.Board('k7/8/8/8/8/8/8/7K w - - 0 1')
    assert board.is_insufficient_material()
    line1, line2 = game_over_message(board, player_is_white=True)
    assert line1 == 'Draw'
    assert 'material' in line2.lower()
