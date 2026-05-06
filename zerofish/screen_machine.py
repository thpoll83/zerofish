"""State machine governing valid ZeroFish screen transitions.

Each (current_screen_id, action_string) pair maps to the next screen_id.
Use ``force()`` for programmatic jumps (e.g. when the next screen depends on
chess-engine output rather than a simple button press).
"""

from ui import (
    SCREEN_SPLASH, SCREEN_DIFFICULTY, SCREEN_COLOR,
    SCREEN_THINKING, SCREEN_SF_MOVE, SCREEN_PLAYER_MOVE,
    SCREEN_GAME_OVER, SCREEN_PROMOTION, SCREEN_DISAMBIG,
    SCREEN_INGAME_MENU, SCREEN_SCORESHEET, SCREEN_BOARD,
    SCREEN_TIME, SCREEN_RESIGN_CONFIRM, SCREEN_RESUME,
    SCREEN_MAIN_MENU, SCREEN_PUZZLE, SCREEN_PUZZLE_MOVE,
    SCREEN_PUZZLE_DISAMBIG, SCREEN_PUZZLE_LOADING, SCREEN_PUZZLE_PROMOTION,
    SCREEN_PUZZLE_END_CONFIRM, SCREEN_PUZZLE_DIFFICULTY,
)


class ScreenMachine:
    """Controls the sequence of screens in the ZeroFish application.

    Typical usage in the main loop::

        machine = ScreenMachine()

        # after a button tap:
        new_id = machine.transition('ok')
        if new_id is not None:
            _transition(epd, build_next_screen(), partial_count)

        # for chess-logic-driven jumps:
        machine.force(ui.SCREEN_SF_MOVE)
    """

    # (from_screen_id, action) → to_screen_id
    TRANSITIONS: dict[tuple[int, str], int] = {
        # Splash → main menu only
        (SCREEN_SPLASH,         'ok'):          SCREEN_MAIN_MENU,

        # Main menu
        (SCREEN_MAIN_MENU,      'new_game'):      SCREEN_DIFFICULTY,
        (SCREEN_MAIN_MENU,      'cont'):          SCREEN_RESUME,
        (SCREEN_MAIN_MENU,      'puzzle'):        SCREEN_PUZZLE_DIFFICULTY,
        (SCREEN_MAIN_MENU,      'back'):          SCREEN_SPLASH,

        # Puzzle difficulty selection (new screen inserted before puzzle)
        (SCREEN_PUZZLE_DIFFICULTY, 'ok'):         SCREEN_PUZZLE,
        (SCREEN_PUZZLE_DIFFICULTY, 'loading'):    SCREEN_PUZZLE_LOADING,
        (SCREEN_PUZZLE_DIFFICULTY, 'back'):       SCREEN_MAIN_MENU,

        # Difficulty / side selection
        (SCREEN_DIFFICULTY,     'ok'):          SCREEN_COLOR,
        (SCREEN_DIFFICULTY,     'back'):        SCREEN_MAIN_MENU,

        (SCREEN_COLOR,          'ok'):          SCREEN_PLAYER_MOVE,
        (SCREEN_COLOR,          'ok_black'):    SCREEN_THINKING,
        (SCREEN_COLOR,          'back'):        SCREEN_DIFFICULTY,

        (SCREEN_SF_MOVE,        'ok'):          SCREEN_PLAYER_MOVE,
        (SCREEN_SF_MOVE,        'game_over'):   SCREEN_GAME_OVER,

        (SCREEN_PLAYER_MOVE,    'menu'):        SCREEN_INGAME_MENU,
        (SCREEN_PLAYER_MOVE,    'promote'):     SCREEN_PROMOTION,
        (SCREEN_PLAYER_MOVE,    'disambig'):    SCREEN_DISAMBIG,
        (SCREEN_PLAYER_MOVE,    'thinking'):    SCREEN_THINKING,
        (SCREEN_PLAYER_MOVE,    'game_over'):   SCREEN_GAME_OVER,

        (SCREEN_PROMOTION,      'ok'):          SCREEN_THINKING,
        (SCREEN_PROMOTION,      'disambig'):    SCREEN_DISAMBIG,
        (SCREEN_PROMOTION,      'game_over'):   SCREEN_GAME_OVER,

        (SCREEN_DISAMBIG,       'ok'):          SCREEN_THINKING,
        (SCREEN_DISAMBIG,       'game_over'):   SCREEN_GAME_OVER,

        (SCREEN_THINKING,       'done'):        SCREEN_SF_MOVE,
        (SCREEN_THINKING,       'game_over'):   SCREEN_GAME_OVER,

        (SCREEN_INGAME_MENU,    'back'):        SCREEN_PLAYER_MOVE,
        (SCREEN_INGAME_MENU,    'resign'):      SCREEN_RESIGN_CONFIRM,
        (SCREEN_INGAME_MENU,    'board'):       SCREEN_BOARD,
        (SCREEN_INGAME_MENU,    'scoresheet'):  SCREEN_SCORESHEET,
        (SCREEN_INGAME_MENU,    'time'):        SCREEN_TIME,

        (SCREEN_RESIGN_CONFIRM, 'yes'):         SCREEN_GAME_OVER,
        (SCREEN_RESIGN_CONFIRM, 'no'):          SCREEN_INGAME_MENU,

        (SCREEN_BOARD,          'back'):        SCREEN_INGAME_MENU,
        (SCREEN_SCORESHEET,     'back'):        SCREEN_INGAME_MENU,
        (SCREEN_TIME,           'ok'):          SCREEN_INGAME_MENU,

        (SCREEN_GAME_OVER,      'ok'):          SCREEN_SPLASH,

        (SCREEN_RESUME,         'back'):        SCREEN_MAIN_MENU,
        (SCREEN_RESUME,         'ok'):          SCREEN_PLAYER_MOVE,
        (SCREEN_RESUME,         'next_page'):   SCREEN_RESUME,

        # Puzzle loading screen
        (SCREEN_PUZZLE_LOADING,  'back'):       SCREEN_MAIN_MENU,
        (SCREEN_PUZZLE_LOADING,  'play'):       SCREEN_PUZZLE,

        # Puzzle flow
        (SCREEN_PUZZLE,         'solve'):       SCREEN_PUZZLE_MOVE,
        (SCREEN_PUZZLE,         'skip'):        SCREEN_PUZZLE,
        (SCREEN_PUZZLE,         'end'):         SCREEN_PUZZLE_END_CONFIRM,
        (SCREEN_PUZZLE_END_CONFIRM, 'yes'):     SCREEN_MAIN_MENU,
        (SCREEN_PUZZLE_END_CONFIRM, 'no'):      SCREEN_PUZZLE,

        (SCREEN_PUZZLE_MOVE,    'ok'):          SCREEN_PUZZLE,
        (SCREEN_PUZZLE_MOVE,    'back'):        SCREEN_PUZZLE,
        (SCREEN_PUZZLE_MOVE,    'promote'):     SCREEN_PUZZLE_PROMOTION,
        (SCREEN_PUZZLE_MOVE,    'disambig'):    SCREEN_PUZZLE_DISAMBIG,

        (SCREEN_PUZZLE_PROMOTION, 'ok'):        SCREEN_PUZZLE,

        (SCREEN_PUZZLE_DISAMBIG, 'ok'):         SCREEN_PUZZLE,
        (SCREEN_PUZZLE_DISAMBIG, 'back'):       SCREEN_PUZZLE_MOVE,
    }

    def __init__(self) -> None:
        self._current: int = SCREEN_SPLASH

    @property
    def current(self) -> int:
        return self._current

    def is_at(self, screen_id: int) -> bool:
        return self._current == screen_id

    def transition(self, action: str) -> int | None:
        """Apply *action* from the current screen.

        Returns the new screen ID if the transition is defined, or ``None``
        if the action is not valid from the current screen (state unchanged).
        """
        next_id = self.TRANSITIONS.get((self._current, action))
        if next_id is not None:
            self._current = next_id
        return next_id

    def force(self, screen_id: int) -> None:
        """Unconditionally jump to *screen_id*.

        Use this for context-dependent transitions that cannot be expressed as
        a simple (state, action) pair, e.g. when the chess engine determines
        whether the game continues or ends.
        """
        self._current = screen_id
