"""
RPi integration tests – run on real Raspberry Pi hardware.

Skipped automatically on dev machines where RPi hardware is absent.

To run on the RPi after deployment:
    cd ~/zerofish && pytest tests/rpi/ -v

The tests exercise the complete game loop with:
  - Real e-ink display (actual refresh timing respected, not mocked)
  - Real GT1151 touch controller (events injected via patched GT_Scan)
  - Mock Stockfish (instant, deterministic first-legal-move replies)
  - Temp directory for game saves (nothing written to ~/.zerofish_saves)
"""
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
    """
    for mod in list(sys.modules.keys()):
        if mod in ('gpiozero', 'spidev', 'smbus') or mod.startswith('TP_lib'):
            del sys.modules[mod]

    _app_mods = (
        'main', 'game_state', 'ui', 'config', 'boot_splash',
        'screen_splash', 'screen_difficulty', 'screen_color',
        'screen_player_move', 'screen_ingame_menu', 'screen_resign_confirm',
        'screen_resume', 'screen_sf_move', 'screen_thinking',
        'screen_game_over', 'screen_board', 'screen_scoresheet',
        'screen_time', 'screen_promotion', 'screen_disambig',
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
    from screen_splash       import (_SPLASH_OK_Y0, _SPLASH_OK_Y1_FULL)
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
        # Full-height OK (no saved games yet)
        inject(ok_cx, (_SPLASH_OK_Y0 + _SPLASH_OK_Y1_FULL) // 2)

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

    from screen_splash  import (_SPLASH_OK_Y0, _SPLASH_OK_Y1,
                                 _SPLASH_SEC_Y0, _SPLASH_SEC_Y1)
    from screen_resume  import _slot_rect, _OK2_Y0, _OK2_Y1
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
        # ── Splash (with Cont button because a save exists) ───────────────────
        wait_startup()
        # Tap "Cont" (secondary / lower half of right panel)
        inject(ok_cx, (_SPLASH_SEC_Y0 + _SPLASH_SEC_Y1) // 2)

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
