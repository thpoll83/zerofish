"""Tests for zerofish/screen_machine.py.

Covers the new transitions added in this PR:
- Splash → SCREEN_MAIN_MENU (action 'ok')
- Main menu transitions (new_game, cont, puzzle, back)
- Difficulty 'back' now returns to SCREEN_MAIN_MENU
- Resume 'back' now returns to SCREEN_MAIN_MENU
- Puzzle flow: SCREEN_PUZZLE, SCREEN_PUZZLE_MOVE, SCREEN_PUZZLE_DISAMBIG
"""
import ui
from screen_machine import ScreenMachine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _machine_at(screen_id: int) -> ScreenMachine:
    m = ScreenMachine()
    m.force(screen_id)
    return m


# ---------------------------------------------------------------------------
# Splash screen transitions
# ---------------------------------------------------------------------------

def test_splash_ok_goes_to_main_menu():
    m = ScreenMachine()
    assert m.is_at(ui.SCREEN_SPLASH)
    result = m.transition('ok')
    assert result == ui.SCREEN_MAIN_MENU
    assert m.is_at(ui.SCREEN_MAIN_MENU)


def test_splash_unknown_action_stays():
    m = ScreenMachine()
    result = m.transition('new_game')   # old action no longer valid from splash
    assert result is None
    assert m.is_at(ui.SCREEN_SPLASH)


# ---------------------------------------------------------------------------
# Main menu transitions
# ---------------------------------------------------------------------------

def test_main_menu_new_game():
    m = _machine_at(ui.SCREEN_MAIN_MENU)
    result = m.transition('new_game')
    assert result == ui.SCREEN_DIFFICULTY
    assert m.is_at(ui.SCREEN_DIFFICULTY)


def test_main_menu_cont():
    m = _machine_at(ui.SCREEN_MAIN_MENU)
    result = m.transition('cont')
    assert result == ui.SCREEN_RESUME
    assert m.is_at(ui.SCREEN_RESUME)


def test_main_menu_puzzle():
    m = _machine_at(ui.SCREEN_MAIN_MENU)
    result = m.transition('puzzle')
    assert result == ui.SCREEN_PUZZLE
    assert m.is_at(ui.SCREEN_PUZZLE)


def test_main_menu_back():
    m = _machine_at(ui.SCREEN_MAIN_MENU)
    result = m.transition('back')
    assert result == ui.SCREEN_SPLASH
    assert m.is_at(ui.SCREEN_SPLASH)


def test_main_menu_invalid_action():
    m = _machine_at(ui.SCREEN_MAIN_MENU)
    result = m.transition('resume')   # old action, no longer valid
    assert result is None
    assert m.is_at(ui.SCREEN_MAIN_MENU)


# ---------------------------------------------------------------------------
# Difficulty 'back' now goes to SCREEN_MAIN_MENU
# ---------------------------------------------------------------------------

def test_difficulty_back_goes_to_main_menu():
    m = _machine_at(ui.SCREEN_DIFFICULTY)
    result = m.transition('back')
    assert result == ui.SCREEN_MAIN_MENU
    assert m.is_at(ui.SCREEN_MAIN_MENU)


# ---------------------------------------------------------------------------
# Resume 'back' now goes to SCREEN_MAIN_MENU
# ---------------------------------------------------------------------------

def test_resume_back_goes_to_main_menu():
    m = _machine_at(ui.SCREEN_RESUME)
    result = m.transition('back')
    assert result == ui.SCREEN_MAIN_MENU
    assert m.is_at(ui.SCREEN_MAIN_MENU)


# ---------------------------------------------------------------------------
# Puzzle flow: SCREEN_PUZZLE
# ---------------------------------------------------------------------------

def test_puzzle_solve_goes_to_puzzle_move():
    m = _machine_at(ui.SCREEN_PUZZLE)
    result = m.transition('solve')
    assert result == ui.SCREEN_PUZZLE_MOVE
    assert m.is_at(ui.SCREEN_PUZZLE_MOVE)


def test_puzzle_skip_stays_on_puzzle():
    m = _machine_at(ui.SCREEN_PUZZLE)
    result = m.transition('skip')
    assert result == ui.SCREEN_PUZZLE
    assert m.is_at(ui.SCREEN_PUZZLE)


def test_puzzle_end_goes_to_splash():
    m = _machine_at(ui.SCREEN_PUZZLE)
    result = m.transition('end')
    assert result == ui.SCREEN_SPLASH
    assert m.is_at(ui.SCREEN_SPLASH)


def test_puzzle_invalid_action():
    m = _machine_at(ui.SCREEN_PUZZLE)
    result = m.transition('back')
    assert result is None
    assert m.is_at(ui.SCREEN_PUZZLE)


# ---------------------------------------------------------------------------
# Puzzle flow: SCREEN_PUZZLE_MOVE
# ---------------------------------------------------------------------------

def test_puzzle_move_ok_returns_to_puzzle():
    m = _machine_at(ui.SCREEN_PUZZLE_MOVE)
    result = m.transition('ok')
    assert result == ui.SCREEN_PUZZLE
    assert m.is_at(ui.SCREEN_PUZZLE)


def test_puzzle_move_back_returns_to_puzzle():
    m = _machine_at(ui.SCREEN_PUZZLE_MOVE)
    result = m.transition('back')
    assert result == ui.SCREEN_PUZZLE
    assert m.is_at(ui.SCREEN_PUZZLE)


def test_puzzle_move_disambig_goes_to_puzzle_disambig():
    m = _machine_at(ui.SCREEN_PUZZLE_MOVE)
    result = m.transition('disambig')
    assert result == ui.SCREEN_PUZZLE_DISAMBIG
    assert m.is_at(ui.SCREEN_PUZZLE_DISAMBIG)


# ---------------------------------------------------------------------------
# Puzzle flow: SCREEN_PUZZLE_DISAMBIG
# ---------------------------------------------------------------------------

def test_puzzle_disambig_ok_returns_to_puzzle():
    m = _machine_at(ui.SCREEN_PUZZLE_DISAMBIG)
    result = m.transition('ok')
    assert result == ui.SCREEN_PUZZLE
    assert m.is_at(ui.SCREEN_PUZZLE)


def test_puzzle_disambig_back_returns_to_puzzle_move():
    m = _machine_at(ui.SCREEN_PUZZLE_DISAMBIG)
    result = m.transition('back')
    assert result == ui.SCREEN_PUZZLE_MOVE
    assert m.is_at(ui.SCREEN_PUZZLE_MOVE)


# ---------------------------------------------------------------------------
# Full puzzle round-trip
# ---------------------------------------------------------------------------

def test_full_puzzle_flow_solve_correct():
    """Simulate: main_menu → puzzle → solve → ok (correct answer) → puzzle."""
    m = ScreenMachine()
    m.transition('ok')                 # splash → main_menu
    m.transition('puzzle')             # main_menu → puzzle
    m.transition('solve')              # puzzle → puzzle_move
    m.transition('ok')                 # puzzle_move → puzzle (answer submitted)
    assert m.is_at(ui.SCREEN_PUZZLE)


def test_full_puzzle_flow_with_disambig():
    """Simulate: puzzle → solve → disambig → ok → puzzle."""
    m = _machine_at(ui.SCREEN_PUZZLE)
    m.transition('solve')              # puzzle → puzzle_move
    m.transition('disambig')           # puzzle_move → puzzle_disambig
    m.transition('ok')                 # puzzle_disambig → puzzle
    assert m.is_at(ui.SCREEN_PUZZLE)


def test_full_puzzle_flow_skip_then_end():
    """Simulate: puzzle → skip → skip → end → splash."""
    m = _machine_at(ui.SCREEN_PUZZLE)
    m.transition('skip')
    m.transition('skip')
    m.transition('end')
    assert m.is_at(ui.SCREEN_SPLASH)


# ---------------------------------------------------------------------------
# force() bypasses transition table
# ---------------------------------------------------------------------------

def test_force_sets_any_screen():
    m = ScreenMachine()
    m.force(ui.SCREEN_PUZZLE_DISAMBIG)
    assert m.is_at(ui.SCREEN_PUZZLE_DISAMBIG)
    assert m.current == ui.SCREEN_PUZZLE_DISAMBIG


# ---------------------------------------------------------------------------
# New screen ID constants
# ---------------------------------------------------------------------------

def test_screen_id_values_are_unique():
    ids = [
        ui.SCREEN_SPLASH, ui.SCREEN_MAIN_MENU, ui.SCREEN_DIFFICULTY,
        ui.SCREEN_COLOR, ui.SCREEN_THINKING, ui.SCREEN_SF_MOVE,
        ui.SCREEN_PLAYER_MOVE, ui.SCREEN_GAME_OVER, ui.SCREEN_PROMOTION,
        ui.SCREEN_DISAMBIG, ui.SCREEN_INGAME_MENU, ui.SCREEN_SCORESHEET,
        ui.SCREEN_BOARD, ui.SCREEN_TIME, ui.SCREEN_RESIGN_CONFIRM,
        ui.SCREEN_RESUME, ui.SCREEN_PUZZLE, ui.SCREEN_PUZZLE_MOVE,
        ui.SCREEN_PUZZLE_DISAMBIG,
    ]
    assert len(ids) == len(set(ids)), "Screen ID collision detected"


def test_new_screen_ids_have_expected_values():
    assert ui.SCREEN_MAIN_MENU      == 15
    assert ui.SCREEN_PUZZLE         == 16
    assert ui.SCREEN_PUZZLE_MOVE    == 17
    assert ui.SCREEN_PUZZLE_DISAMBIG == 18
