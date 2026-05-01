"""Tests for move-candidate lookup and promotion detection."""
import chess
from screen_player_move import find_candidates, needs_promotion

# PIECES index map: 0=P 1=N 2=B 3=R 4=Q 5=K
P, N, B, R, Q, K = 0, 1, 2, 3, 4, 5


# ── find_candidates ───────────────────────────────────────────────────────────

def test_pawn_e4_from_start():
    board = chess.Board()
    moves = find_candidates(board, P, 4, 3)   # pawn to e4 (file=4, rank=3)
    assert len(moves) == 1
    assert moves[0] == chess.Move.from_uci('e2e4')


def test_pawn_e3_from_start():
    board = chess.Board()
    moves = find_candidates(board, P, 4, 2)   # pawn to e3
    assert len(moves) == 1
    assert moves[0] == chess.Move.from_uci('e2e3')


def test_knight_c3_from_start():
    board = chess.Board()
    moves = find_candidates(board, N, 2, 2)   # knight to c3
    assert len(moves) == 1
    assert moves[0] == chess.Move.from_uci('b1c3')


def test_no_candidates_for_illegal_move():
    board = chess.Board()
    # King cannot move to e5 from the starting position
    moves = find_candidates(board, K, 4, 4)
    assert moves == []


def test_no_candidates_wrong_piece_type():
    board = chess.Board()
    # There is a pawn on e2 but asking for a rook there should return nothing
    moves = find_candidates(board, R, 4, 3)   # rook to e4 — no rook can go there
    assert moves == []


def test_disambiguation_two_rooks_same_target():
    # Two white rooks on a1 and g1; both can reach d1
    board = chess.Board('7k/8/8/8/8/8/8/R5RK w - - 0 1')
    moves = find_candidates(board, R, 3, 0)   # rook to d1 (file=3, rank=0)
    assert len(moves) == 2


def test_single_rook_no_ambiguity():
    board = chess.Board('7k/8/8/8/8/8/8/R6K w - - 0 1')
    moves = find_candidates(board, R, 3, 0)   # rook a1 to d1
    assert len(moves) == 1


def test_blocked_pawn():
    # White pawn on e2, black pawn on e3 — e2e3 and e2e4 are both blocked
    board = chess.Board('k7/8/8/8/8/4p3/4P3/7K w - - 0 1')
    assert find_candidates(board, P, 4, 2) == []
    assert find_candidates(board, P, 4, 3) == []


def test_pawn_capture():
    # White pawn on e4, black pawn on d5 — exd5 is a legal capture
    board = chess.Board('k7/8/8/3p4/4P3/8/8/7K w - - 0 1')
    moves = find_candidates(board, P, 3, 4)   # pawn to d5
    assert len(moves) == 1
    assert moves[0] == chess.Move.from_uci('e4d5')


# ── needs_promotion ───────────────────────────────────────────────────────────

def test_needs_promotion_pawn_on_seventh():
    # White pawn on e7 about to promote to e8
    board = chess.Board('k7/4P3/8/8/8/8/8/4K3 w - - 0 1')
    assert needs_promotion(board, P, 4, 7) is True


def test_needs_promotion_not_back_rank():
    board = chess.Board()
    assert needs_promotion(board, P, 4, 5) is False


def test_needs_promotion_not_a_pawn():
    board = chess.Board('k7/4P3/8/8/8/8/8/4K3 w - - 0 1')
    assert needs_promotion(board, N, 4, 7) is False


def test_needs_promotion_normal_pawn_advance():
    board = chess.Board()
    assert needs_promotion(board, P, 4, 3) is False   # e4 is not a promotion


def test_needs_promotion_black_pawn():
    # Black pawn on e2 about to promote to e1; white king on h1 (not blocking)
    board = chess.Board('k7/8/8/8/8/8/4p3/7K b - - 0 1')
    assert needs_promotion(board, P, 4, 0) is True
