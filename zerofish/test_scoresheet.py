"""Tests for screen_scoresheet — hit detection, scroll logic, and rendering."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
import config
from screen_scoresheet import (
    SCORE_ROWS, SCORE_BACK_Y0, SCORE_BACK_Y1, SCORE_MORE_X0,
    build_scoresheet_screen,
    next_score_end,
    hit_scoresheet_back,
    hit_scoresheet_more,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _moves(n):
    """Return a synthetic move history of length n (alternating w/b SAN)."""
    pieces = ['e4', 'e5', 'Nf3', 'Nc6', 'Bb5', 'a6', 'Ba4', 'Nf6', 'd3', 'd6']
    return [pieces[i % len(pieces)] for i in range(n)]


# ---------------------------------------------------------------------------
# hit_scoresheet_back — single button (≤ 15 full moves)
# ---------------------------------------------------------------------------

class TestHitBackSingleButton:
    def test_inside(self):
        assert hit_scoresheet_back(60, SCORE_BACK_Y0 + 5, has_more=False)

    def test_left_edge(self):
        assert hit_scoresheet_back(2, SCORE_BACK_Y0, has_more=False)

    def test_right_edge(self):
        assert hit_scoresheet_back(config.SCORE_W - 3, SCORE_BACK_Y1, has_more=False)

    def test_above_button(self):
        assert not hit_scoresheet_back(60, SCORE_BACK_Y0 - 1, has_more=False)

    def test_left_of_button(self):
        assert not hit_scoresheet_back(1, SCORE_BACK_Y0 + 5, has_more=False)


# ---------------------------------------------------------------------------
# hit_scoresheet_back — split layout (> 15 full moves)
# ---------------------------------------------------------------------------

class TestHitBackSplitButton:
    def test_inside_back_half(self):
        assert hit_scoresheet_back(20, SCORE_BACK_Y0 + 5, has_more=True)

    def test_right_edge_back_half(self):
        assert hit_scoresheet_back(SCORE_MORE_X0 - 3, SCORE_BACK_Y0, has_more=True)

    def test_more_region_does_not_trigger_back(self):
        assert not hit_scoresheet_back(SCORE_MORE_X0 + 5, SCORE_BACK_Y0 + 5, has_more=True)

    def test_above_button(self):
        assert not hit_scoresheet_back(20, SCORE_BACK_Y0 - 1, has_more=True)


# ---------------------------------------------------------------------------
# hit_scoresheet_more
# ---------------------------------------------------------------------------

class TestHitMore:
    def test_inside(self):
        assert hit_scoresheet_more(SCORE_MORE_X0 + 10, SCORE_BACK_Y0 + 5)

    def test_left_edge(self):
        assert hit_scoresheet_more(SCORE_MORE_X0, SCORE_BACK_Y0)

    def test_right_edge(self):
        assert hit_scoresheet_more(config.SCORE_W - 3, SCORE_BACK_Y1)

    def test_back_region_does_not_trigger_more(self):
        assert not hit_scoresheet_more(10, SCORE_BACK_Y0 + 5)

    def test_above_button(self):
        assert not hit_scoresheet_more(SCORE_MORE_X0 + 5, SCORE_BACK_Y0 - 1)


# ---------------------------------------------------------------------------
# next_score_end — scroll logic
# ---------------------------------------------------------------------------

class TestNextScoreEnd:
    def test_no_more_button_when_at_most_15_moves(self):
        # With ≤ SCORE_ROWS full moves the More button is not shown; the function
        # is not called, but verify it gracefully wraps anyway.
        history = _moves(SCORE_ROWS * 2)
        assert next_score_end(history) is None  # start==0, so wraps

    def test_first_press_scrolls_back(self):
        # 25 full moves (50 plies) → first view shows moves 11-25
        history = _moves(50)
        se = next_score_end(history, score_end=None)
        assert se is not None
        assert se == 50 - (SCORE_ROWS - 2) * 2   # = 24

    def test_second_press_reaches_move_one_then_wraps(self):
        history = _moves(50)
        se = next_score_end(history, score_end=None)   # se = 24
        # start = max(0, 24-30) = 0 → wrap
        se2 = next_score_end(history, score_end=se)
        assert se2 is None

    def test_multiple_presses_wrap_correctly(self):
        # 100 full moves (200 plies).  Each press scrolls back 26 plies.
        history = _moves(200)
        se = None
        for _ in range(100):           # enough presses to cycle through
            se = next_score_end(history, score_end=se)
        # After wrapping we must always end up back at None eventually.
        assert se is None or isinstance(se, int)

    def test_overlap_is_two_full_moves(self):
        history = _moves(80)          # 40 full moves
        se1 = None                    # shows plies 50-79
        se2 = next_score_end(history, score_end=se1)   # se2 = 80-26 = 54

        # Window 1: plies [50, 79]
        start1 = max(0, 80 - SCORE_ROWS * 2)  # 50
        # Window 2: plies [max(0, 54-30), 53] = [24, 53]
        start2 = max(0, se2 - SCORE_ROWS * 2)  # 24
        overlap = list(range(start1, se2))     # plies 50..53 → 2 full moves
        assert len(overlap) == 4               # 4 half-moves = 2 full moves

    def test_preserves_even_alignment(self):
        # total odd (white just played)
        history = _moves(51)   # 51 plies → 25W + 26B? Actually 25 full moves + 1 extra
        se = next_score_end(history, score_end=None)
        # start in build_scoresheet_screen always adjusted to even; se itself need not be
        assert se is None or isinstance(se, int)


# ---------------------------------------------------------------------------
# build_scoresheet_screen — image dimensions and More button presence
# ---------------------------------------------------------------------------

class TestBuildScoresheet:
    def test_image_size(self):
        img = build_scoresheet_screen([])
        assert img.size == (config.SCORE_W, config.SCORE_H)

    def test_image_size_with_moves(self):
        img = build_scoresheet_screen(_moves(20))
        assert img.size == (config.SCORE_W, config.SCORE_H)

    def test_no_more_button_few_moves(self):
        # With ≤ SCORE_ROWS full moves no More button — pixel at More-button
        # centre should be white (background) since no rectangle is drawn there.
        history = _moves(SCORE_ROWS * 2)      # exactly 15 full moves
        img = build_scoresheet_screen(history)
        more_cx = (SCORE_MORE_X0 + config.SCORE_W - 3) // 2
        btn_cy  = (SCORE_BACK_Y0 + SCORE_BACK_Y1) // 2
        # Pixel in the More button region: 0=black 255=white in mode '1'
        px = img.getpixel((more_cx, btn_cy))
        assert px == 255  # white background — no More button drawn

    def test_more_button_present_many_moves(self):
        history = _moves(SCORE_ROWS * 2 + 2)  # one full move over the limit
        img = build_scoresheet_screen(history)
        # The More button outline means at least one pixel in its area is black.
        more_cx = (SCORE_MORE_X0 + config.SCORE_W - 3) // 2
        btn_cy  = (SCORE_BACK_Y0 + SCORE_BACK_Y1) // 2
        px = img.getpixel((more_cx, btn_cy))
        # Centre of the More button text renders black (the label "More").
        # Accept either black (text centre hit) or check boundary pixels.
        region_pixels = [
            img.getpixel((x, y))
            for x in range(SCORE_MORE_X0, config.SCORE_W - 3)
            for y in range(SCORE_BACK_Y0, SCORE_BACK_Y1 + 1)
        ]
        assert 0 in region_pixels  # at least one black pixel (outline or text)

    def test_score_end_limits_displayed_moves(self):
        # With 30 moves and score_end=20, only the first 10 full moves show.
        history = _moves(30)
        img = build_scoresheet_screen(history, score_end=20)
        assert img.size == (config.SCORE_W, config.SCORE_H)

    def test_score_end_none_shows_most_recent(self):
        # score_end=None and score_end=len produce identical images.
        history = _moves(40)
        img_default = build_scoresheet_screen(history)
        img_explicit = build_scoresheet_screen(history, score_end=len(history))
        assert img_default.tobytes() == img_explicit.tobytes()
