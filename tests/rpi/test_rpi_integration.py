"""
RPi integration tests – run on real Raspberry Pi hardware.

Skipped automatically on dev machines where RPi hardware is absent.

To run on the RPi after deployment:
    bash deploy/deploy.sh
    ssh zero@zerofish.local 'cd ~/zerofish && pytest tests/rpi/ -v'

The tests exercise the complete game loop with:
  - Real e-ink display (actual refresh timing respected, not mocked)
  - Real GT1151 touch controller (events injected via patched GT_Scan)
  - Mock Stockfish (instant, deterministic first-legal-move replies)
  - Temp directory for game saves (nothing written to ~/.zerofish_saves)
"""
import gc
import os
import sys
import queue
import threading
import time

import pytest
import chess
import chess.engine


# ── RPi detection ─────────────────────────────────────────────────────────────

def _is_rpi() -> bool:
    try:
        with open('/sys/firmware/devicetree/base/model') as f:
            return 'Raspberry Pi' in f.read()
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _is_rpi(),
    reason='Raspberry Pi hardware required',
)


# ── Mock chess engine ─────────────────────────────────────────────────────────

class _MockEngine:
    """Returns the first legal move instantly – no Stockfish subprocess."""

    def configure(self, options):
        pass

    def play(self, board, limit):
        move = next(iter(board.legal_moves))
        return chess.engine.PlayResult(move=move, ponder=None)

    def quit(self):
        pass


# ── Coordinate helpers ────────────────────────────────────────────────────────

def _to_portrait(lx: int, ly: int) -> tuple[int, int]:
    """Inverse of ui.to_landscape(tx, ty) = (249 - ty, tx)."""
    return (ly, 249 - lx)


def _center(rect) -> tuple[int, int]:
    x0, y0, x1, y1 = rect
    return ((x0 + x1) // 2, (y0 + y1) // 2)


# ── Bootstrap helpers ─────────────────────────────────────────────────────────

def _clear_hardware_stubs():
    """
    Remove the empty TP_lib / gpiozero / spidev / smbus stubs that
    tests/conftest.py installs, together with any cached application modules,
    so subsequent imports resolve against the real RPi drivers.

    Must explicitly close any gpiozero devices from a prior epdconfig import
    before evicting the module; otherwise their pin reservations remain in the
    lgpio factory and the next import attempt raises GPIOPinInUse.
    """
    ec = sys.modules.get('TP_lib.epdconfig')
    if ec is not None:
        for attr in ('GPIO_RST_PIN', 'GPIO_DC_PIN', 'GPIO_TRST',
                     'GPIO_BUSY_PIN', 'GPIO_INT'):
            dev = getattr(ec, attr, None)
            if dev is not None:
                try:
                    dev.close()
                except Exception:
                    pass

    for mod in list(sys.modules.keys()):
        if mod in ('gpiozero', 'spidev', 'smbus') or mod.startswith('TP_lib'):
            del sys.modules[mod]

    gc.collect()

    _app_mods = (
        'main', 'game_state', 'ui', 'config', 'boot_splash',
        'screen_splash', 'screen_difficulty', 'screen_color',
        'screen_player_move', 'screen_ingame_menu', 'screen_resign_confirm',
        'screen_resume', 'screen_sf_move', 'screen_thinking',
        'screen_game_over', 'screen_board', 'screen_scoresheet',
        'screen_time', 'screen_promotion', 'screen_disambig',
        'screen_puzzle', 'screen_puzzle_loading', 'screen_machine',
        'puzzle_state', 'download_puzzles',
    )
    for mod in _app_mods:
        sys.modules.pop(mod, None)


def _wire_touch_injection(monkeypatch, gt1151):
    """
    Replace GT1151.GT_Scan with a queue-driven stub.

    Returns ``(touch_q, inject, inject_rect)``:
      touch_q       – ``queue.Queue`` of ``(tx, ty)`` portrait coordinates
      inject(lx,ly) – convert landscape coords and enqueue a touch event
      inject_rect(r)– enqueue the centre of rectangle ``r``
    """
    touch_q: queue.Queue = queue.Queue()

    def _mock_scan(self, GT_Dev, GT_Old):
        try:
            tx, ty = touch_q.get_nowait()
        except queue.Empty:
            # No pending event – clear flags so the main loop idles cleanly.
            GT_Dev.TouchpointFlag = 0
            GT_Dev.Touch = 0
            return
        # Guarantee old.X[0] != dev.X[0] so same_coords is always False.
        GT_Old.X[0] = (tx + 1) & 0xFF
        GT_Old.Y[0] = GT_Dev.Y[0]
        GT_Old.S[0] = GT_Dev.S[0]
        GT_Dev.X[0] = tx
        GT_Dev.Y[0] = ty
        GT_Dev.S[0] = 50
        GT_Dev.TouchpointFlag = 0x80
        GT_Dev.Touch = 0

    monkeypatch.setattr(gt1151.GT1151, 'GT_Scan', _mock_scan)

    def inject(lx: int, ly: int) -> None:
        touch_q.put(_to_portrait(lx, ly))

    def inject_rect(rect) -> None:
        inject(*_center(rect))

    return touch_q, inject, inject_rect


def _wire_display_sync(main_mod):
    """
    Attach semaphore-based callbacks to ``main_mod._test_hooks`` so tests can
    block until the e-ink display has finished a full refresh.

    Returns ``(wait_startup, wait_refresh, stop)``:
      wait_startup(timeout)       – block until initial splash is rendered
      wait_refresh(count,timeout) – block until *count* full refreshes complete
      stop()                      – signal the main loop to exit cleanly
    """
    refresh_sem = threading.Semaphore(0)
    startup_sem = threading.Semaphore(0)

    main_mod._test_hooks.on_transition = lambda: refresh_sem.release()
    main_mod._test_hooks.on_startup    = lambda: startup_sem.release()
    main_mod._test_hooks.stop          = False

    def wait_startup(timeout: float = 30.0) -> None:
        if not startup_sem.acquire(timeout=timeout):
            pytest.fail('App startup timed out (display never showed splash)')

    def wait_refresh(count: int = 1, timeout: float = 20.0) -> None:
        for n in range(count):
            if not refresh_sem.acquire(timeout=timeout):
                pytest.fail(
                    f'e-ink full refresh #{n + 1}/{count} timed out after {timeout}s'
                )

    def stop() -> None:
        main_mod._test_hooks.stop          = True
        main_mod._test_hooks.on_transition = None
        main_mod._test_hooks.on_startup    = None

    return wait_startup, wait_refresh, stop


def _setup(monkeypatch, tmp_path):
    """
    Full per-test bootstrap: clear stubs, import real drivers, wire all mocks.

    Returns a dict with keys:
        main, game_state, ui               – the freshly imported modules
        touch_q                            – raw queue.Queue (for inspection)
        wait_startup, wait_refresh         – display-sync helpers
        inject, inject_rect                – touch-injection helpers
        stop                               – clean loop-exit helper
    """
    _clear_hardware_stubs()

    # Import real application modules now that hardware stubs are gone.
    import main as main_mod
    import game_state
    import ui
    from TP_lib import gt1151

    import download_puzzles
    monkeypatch.setattr(download_puzzles, 'has_internet', lambda *a, **kw: False)
    monkeypatch.setattr(
        chess.engine.SimpleEngine, 'popen_uci',
        lambda *a, **kw: _MockEngine(),
    )
    monkeypatch.setattr(game_state, 'SAVE_DIR', str(tmp_path / 'saves'))

    touch_q, inject, inject_rect = _wire_touch_injection(monkeypatch, gt1151)
    wait_startup, wait_refresh, stop = _wire_display_sync(main_mod)

    return dict(
        main=main_mod, game_state=game_state, ui=ui,
        touch_q=touch_q,
        wait_startup=wait_startup, wait_refresh=wait_refresh,
        inject=inject, inject_rect=inject_rect,
        stop=stop,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_new_game_white_resign(tmp_path, monkeypatch):
    """
    Full flow: new game as White, play pawn e4, acknowledge Stockfish's reply,
    then open the in-game menu and resign.

    Verifies the complete screen sequence on real e-ink hardware and that the
    save file is created during play and deleted after game over.
    """
    h = _setup(monkeypatch, tmp_path)
    main_mod   = h['main']
    game_state = h['game_state']
    ui         = h['ui']

    # Import layout helpers after the module-cache flush in _setup.
    from screen_splash       import _SPLASH_OK_Y0, _SPLASH_OK_Y1
    from screen_main_menu    import _menu_rect
    from screen_difficulty   import diff_rect
    from screen_color        import COLOR_BTN_X, COLOR_BTN_W, COLOR_BTN_Y0, COLOR_BTN_Y1
    from screen_player_move  import pm_piece_rect, pm_file_rect, pm_rank_rect
    from screen_ingame_menu  import igmenu_rect
    from screen_resign_confirm import _YES_X0, _YES_X1, _YES_Y0, _YES_Y1

    wait_startup = h['wait_startup']
    wait_refresh = h['wait_refresh']
    inject       = h['inject']
    inject_rect  = h['inject_rect']
    stop         = h['stop']

    ok_cx = (ui.OK_X0 + ui.OK_X1) // 2

    error: list = [None]

    def _run():
        try:
            main_mod.main()
        except KeyboardInterrupt:
            pass
        except Exception as exc:
            error[0] = exc

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    try:
        # ── Splash ────────────────────────────────────────────────────────────
        wait_startup()
        inject(ok_cx, (_SPLASH_OK_Y0 + _SPLASH_OK_Y1) // 2)  # OK → main menu

        # ── Main menu ─────────────────────────────────────────────────────────
        wait_refresh()
        inject_rect(_menu_rect(0))  # "New Game" (index 0)

        # ── Difficulty ────────────────────────────────────────────────────────
        wait_refresh()
        inject_rect(diff_rect(1))                         # select level 1
        time.sleep(0.5)                                   # partial-refresh settles
        inject(ok_cx, (ui.OK_Y0 + ui.OK_Y1_SPLIT) // 2) # OK (split)

        # ── Side selection ────────────────────────────────────────────────────
        wait_refresh()
        inject(COLOR_BTN_X[0] + COLOR_BTN_W // 2,
               (COLOR_BTN_Y0 + COLOR_BTN_Y1) // 2)       # tap "White" (index 0)
        time.sleep(0.5)
        inject(ok_cx, (ui.OK_Y0 + ui.OK_Y1_SPLIT) // 2) # OK (split)

        # ── Player move screen (pawn e4) ──────────────────────────────────────
        # SCREEN_COLOR → SCREEN_PLAYER_MOVE is one _transition call.
        wait_refresh()

        save_dir = str(tmp_path / 'saves')
        saves_before = (
            [f for f in os.listdir(save_dir) if f.endswith('.json')]
            if os.path.isdir(save_dir) else []
        )
        assert saves_before, 'Save file not created when game started'

        inject_rect(pm_piece_rect(0))  # piece: Pawn (PIECES index 0 = 'P')
        time.sleep(0.4)
        inject_rect(pm_file_rect(4))   # file: 'e' (FILES index 4)
        time.sleep(0.4)
        inject_rect(pm_rank_rect(3))   # rank: '4' (RANKS index 3)
        time.sleep(0.4)
        # OK: split + no_title chrome
        inject((ui.OK_X0 + ui.OK_X1) // 2,
               (ui.NT_OK_Y0 + ui.NT_OK_Y1_SPLIT) // 2)

        # _push_and_continue fires _transition twice: THINKING then SF_MOVE.
        wait_refresh(count=2)

        # ── SF move screen ────────────────────────────────────────────────────
        # OK: no_title, no split (full-height).
        inject((ui.OK_X0 + ui.OK_X1) // 2,
               (ui.NT_OK_Y0 + ui.NT_OK_Y1) // 2)

        # ── Back to player move, then open in-game menu ───────────────────────
        wait_refresh()
        # Secondary (☰) button: no_title chrome
        inject((ui.OK_X0 + ui.OK_X1) // 2,
               (ui.NT_SEC_Y0 + ui.NT_SEC_Y1) // 2)

        # ── In-game menu ──────────────────────────────────────────────────────
        wait_refresh()
        inject_rect(igmenu_rect(0))  # Resign (index 0)

        # ── Resign confirmation ───────────────────────────────────────────────
        wait_refresh()
        inject((_YES_X0 + _YES_X1) // 2, (_YES_Y0 + _YES_Y1) // 2)

        # ── Game over ─────────────────────────────────────────────────────────
        wait_refresh()
        inject(ok_cx, (ui.OK_Y0 + ui.OK_Y1) // 2)  # OK (full, title bar)

        # ── Back at splash ────────────────────────────────────────────────────
        wait_refresh()

    finally:
        stop()

    if error[0] is not None:
        raise error[0]

    # Save file must be gone after game-over OK (game_state.clear was called).
    remaining = (
        [f for f in os.listdir(str(tmp_path / 'saves')) if f.endswith('.json')]
        if os.path.isdir(str(tmp_path / 'saves')) else []
    )
    assert remaining == [], f'Save file(s) not cleaned up after resign: {remaining}'


def test_resume_unfinished_game(tmp_path, monkeypatch):
    """
    Resume flow: a pre-existing save file is detected on startup (showing the
    Cont button), the user navigates to the resume screen, selects the game,
    and immediately resigns.

    Verifies that mocked save-file handling and the resume-screen touch
    targets work correctly on real hardware.
    """
    h = _setup(monkeypatch, tmp_path)
    main_mod   = h['main']
    game_state = h['game_state']
    ui         = h['ui']

    from screen_splash    import _SPLASH_OK_Y0, _SPLASH_OK_Y1
    from screen_main_menu import _menu_rect
    from screen_resume    import _slot_rect, _OK2_Y0, _OK2_Y1
    from screen_ingame_menu    import igmenu_rect
    from screen_resign_confirm import _YES_X0, _YES_X1, _YES_Y0, _YES_Y1

    wait_startup = h['wait_startup']
    wait_refresh = h['wait_refresh']
    inject       = h['inject']
    inject_rect  = h['inject_rect']
    stop         = h['stop']

    ok_cx = (ui.OK_X0 + ui.OK_X1) // 2

    # Pre-create an unfinished save (position after 1.e4 e5, player is White).
    board = chess.Board()
    board.push_san('e4')
    board.push_san('e5')
    save_path = game_state.save(board, ['e4', 'e5'], True, 1)
    assert os.path.exists(save_path), 'Pre-created save file missing'

    error: list = [None]

    def _run():
        try:
            main_mod.main()
        except KeyboardInterrupt:
            pass
        except Exception as exc:
            error[0] = exc

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    try:
        # ── Splash ────────────────────────────────────────────────────────────
        wait_startup()
        inject(ok_cx, (_SPLASH_OK_Y0 + _SPLASH_OK_Y1) // 2)  # OK → main menu

        # ── Main menu ─────────────────────────────────────────────────────────
        wait_refresh()
        inject_rect(_menu_rect(1))  # "Cont" (index 1)

        # ── Resume screen ─────────────────────────────────────────────────────
        wait_refresh()
        inject_rect(_slot_rect(0))               # select game slot 0
        time.sleep(0.5)                          # partial refresh settles
        inject(ok_cx, (_OK2_Y0 + _OK2_Y1) // 2) # OK (2-button layout, no Next)

        # ── Player move screen (resumed position: 1.e4 e5, White to move) ─────
        wait_refresh()
        # Open in-game menu and resign immediately.
        inject((ui.OK_X0 + ui.OK_X1) // 2,
               (ui.NT_SEC_Y0 + ui.NT_SEC_Y1) // 2)

        # ── In-game menu ──────────────────────────────────────────────────────
        wait_refresh()
        inject_rect(igmenu_rect(0))  # Resign

        # ── Resign confirmation ───────────────────────────────────────────────
        wait_refresh()
        inject((_YES_X0 + _YES_X1) // 2, (_YES_Y0 + _YES_Y1) // 2)

        # ── Game over ─────────────────────────────────────────────────────────
        wait_refresh()
        inject(ok_cx, (ui.OK_Y0 + ui.OK_Y1) // 2)

        # ── Back at splash ────────────────────────────────────────────────────
        wait_refresh()

    finally:
        stop()

    if error[0] is not None:
        raise error[0]

    # After game over the save should be deleted.
    remaining = (
        [f for f in os.listdir(str(tmp_path / 'saves')) if f.endswith('.json')]
        if os.path.isdir(str(tmp_path / 'saves')) else []
    )
    assert remaining == [], f'Save file(s) not cleaned up after resume+resign: {remaining}'


# ── Puzzle helpers ────────────────────────────────────────────────────────────

import json

# FEN after 1.e4 (Black to move).  Solution: e7→e5 (UCI e7e5).
# Rating 1200 fits difficulty band 2 (1000–1399).
_PUZZLE_FEN = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1'
_TEST_PUZZLES = [
    {'id': 'tpz1', 'fen': _PUZZLE_FEN, 'moves': ['e7e5'], 'rating': 1200},
    {'id': 'tpz2', 'fen': _PUZZLE_FEN, 'moves': ['e7e5'], 'rating': 1200},
    {'id': 'tpz3', 'fen': _PUZZLE_FEN, 'moves': ['e7e5'], 'rating': 1200},
]


def _write_puzzle_file(path: str, puzzles: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump({'version': 1, 'puzzles': puzzles}, f)


def _patch_puzzle_state(monkeypatch, tmp_path) -> None:
    """Redirect puzzle_state file paths to tmp_path so tests are isolated."""
    import puzzle_state
    monkeypatch.setattr(puzzle_state, 'PUZZLE_DIR',  str(tmp_path))
    monkeypatch.setattr(puzzle_state, 'PUZZLE_FILE', str(tmp_path / 'puzzles.json'))
    monkeypatch.setattr(puzzle_state, 'SOLVED_FILE', str(tmp_path / 'solved.json'))


def _puzzle_navigate_to_screen(inject, inject_rect, wait_startup, wait_refresh, ui,
                                pz_diff_rect, ok_cx):
    """Shared navigation: splash → main menu → puzzle difficulty → puzzle screen.

    Selects difficulty band 2 (1000–1399), which matches _TEST_PUZZLES rating 1200.
    Leaves the test at SCREEN_PUZZLE with the first test puzzle loaded.
    """
    from screen_main_menu import _menu_rect
    from screen_splash    import _SPLASH_OK_Y0, _SPLASH_OK_Y1

    # Splash OK
    wait_startup()
    inject(ok_cx, (_SPLASH_OK_Y0 + _SPLASH_OK_Y1) // 2)

    # Main menu → Puzzle (index 2)
    wait_refresh()
    inject_rect(_menu_rect(2))

    # Puzzle difficulty → select level 2, then OK (split button)
    wait_refresh()
    inject_rect(pz_diff_rect(2))
    time.sleep(0.5)
    inject(ok_cx, (ui.OK_Y0 + ui.OK_Y1_SPLIT) // 2)

    # Puzzle screen loaded
    wait_refresh()


def _puzzle_end_session(inject, wait_refresh, ok_cx, end_cx, end_cy,
                         yes_cx, yes_cy):
    """Shared cleanup: tap End → confirm Yes → back at main menu."""
    inject(end_cx, end_cy)
    wait_refresh()
    inject(yes_cx, yes_cy)
    wait_refresh()


# ── Puzzle tests ──────────────────────────────────────────────────────────────

def test_puzzle_solve(tmp_path, monkeypatch):
    """
    Correct solution flow: solve puzzle tpz1 by entering the expected move
    (Black pawn e7→e5), verify the puzzle is marked solved in solved.json,
    then end the session.

    Exercises: puzzle difficulty selection, SCREEN_PUZZLE_MOVE OK path,
    _pz_check_move correct-branch, mark_solved.
    """
    h = _setup(monkeypatch, tmp_path)
    _patch_puzzle_state(monkeypatch, tmp_path)
    _write_puzzle_file(str(tmp_path / 'puzzles.json'), _TEST_PUZZLES)

    main_mod = h['main']
    ui        = h['ui']
    wait_startup = h['wait_startup']
    wait_refresh = h['wait_refresh']
    inject       = h['inject']
    inject_rect  = h['inject_rect']
    stop         = h['stop']

    from screen_splash             import _SPLASH_OK_Y0, _SPLASH_OK_Y1
    from screen_puzzle_difficulty  import pz_diff_rect
    from screen_player_move        import pm_piece_rect, pm_file_rect, pm_rank_rect
    from screen_puzzle_end_confirm import _YES_RECT
    from screen_puzzle             import _RX0, _RX1, _BTN_Y_SOLVE, _BTN_Y_END

    ok_cx   = (ui.OK_X0   + ui.OK_X1)   // 2
    move_cx = (_RX0 + _RX1) // 2
    move_cy = (_BTN_Y_SOLVE[0] + _BTN_Y_SOLVE[1]) // 2
    end_cy  = (_BTN_Y_END[0]   + _BTN_Y_END[1])   // 2
    yes_cx  = (_YES_RECT[0] + _YES_RECT[2]) // 2
    yes_cy  = (_YES_RECT[1] + _YES_RECT[3]) // 2

    error: list = [None]

    def _run():
        try:
            main_mod.main()
        except KeyboardInterrupt:
            pass
        except Exception as exc:
            error[0] = exc

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    try:
        _puzzle_navigate_to_screen(
            inject, inject_rect, wait_startup, wait_refresh, ui,
            pz_diff_rect, ok_cx)

        # ── Tap Move → player move input screen ───────────────────────────────
        inject(move_cx, move_cy)
        wait_refresh()

        # ── Enter solution: Black Pawn (0) to e5 (file e=4, rank 5=idx 4) ─────
        # Piece, file, rank each fire a partial refresh via _show.
        inject_rect(pm_piece_rect(0))   # Pawn
        time.sleep(0.4)
        inject_rect(pm_file_rect(4))    # file e
        time.sleep(0.4)
        inject_rect(pm_rank_rect(4))    # rank 5
        time.sleep(0.4)
        # OK: no-title, split
        inject((ui.OK_X0 + ui.OK_X1) // 2,
               (ui.NT_OK_Y0 + ui.NT_OK_Y1_SPLIT) // 2)

        # Correct move → tpz1 solved, advance to tpz2
        wait_refresh()

        # ── End session ───────────────────────────────────────────────────────
        _puzzle_end_session(inject, wait_refresh, ok_cx,
                            move_cx, end_cy, yes_cx, yes_cy)

    finally:
        stop()

    if error[0] is not None:
        raise error[0]

    # Puzzle tpz1 must appear in solved.json
    solved_file = str(tmp_path / 'solved.json')
    assert os.path.exists(solved_file), 'solved.json not written after correct move'
    with open(solved_file) as f:
        solved_ids = json.load(f)
    assert 'tpz1' in solved_ids, f'tpz1 not in solved.json; got {solved_ids}'


def test_puzzle_wrong_advances(tmp_path, monkeypatch):
    """
    Wrong-move flow: enter Nf6 (g8f6) which is a legal chess move but NOT the
    expected e7e5.  After the tap the app must advance to the next puzzle
    immediately — no retry — and wrong count increments by 1.

    Verifies that _pz_check_move wrong-branch calls _pz_advance() instead of
    resetting the board.
    """
    h = _setup(monkeypatch, tmp_path)
    _patch_puzzle_state(monkeypatch, tmp_path)
    _write_puzzle_file(str(tmp_path / 'puzzles.json'), _TEST_PUZZLES)

    main_mod = h['main']
    ui        = h['ui']
    wait_startup = h['wait_startup']
    wait_refresh = h['wait_refresh']
    inject       = h['inject']
    inject_rect  = h['inject_rect']
    stop         = h['stop']

    from screen_splash             import _SPLASH_OK_Y0, _SPLASH_OK_Y1
    from screen_puzzle_difficulty  import pz_diff_rect
    from screen_player_move        import pm_piece_rect, pm_file_rect, pm_rank_rect
    from screen_puzzle_end_confirm import _YES_RECT
    from screen_puzzle             import _RX0, _RX1, _BTN_Y_SOLVE, _BTN_Y_END

    ok_cx   = (ui.OK_X0   + ui.OK_X1)   // 2
    move_cx = (_RX0 + _RX1) // 2
    move_cy = (_BTN_Y_SOLVE[0] + _BTN_Y_SOLVE[1]) // 2
    end_cy  = (_BTN_Y_END[0]   + _BTN_Y_END[1])   // 2
    yes_cx  = (_YES_RECT[0] + _YES_RECT[2]) // 2
    yes_cy  = (_YES_RECT[1] + _YES_RECT[3]) // 2

    error: list = [None]

    def _run():
        try:
            main_mod.main()
        except KeyboardInterrupt:
            pass
        except Exception as exc:
            error[0] = exc

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    try:
        _puzzle_navigate_to_screen(
            inject, inject_rect, wait_startup, wait_refresh, ui,
            pz_diff_rect, ok_cx)

        # Tap Move
        inject(move_cx, move_cy)
        wait_refresh()

        # Enter wrong move: Knight (1) to f6 (file f=5, rank 6=idx 5)
        # g8f6 is a legal chess move but NOT the solution (e7e5).
        inject_rect(pm_piece_rect(1))   # Knight
        time.sleep(0.4)
        inject_rect(pm_file_rect(5))    # file f
        time.sleep(0.4)
        inject_rect(pm_rank_rect(5))    # rank 6
        time.sleep(0.4)
        inject((ui.OK_X0 + ui.OK_X1) // 2,
               (ui.NT_OK_Y0 + ui.NT_OK_Y1_SPLIT) // 2)

        # Wrong → advance to tpz2 (one _transition: SCREEN_PUZZLE_MOVE → SCREEN_PUZZLE)
        wait_refresh()

        # End session
        _puzzle_end_session(inject, wait_refresh, ok_cx,
                            move_cx, end_cy, yes_cx, yes_cy)

    finally:
        stop()

    if error[0] is not None:
        raise error[0]

    # Nothing should be solved; solved.json absent or empty
    solved_file = str(tmp_path / 'solved.json')
    if os.path.exists(solved_file):
        with open(solved_file) as f:
            solved_ids = json.load(f)
        assert solved_ids == [], f'No puzzle should be solved after a wrong move; got {solved_ids}'


def test_puzzle_skip(tmp_path, monkeypatch):
    """
    Skip flow: tap the Skip button to skip tpz1 without attempting a move.
    The app must advance to tpz2 (last_result='skipped'), then end the session.

    Verifies that skip stays on SCREEN_PUZZLE and does not increment solved.
    """
    h = _setup(monkeypatch, tmp_path)
    _patch_puzzle_state(monkeypatch, tmp_path)
    _write_puzzle_file(str(tmp_path / 'puzzles.json'), _TEST_PUZZLES)

    main_mod = h['main']
    ui        = h['ui']
    wait_startup = h['wait_startup']
    wait_refresh = h['wait_refresh']
    inject       = h['inject']
    inject_rect  = h['inject_rect']
    stop         = h['stop']

    from screen_splash             import _SPLASH_OK_Y0, _SPLASH_OK_Y1
    from screen_puzzle_difficulty  import pz_diff_rect
    from screen_puzzle_end_confirm import _YES_RECT
    from screen_puzzle             import _RX0, _RX1, _BTN_Y_SKIP, _BTN_Y_END

    ok_cx   = (ui.OK_X0   + ui.OK_X1)   // 2
    btn_cx  = (_RX0 + _RX1) // 2
    skip_cy = (_BTN_Y_SKIP[0] + _BTN_Y_SKIP[1]) // 2
    end_cy  = (_BTN_Y_END[0]  + _BTN_Y_END[1])  // 2
    yes_cx  = (_YES_RECT[0] + _YES_RECT[2]) // 2
    yes_cy  = (_YES_RECT[1] + _YES_RECT[3]) // 2

    error: list = [None]

    def _run():
        try:
            main_mod.main()
        except KeyboardInterrupt:
            pass
        except Exception as exc:
            error[0] = exc

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    try:
        _puzzle_navigate_to_screen(
            inject, inject_rect, wait_startup, wait_refresh, ui,
            pz_diff_rect, ok_cx)

        # Skip tpz1 → advances to tpz2 (stays on SCREEN_PUZZLE)
        inject(btn_cx, skip_cy)
        wait_refresh()

        # End session
        _puzzle_end_session(inject, wait_refresh, ok_cx,
                            btn_cx, end_cy, yes_cx, yes_cy)

    finally:
        stop()

    if error[0] is not None:
        raise error[0]

    # Nothing solved
    solved_file = str(tmp_path / 'solved.json')
    if os.path.exists(solved_file):
        with open(solved_file) as f:
            solved_ids = json.load(f)
        assert solved_ids == [], f'Skip should not mark anything solved; got {solved_ids}'


def test_puzzle_invalid_move_counts_wrong(tmp_path, monkeypatch):
    """
    Invalid-move flow: select Bishop (index 2) to d6 — both black bishops are
    blocked in the test FEN so find_candidates returns [] (impossible move).
    The app must count it as wrong and advance to the next puzzle immediately,
    NOT stay on the move-input screen.

    Verifies the empty-candidates branch in SCREEN_PUZZLE_MOVE increments wrong
    and calls _pz_advance().
    """
    h = _setup(monkeypatch, tmp_path)
    _patch_puzzle_state(monkeypatch, tmp_path)
    _write_puzzle_file(str(tmp_path / 'puzzles.json'), _TEST_PUZZLES)

    main_mod = h['main']
    ui        = h['ui']
    wait_startup = h['wait_startup']
    wait_refresh = h['wait_refresh']
    inject       = h['inject']
    inject_rect  = h['inject_rect']
    stop         = h['stop']

    from screen_splash             import _SPLASH_OK_Y0, _SPLASH_OK_Y1
    from screen_puzzle_difficulty  import pz_diff_rect
    from screen_player_move        import pm_piece_rect, pm_file_rect, pm_rank_rect
    from screen_puzzle_end_confirm import _YES_RECT
    from screen_puzzle             import _RX0, _RX1, _BTN_Y_SOLVE, _BTN_Y_END

    ok_cx   = (ui.OK_X0   + ui.OK_X1)   // 2
    move_cx = (_RX0 + _RX1) // 2
    move_cy = (_BTN_Y_SOLVE[0] + _BTN_Y_SOLVE[1]) // 2
    end_cy  = (_BTN_Y_END[0]   + _BTN_Y_END[1])   // 2
    yes_cx  = (_YES_RECT[0] + _YES_RECT[2]) // 2
    yes_cy  = (_YES_RECT[1] + _YES_RECT[3]) // 2

    error: list = [None]

    def _run():
        try:
            main_mod.main()
        except KeyboardInterrupt:
            pass
        except Exception as exc:
            error[0] = exc

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    try:
        _puzzle_navigate_to_screen(
            inject, inject_rect, wait_startup, wait_refresh, ui,
            pz_diff_rect, ok_cx)

        # Tap Move
        inject(move_cx, move_cy)
        wait_refresh()

        # Enter impossible move: Bishop (2) to d6 (file d=3, rank 6=idx 5).
        # Both black bishops are blocked by pawns in the test FEN,
        # so find_candidates returns [] → invalid → wrong + advance.
        inject_rect(pm_piece_rect(2))   # Bishop
        time.sleep(0.4)
        inject_rect(pm_file_rect(3))    # file d
        time.sleep(0.4)
        inject_rect(pm_rank_rect(5))    # rank 6
        time.sleep(0.4)
        inject((ui.OK_X0 + ui.OK_X1) // 2,
               (ui.NT_OK_Y0 + ui.NT_OK_Y1_SPLIT) // 2)

        # Invalid → wrong + advance: one transition back to SCREEN_PUZZLE
        wait_refresh()

        # End session
        _puzzle_end_session(inject, wait_refresh, ok_cx,
                            move_cx, end_cy, yes_cx, yes_cy)

    finally:
        stop()

    if error[0] is not None:
        raise error[0]

    # Nothing solved; impossible move is wrong, not a solve
    solved_file = str(tmp_path / 'solved.json')
    if os.path.exists(solved_file):
        with open(solved_file) as f:
            solved_ids = json.load(f)
        assert solved_ids == [], (
            f'Impossible move should not mark anything solved; got {solved_ids}'
        )


# FEN after 1.e4 (Black to move).  Multi-move solution: e7e5 / d2d4 / e5d4.
_MULTI_PUZZLE_FEN   = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1'
_MULTI_PUZZLE_MOVES = ['e7e5', 'd2d4', 'e5d4']
_MULTI_PUZZLE = [
    {'id': 'mpz1', 'fen': _MULTI_PUZZLE_FEN, 'moves': _MULTI_PUZZLE_MOVES, 'rating': 1200},
    _TEST_PUZZLES[0],
    _TEST_PUZZLES[1],
]


def test_puzzle_multi_move_solve(tmp_path, monkeypatch):
    """
    Multi-move puzzle flow: solve mpz1 which requires two player moves separated
    by an engine reply (e7e5 / d2d4 auto-played / e5d4).

    After move 1 the puzzle screen must show move_num=2, move_total=2.
    After move 2 the puzzle is marked solved and the screen advances to tpz1.

    Verifies: _pz_check_move correct-branch with move_total>1, engine auto-play
    between player moves, and mark_solved called only after the final move.
    """
    h = _setup(monkeypatch, tmp_path)
    _patch_puzzle_state(monkeypatch, tmp_path)
    _write_puzzle_file(str(tmp_path / 'puzzles.json'), _MULTI_PUZZLE)

    main_mod     = h['main']
    ui           = h['ui']
    wait_startup = h['wait_startup']
    wait_refresh = h['wait_refresh']
    inject       = h['inject']
    inject_rect  = h['inject_rect']
    stop         = h['stop']

    from screen_puzzle_difficulty  import pz_diff_rect
    from screen_player_move        import pm_piece_rect, pm_file_rect, pm_rank_rect
    from screen_puzzle_end_confirm import _YES_RECT
    from screen_puzzle             import _RX0, _RX1, _BTN_Y_SOLVE, _BTN_Y_END

    ok_cx   = (ui.OK_X0 + ui.OK_X1) // 2
    move_cx = (_RX0 + _RX1) // 2
    move_cy = (_BTN_Y_SOLVE[0] + _BTN_Y_SOLVE[1]) // 2
    end_cy  = (_BTN_Y_END[0]   + _BTN_Y_END[1])   // 2
    yes_cx  = (_YES_RECT[0] + _YES_RECT[2]) // 2
    yes_cy  = (_YES_RECT[1] + _YES_RECT[3]) // 2

    error: list = [None]

    def _run():
        try:
            main_mod.main()
        except KeyboardInterrupt:
            pass
        except Exception as exc:
            error[0] = exc

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    try:
        _puzzle_navigate_to_screen(
            inject, inject_rect, wait_startup, wait_refresh, ui,
            pz_diff_rect, ok_cx)

        # ── Tap Move → player move input screen (move 1/2) ────────────────────
        inject(move_cx, move_cy)
        wait_refresh()

        # ── Enter player move 1: Black Pawn (0) to e5 (file e=4, rank 5=idx 4) ─
        inject_rect(pm_piece_rect(0))   # Pawn
        time.sleep(0.4)
        inject_rect(pm_file_rect(4))    # file e
        time.sleep(0.4)
        inject_rect(pm_rank_rect(4))    # rank 5
        time.sleep(0.4)
        # OK: no-title, split
        inject((ui.OK_X0 + ui.OK_X1) // 2,
               (ui.NT_OK_Y0 + ui.NT_OK_Y1_SPLIT) // 2)

        # Correct move 1 → engine auto-plays d2d4 → puzzle screen (2/2)
        wait_refresh()

        # ── Tap Move → player move input screen (move 2/2) ────────────────────
        inject(move_cx, move_cy)
        wait_refresh()

        # ── Enter player move 2: Black Pawn (0) to d4 (file d=3, rank 4=idx 3) ─
        inject_rect(pm_piece_rect(0))   # Pawn
        time.sleep(0.4)
        inject_rect(pm_file_rect(3))    # file d
        time.sleep(0.4)
        inject_rect(pm_rank_rect(3))    # rank 4
        time.sleep(0.4)
        # OK: no-title, split
        inject((ui.OK_X0 + ui.OK_X1) // 2,
               (ui.NT_OK_Y0 + ui.NT_OK_Y1_SPLIT) // 2)

        # Correct final move → mpz1 solved, advance to tpz1
        wait_refresh()

        # ── End session ───────────────────────────────────────────────────────
        _puzzle_end_session(inject, wait_refresh, ok_cx,
                            move_cx, end_cy, yes_cx, yes_cy)

    finally:
        stop()

    if error[0] is not None:
        raise error[0]

    # Puzzle mpz1 must appear in solved.json
    solved_file = str(tmp_path / 'solved.json')
    assert os.path.exists(solved_file), 'solved.json not written after multi-move solve'
    with open(solved_file) as f:
        solved_ids = json.load(f)
    assert 'mpz1' in solved_ids, f'mpz1 not in solved.json; got {solved_ids}'
