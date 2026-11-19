"""Puzzle session state and logic.

PuzzleSession encapsulates the mutable state that was previously the ``pz``
dict in main.py, together with the ``_pz_*`` helper functions.  The main loop
creates one instance per puzzle session and delegates all puzzle-specific
bookkeeping to it.
"""

import logging
import chess

import config
import puzzle_state
from screen_puzzle      import build_puzzle_screen
from screen_puzzle_hint import build_puzzle_hint_screen

log = logging.getLogger('zerofish')


class PuzzleSession:
    """Holds all mutable state for one puzzle-mode session."""

    def __init__(self) -> None:
        self.list:        list  = []
        self.idx:         int   = 0
        self.board:       chess.Board | None = None
        self.fen:         str   = ''
        self.moves:       list  = []   # full solution sequence [player, engine, …]
        self.move_idx:    int   = 0    # index of next expected player move
        self.move_num:    int   = 1    # 1-based player-move counter (displayed)
        self.move_total:  int   = 1    # total player moves in the puzzle
        self.sol:         str   = ''   # UCI of the currently expected player move
        self.id:          str   = ''   # Lichess puzzle ID
        self.diff_label:  str   = ''   # rating string shown in stats
        self.diff_sel:    int | None = None
        self.solved:      int   = 0
        self.wrong:       int   = 0
        self.skipped:     int   = 0
        self.last_result: str | None = None
        # Hint info (populated on wrong move, consumed by hint screen)
        self.hint_fen:      str   = ''
        self.hint_moves:    list  = []
        self.hint_move_idx: int   = 0
        # Puzzle to re-queue after the player dismisses the hint screen
        self._pending_retry: dict | None = None

    # ── Screen builders ───────────────────────────────────────────────────────

    def screen(self):
        """Return a PIL Image for the current puzzle state."""
        total      = puzzle_state.total_available()
        puzzle_num = (self.solved + self.wrong + self.skipped + 1
                      if self.board else 0)
        return build_puzzle_screen(
            self.board, puzzle_num, total,
            self.solved, self.wrong, self.diff_label,
            move_num=self.move_num, move_total=self.move_total,
            last_result=self.last_result,
        )

    def hint_screen(self):
        """Return a PIL Image for the hint (shown after a wrong move)."""
        return build_puzzle_hint_screen(
            self.board, self.hint_fen, self.hint_moves, self.hint_move_idx,
        )

    # ── State management ──────────────────────────────────────────────────────

    def load_current(self) -> None:
        """Populate fields from list[idx], skipping entries with invalid FENs."""
        while self.idx < len(self.list):
            p   = self.list[self.idx]
            fen = p.get('fen', '')
            mvs = puzzle_state.get_moves(p)
            try:
                self.board = chess.Board(fen)
            except Exception:
                log.warning('Skipping puzzle %s: invalid FEN', p.get('id', '?'))
                self.idx += 1
                continue
            self.fen        = fen
            self.moves      = mvs
            self.move_idx   = 0
            self.move_num   = 1
            self.move_total = max(1, (len(mvs) + 1) // 2)
            self.sol        = mvs[0] if mvs else ''
            self.id         = p.get('id', '')
            self.diff_label = str(p.get('rating', '?'))
            return
        # Exhausted the list without finding a valid puzzle
        self.board      = None
        self.fen        = ''
        self.moves      = []
        self.move_idx   = 0
        self.move_num   = 1
        self.move_total = 1
        self.sol        = ''
        self.id         = ''
        self.diff_label = ''

    def advance(self) -> None:
        """Move to the next unsolved puzzle, reloading from disk if exhausted.

        If the previous attempt was wrong the puzzle is re-inserted a few
        positions ahead so the player gets another chance in the same session.
        """
        retry = self._pending_retry
        self._pending_retry = None
        self.idx += 1
        if self.idx >= len(self.list):
            min_r = config.PUZZLE_DIFF_MIN.get(self.diff_sel, 0)
            max_r = config.PUZZLE_DIFF_MAX.get(self.diff_sel, 9999)
            self.list = puzzle_state.load_unsolved_by_rating(min_r, max_r)
            self.idx  = 0
        if retry is not None:
            insert_at = min(self.idx + 2, len(self.list))
            self.list.insert(insert_at, retry)
        self.load_current()

    def check_move(self, move_uci: str) -> str:
        """Validate *move_uci* against the currently expected solution move.

        Correct move: board and sequence pointers are advanced; engine response
        is applied automatically.  Returns ``'partial'`` (more moves remain)
        or ``'solved'``.

        Wrong move: hint state is saved, but advance() is NOT called — the
        caller transitions to the hint screen first, then calls advance() when
        the player dismisses it.  Returns ``'wrong'``.
        """
        if move_uci == self.sol:
            self.board.push(chess.Move.from_uci(move_uci))
            self.move_idx += 1
            if self.move_idx < len(self.moves):
                engine_uci = self.moves[self.move_idx]
                try:
                    engine_move = chess.Move.from_uci(engine_uci)
                    if not self.board.is_legal(engine_move):
                        raise ValueError(f'illegal engine move {engine_uci}')
                    self.board.push(engine_move)
                except Exception as exc:
                    log.warning('Puzzle %s: invalid engine move %s (idx=%d): %s',
                                self.id, engine_uci, self.move_idx, exc)
                    self.solved += 1
                    self.last_result = 'solved'
                    puzzle_state.mark_solved(self.id)
                    self.advance()
                    return 'solved'
                self.move_idx += 1
                self.move_num += 1
                self.sol = (self.moves[self.move_idx]
                            if self.move_idx < len(self.moves) else '')
                log.info('Puzzle %s move %d/%d correct',
                         self.id, self.move_num - 1, self.move_total)
                return 'partial'
            else:
                self.solved += 1
                self.last_result = 'solved'
                puzzle_state.mark_solved(self.id)
                log.info('Puzzle solved: %s', self.id)
                self.advance()
                return 'solved'
        else:
            self.wrong += 1
            self.last_result    = 'wrong'
            self.hint_fen       = self.fen
            self.hint_moves     = list(self.moves)
            self.hint_move_idx  = self.move_idx
            # Schedule a retry: advance() will re-insert this puzzle shortly.
            if self.idx < len(self.list):
                self._pending_retry = self.list[self.idx]
            log.info('Puzzle wrong: played %s expected %s', move_uci, self.sol)
            return 'wrong'
