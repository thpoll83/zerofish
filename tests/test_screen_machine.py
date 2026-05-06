"""Tests for ScreenMachine — the screen transition state machine.

Covers new and modified transitions introduced in this PR:
- Splash → ok → Main Menu (replaces old new_game / resume transitions)
- Main menu transitions (new_game, cont, puzzle, back)
- Difficulty back now goes to Main Menu (not Splash)
- Resume back now goes to Main Menu (not Splash)
- Puzzle flow: PUZZLE → solve/skip/end, PUZZLE_MOVE → ok/back/disambig,
  PUZZLE_DISAMBIG → ok/back
"""
import pytest
import ui
from screen_machine import ScreenMachine


def _machine_at(screen_id: int) -> ScreenMachine:
    """Return a ScreenMachine forced to a given screen."""
    m = ScreenMachine()
    m.force(screen_id)
    return m


# ── Initial state ─────────────────────────────────────────────────────────────

def test_initial_screen_is_splash():
    m = ScreenMachine()
    assert m.current == ui.SCREEN_SPLASH
    assert m.is_at(ui.SCREEN_SPLASH)


# ── Splash → Main Menu ────────────────────────────────────────────────────────

def test_splash_ok_goes_to_main_menu():
    m = ScreenMachine()
    result = m.transition('ok')
    assert result == ui.SCREEN_MAIN_MENU
    assert m.is_at(ui.SCREEN_MAIN_MENU)


def test_splash_invalid_action_returns_none():
    m = ScreenMachine()
    assert m.transition('new_game') is None   # no longer valid from splash
    assert m.is_at(ui.SCREEN_SPLASH)          # state unchanged


def test_splash_resume_no_longer_valid():
    m = ScreenMachine()
    assert m.transition('resume') is None
    assert m.is_at(ui.SCREEN_SPLASH)


# ── Main menu transitions ─────────────────────────────────────────────────────

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


def test_main_menu_invalid_action_returns_none():
    m = _machine_at(ui.SCREEN_MAIN_MENU)
    assert m.transition('bogus') is None
    assert m.is_at(ui.SCREEN_MAIN_MENU)


# ── Difficulty back → Main Menu (changed from Splash) ────────────────────────

def test_difficulty_back_goes_to_main_menu():
    m = _machine_at(ui.SCREEN_DIFFICULTY)
    result = m.transition('back')
    assert result == ui.SCREEN_MAIN_MENU
    assert m.is_at(ui.SCREEN_MAIN_MENU)


def test_difficulty_ok_still_goes_to_color():
    m = _machine_at(ui.SCREEN_DIFFICULTY)
    result = m.transition('ok')
    assert result == ui.SCREEN_COLOR


# ── Resume back → Main Menu (changed from Splash) ────────────────────────────

def test_resume_back_goes_to_main_menu():
    m = _machine_at(ui.SCREEN_RESUME)
    result = m.transition('back')
    assert result == ui.SCREEN_MAIN_MENU
    assert m.is_at(ui.SCREEN_MAIN_MENU)


def test_resume_ok_still_goes_to_player_move():
    m = _machine_at(ui.SCREEN_RESUME)
    result = m.transition('ok')
    assert result == ui.SCREEN_PLAYER_MOVE


def test_resume_next_page_stays_on_resume():
    m = _machine_at(ui.SCREEN_RESUME)
    result = m.transition('next_page')
    assert result == ui.SCREEN_RESUME


# ── Puzzle flow ───────────────────────────────────────────────────────────────

def test_puzzle_solve():
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


def test_puzzle_invalid_action_returns_none():
    m = _machine_at(ui.SCREEN_PUZZLE)
    assert m.transition('back') is None
    assert m.is_at(ui.SCREEN_PUZZLE)


# ── Puzzle move ───────────────────────────────────────────────────────────────

def test_puzzle_move_ok_goes_to_puzzle():
    m = _machine_at(ui.SCREEN_PUZZLE_MOVE)
    result = m.transition('ok')
    assert result == ui.SCREEN_PUZZLE
    assert m.is_at(ui.SCREEN_PUZZLE)


def test_puzzle_move_back_goes_to_puzzle():
    m = _machine_at(ui.SCREEN_PUZZLE_MOVE)
    result = m.transition('back')
    assert result == ui.SCREEN_PUZZLE
    assert m.is_at(ui.SCREEN_PUZZLE)


def test_puzzle_move_disambig():
    m = _machine_at(ui.SCREEN_PUZZLE_MOVE)
    result = m.transition('disambig')
    assert result == ui.SCREEN_PUZZLE_DISAMBIG
    assert m.is_at(ui.SCREEN_PUZZLE_DISAMBIG)


def test_puzzle_move_invalid_action():
    m = _machine_at(ui.SCREEN_PUZZLE_MOVE)
    assert m.transition('end') is None
    assert m.is_at(ui.SCREEN_PUZZLE_MOVE)


# ── Puzzle disambiguation ─────────────────────────────────────────────────────

def test_puzzle_disambig_ok_goes_to_puzzle():
    m = _machine_at(ui.SCREEN_PUZZLE_DISAMBIG)
    result = m.transition('ok')
    assert result == ui.SCREEN_PUZZLE
    assert m.is_at(ui.SCREEN_PUZZLE)


def test_puzzle_disambig_back_goes_to_puzzle_move():
    m = _machine_at(ui.SCREEN_PUZZLE_DISAMBIG)
    result = m.transition('back')
    assert result == ui.SCREEN_PUZZLE_MOVE
    assert m.is_at(ui.SCREEN_PUZZLE_MOVE)


def test_puzzle_disambig_invalid_action():
    m = _machine_at(ui.SCREEN_PUZZLE_DISAMBIG)
    assert m.transition('skip') is None
    assert m.is_at(ui.SCREEN_PUZZLE_DISAMBIG)


# ── Game over still goes to Splash (not main menu) ────────────────────────────

def test_game_over_ok_goes_to_splash():
    m = _machine_at(ui.SCREEN_GAME_OVER)
    result = m.transition('ok')
    assert result == ui.SCREEN_SPLASH
    assert m.is_at(ui.SCREEN_SPLASH)


# ── force() bypasses transition table ────────────────────────────────────────

def test_force_jumps_to_any_screen():
    m = ScreenMachine()
    m.force(ui.SCREEN_PUZZLE_DISAMBIG)
    assert m.is_at(ui.SCREEN_PUZZLE_DISAMBIG)


# ── Full puzzle round-trip path ───────────────────────────────────────────────

def test_full_puzzle_happy_path():
    """Splash → Main Menu → Puzzle → Solve → Puzzle (correct answer)."""
    m = ScreenMachine()
    assert m.transition('ok') == ui.SCREEN_MAIN_MENU
    assert m.transition('puzzle') == ui.SCREEN_PUZZLE
    assert m.transition('solve') == ui.SCREEN_PUZZLE_MOVE
    assert m.transition('ok') == ui.SCREEN_PUZZLE


def test_full_puzzle_skip_path():
    """Splash → Main Menu → Puzzle → Skip → Puzzle."""
    m = ScreenMachine()
    m.transition('ok')
    m.transition('puzzle')
    assert m.transition('skip') == ui.SCREEN_PUZZLE


def test_full_puzzle_disambig_path():
    """Puzzle → Solve → Disambig → OK → Puzzle."""
    m = _machine_at(ui.SCREEN_PUZZLE)
    m.transition('solve')
    assert m.transition('disambig') == ui.SCREEN_PUZZLE_DISAMBIG
    assert m.transition('ok') == ui.SCREEN_PUZZLE


def test_full_new_game_path():
    """Splash → Main Menu → New Game → Color → Player Move."""
    m = ScreenMachine()
    m.transition('ok')
    assert m.transition('new_game') == ui.SCREEN_DIFFICULTY
    assert m.transition('ok') == ui.SCREEN_COLOR
    assert m.transition('ok') == ui.SCREEN_PLAYER_MOVE
