"""
Tests for every hit_* function in the UI layer.

Strategy: derive the expected hit zone from the same rect/layout helpers that
the production code uses, then verify that the centre of each zone registers
as a hit and a clearly-out-of-bounds point does not.
"""
import ui
from screen_splash       import (hit_splash_ok, hit_splash_resume,
                                  _SPLASH_OK_Y0, _SPLASH_OK_Y1_FULL,
                                  _SPLASH_OK_Y1, _SPLASH_SEC_Y0, _SPLASH_SEC_Y1)
from screen_difficulty   import hit_diff, diff_rect
from screen_color        import (hit_color, COLOR_BTN_X, COLOR_BTN_W,
                                  COLOR_BTN_Y0, COLOR_BTN_Y1)
from screen_player_move  import (hit_pm_piece, hit_pm_file, hit_pm_rank,
                                  pm_piece_rect, pm_file_rect, pm_rank_rect)
from screen_promotion    import hit_promo, promo_rect
from screen_disambig     import hit_disambig, disambig_rects
from screen_ingame_menu  import hit_igmenu, igmenu_rect
from screen_resign_confirm import (hit_resign_yes,
                                    _YES_X0, _YES_X1, _YES_Y0, _YES_Y1)
from screen_scoresheet   import hit_scoresheet_back, SCORE_BACK_Y0, SCORE_BACK_Y1
from screen_board        import hit_board_back
import config


def _cx(rect):
    return (rect[0] + rect[2]) // 2


def _cy(rect):
    return (rect[1] + rect[3]) // 2


# ── ui.hit_ok ────────────────────────────────────────────────────────────────

def test_hit_ok_centre():
    assert ui.hit_ok((ui.OK_X0 + ui.OK_X1) // 2, (ui.OK_Y0 + ui.OK_Y1) // 2)


def test_hit_ok_left_of_separator():
    assert not ui.hit_ok(ui.OK_X0 - 5, (ui.OK_Y0 + ui.OK_Y1) // 2)


def test_hit_ok_above():
    assert not ui.hit_ok((ui.OK_X0 + ui.OK_X1) // 2, ui.OK_Y0 - 1)


def test_hit_ok_split_upper_half():
    cx = (ui.OK_X0 + ui.OK_X1) // 2
    cy = (ui.OK_Y0 + ui.OK_Y1_SPLIT) // 2
    assert ui.hit_ok(cx, cy, split=True)


def test_hit_ok_split_rejects_lower_half():
    cx = (ui.OK_X0 + ui.OK_X1) // 2
    cy = (ui.SEC_Y0 + ui.SEC_Y1) // 2   # this is the secondary button region
    assert not ui.hit_ok(cx, cy, split=True)


def test_hit_ok_no_title_centre():
    cx = (ui.OK_X0 + ui.OK_X1) // 2
    cy = (ui.NT_OK_Y0 + ui.NT_OK_Y1) // 2
    assert ui.hit_ok(cx, cy, no_title=True)


# ── ui.hit_sec ───────────────────────────────────────────────────────────────

def test_hit_sec_centre():
    assert ui.hit_sec((ui.OK_X0 + ui.OK_X1) // 2, (ui.SEC_Y0 + ui.SEC_Y1) // 2)


def test_hit_sec_above_zone():
    cx = (ui.OK_X0 + ui.OK_X1) // 2
    assert not ui.hit_sec(cx, ui.SEC_Y0 - 5)


def test_hit_sec_no_title_centre():
    cx = (ui.OK_X0 + ui.OK_X1) // 2
    cy = (ui.NT_SEC_Y0 + ui.NT_SEC_Y1) // 2
    assert ui.hit_sec(cx, cy, no_title=True)


def test_hit_sec_no_title_rejects_ok_zone():
    cx = (ui.OK_X0 + ui.OK_X1) // 2
    cy = (ui.NT_OK_Y0 + ui.NT_OK_Y1_SPLIT) // 2
    assert not ui.hit_sec(cx, cy, no_title=True)


# ── Splash ────────────────────────────────────────────────────────────────────

def test_hit_splash_ok_no_resume():
    cx = (ui.OK_X0 + ui.OK_X1) // 2
    cy = (_SPLASH_OK_Y0 + _SPLASH_OK_Y1_FULL) // 2
    assert hit_splash_ok(cx, cy, has_resume=False)


def test_hit_splash_ok_with_resume_upper():
    cx = (ui.OK_X0 + ui.OK_X1) // 2
    cy = (_SPLASH_OK_Y0 + _SPLASH_OK_Y1) // 2
    assert hit_splash_ok(cx, cy, has_resume=True)


def test_hit_splash_ok_with_resume_rejects_lower():
    cx = (ui.OK_X0 + ui.OK_X1) // 2
    cy = (_SPLASH_SEC_Y0 + _SPLASH_SEC_Y1) // 2   # resume button region
    assert not hit_splash_ok(cx, cy, has_resume=True)


def test_hit_splash_resume():
    cx = (ui.OK_X0 + ui.OK_X1) // 2
    cy = (_SPLASH_SEC_Y0 + _SPLASH_SEC_Y1) // 2
    assert hit_splash_resume(cx, cy)


def test_hit_splash_resume_rejects_ok_region():
    cx = (ui.OK_X0 + ui.OK_X1) // 2
    cy = (_SPLASH_OK_Y0 + _SPLASH_OK_Y1) // 2
    assert not hit_splash_resume(cx, cy)


# ── Difficulty ────────────────────────────────────────────────────────────────

def test_hit_diff_level_1():
    r = diff_rect(1)
    assert hit_diff(1, _cx(r), _cy(r))
    assert not hit_diff(2, _cx(r), _cy(r))


def test_hit_diff_level_8():
    r = diff_rect(8)
    assert hit_diff(8, _cx(r), _cy(r))
    assert not hit_diff(7, _cx(r), _cy(r))


def test_hit_diff_level_15():
    r = diff_rect(15)
    assert hit_diff(15, _cx(r), _cy(r))


def test_hit_diff_origin_misses_all():
    for lvl in range(1, 16):
        assert not hit_diff(lvl, 0, 0)


# ── Side / colour selection ────────────────────────────────────────────────────

def test_hit_color_white():
    cx = COLOR_BTN_X[0] + COLOR_BTN_W // 2
    cy = (COLOR_BTN_Y0 + COLOR_BTN_Y1) // 2
    assert hit_color(0, cx, cy)
    assert not hit_color(1, cx, cy)


def test_hit_color_black():
    cx = COLOR_BTN_X[1] + COLOR_BTN_W // 2
    cy = (COLOR_BTN_Y0 + COLOR_BTN_Y1) // 2
    assert hit_color(1, cx, cy)


def test_hit_color_random():
    cx = COLOR_BTN_X[2] + COLOR_BTN_W // 2
    cy = (COLOR_BTN_Y0 + COLOR_BTN_Y1) // 2
    assert hit_color(2, cx, cy)


def test_hit_color_origin_misses():
    for i in range(3):
        assert not hit_color(i, 0, 0)


# ── Player move input ─────────────────────────────────────────────────────────

def test_hit_pm_piece_first_and_last():
    r0 = pm_piece_rect(0)
    r5 = pm_piece_rect(5)
    assert hit_pm_piece(0, _cx(r0), _cy(r0))
    assert hit_pm_piece(5, _cx(r5), _cy(r5))
    assert not hit_pm_piece(5, _cx(r0), _cy(r0))


def test_hit_pm_file_a_and_h():
    r0 = pm_file_rect(0)
    r7 = pm_file_rect(7)
    assert hit_pm_file(0, _cx(r0), _cy(r0))
    assert hit_pm_file(7, _cx(r7), _cy(r7))
    assert not hit_pm_file(7, _cx(r0), _cy(r0))


def test_hit_pm_rank_1_and_8():
    r0 = pm_rank_rect(0)
    r7 = pm_rank_rect(7)
    assert hit_pm_rank(0, _cx(r0), _cy(r0))
    assert hit_pm_rank(7, _cx(r7), _cy(r7))


def test_pm_rows_do_not_overlap():
    # Centre of piece row must not register as a file or rank hit
    r = pm_piece_rect(3)
    cx, cy = _cx(r), _cy(r)
    assert not hit_pm_file(3, cx, cy)
    assert not hit_pm_rank(3, cx, cy)

    # Centre of file row must not register as a piece or rank hit
    r = pm_file_rect(3)
    cx, cy = _cx(r), _cy(r)
    assert not hit_pm_piece(3, cx, cy)
    assert not hit_pm_rank(3, cx, cy)


# ── Pawn promotion ────────────────────────────────────────────────────────────

def test_hit_promo_each_piece():
    for i in range(4):
        r = promo_rect(i)
        assert hit_promo(i, _cx(r), _cy(r))
        # adjacent button should not fire
        other = (i + 1) % 4
        assert not hit_promo(other, _cx(r), _cy(r))


# ── Disambiguation ────────────────────────────────────────────────────────────

def test_hit_disambig_two_options():
    rects = disambig_rects(2)
    assert hit_disambig(0, rects, _cx(rects[0]), _cy(rects[0]))
    assert hit_disambig(1, rects, _cx(rects[1]), _cy(rects[1]))
    assert not hit_disambig(1, rects, _cx(rects[0]), _cy(rects[0]))


def test_hit_disambig_three_options():
    rects = disambig_rects(3)
    for i in range(3):
        assert hit_disambig(i, rects, _cx(rects[i]), _cy(rects[i]))


# ── In-game menu ──────────────────────────────────────────────────────────────

def test_hit_igmenu_each_button():
    for i in range(4):
        r = igmenu_rect(i)
        assert hit_igmenu(i, _cx(r), _cy(r))
        other = (i + 1) % 4
        assert not hit_igmenu(other, _cx(r), _cy(r))


# ── Resign confirm ────────────────────────────────────────────────────────────

def test_hit_resign_yes_centre():
    assert hit_resign_yes((_YES_X0 + _YES_X1) // 2, (_YES_Y0 + _YES_Y1) // 2)


def test_hit_resign_yes_outside():
    assert not hit_resign_yes(0, 0)


# ── Score sheet ───────────────────────────────────────────────────────────────

def test_hit_scoresheet_back_centre():
    cx = config.SCORE_W // 2
    cy = (SCORE_BACK_Y0 + SCORE_BACK_Y1) // 2
    assert hit_scoresheet_back(cx, cy)


def test_hit_scoresheet_back_misses_title():
    assert not hit_scoresheet_back(config.SCORE_W // 2, 0)


# ── Board view ────────────────────────────────────────────────────────────────

def test_hit_board_back_right_panel():
    assert hit_board_back(ui.VSEP_X + 10, 50)


def test_hit_board_back_misses_board_area():
    assert not hit_board_back(ui.VSEP_X - 10, 50)
