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
)


class ScreenMachine:
    """Controls the sequence of screens in the ZeroFish application.

    Typical usage in the main loop::

        machine = ScreenMachine()

        # after a button tap:
        new_id = machine.transition('new_game')
        if new_id is not None:
            _transition(epd, build_difficulty_screen(), partial_count)

        # for chess-logic-driven jumps:
        machine.force(ui.SCREEN_SF_MOVE)
    """

    # (from_screen_id, action) → to_screen_id
    TRANSITIONS: dict[tuple[int, str], int] = {
        (SCREEN_SPLASH,         'new_game'):    SCREEN_DIFFICULTY,
        (SCREEN_SPLASH,         'resume'):      SCREEN_RESUME,

        (SCREEN_DIFFICULTY,     'ok'):          SCREEN_COLOR,
        (SCREEN_DIFFICULTY,     'back'):        SCREEN_SPLASH,

        (SCREEN_COLOR,          'ok'):          SCREEN_PLAYER_MOVE,
        (SCREEN_COLOR,          'ok_black'):    SCREEN_THINKING,    # SF moves first
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

        (SCREEN_RESUME,         'back'):        SCREEN_SPLASH,
        (SCREEN_RESUME,         'ok'):          SCREEN_PLAYER_MOVE,
        (SCREEN_RESUME,         'next_page'):   SCREEN_RESUME,
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
