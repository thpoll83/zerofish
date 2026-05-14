#!/usr/bin/env python3
"""ZeroFish — chess computer for the WaveShare 2.13" Touch e-Paper HAT V4.

Landscape orientation: hold the device with the short edge at top/bottom
(rotated 90° clockwise from portrait, USB port on the left side).
Score sheet uses portrait orientation (USB at bottom).
"""

import sys
import time
import random
import logging
import threading

# TP_lib imports are deferred to main() — epdconfig.py claims GPIO at module
# level, which crashes on non-Pi hardware and conflicts in --debug-remote mode.
import chess
import chess.engine

import config
import game_state
import puzzle_state
import ui
from game_utils       import (skill_level, think_limit, move_label,
                               push_and_continue, set_cpu_governor, engine_move)
from puzzle_session   import PuzzleSession
from screen_machine   import ScreenMachine
from screen_splash       import (get_sf_info, build_splash_screen,
                                  hit_splash_ok)
from screen_main_menu    import build_main_menu_screen, hit_main_menu
from screen_resume       import (build_resume_screen, hit_game_btn as hit_resume_game,
                                  hit_next as hit_resume_next, hit_ok as hit_resume_ok,
                                  hit_back as hit_resume_back)
from screen_difficulty   import build_difficulty_screen, hit_diff
from screen_color        import build_color_screen, hit_color, COLORS
from screen_thinking     import build_thinking_screen
from screen_sf_move      import build_sf_move_screen
from screen_game_over    import (build_game_over_screen, game_over_message,
                                  hit_game_over, game_over_outcome)
from screen_analyze      import build_analyze_screen, hit_analyze
from screen_player_move  import (build_player_move_screen, hit_pm_piece, hit_pm_file,
                                  hit_pm_rank, find_candidates, needs_promotion,
                                  PIECES, PIECE_SYMBOLS, FILES, RANKS)
from screen_promotion    import build_promotion_screen, hit_promo, PROMO_PIECE_TYPES
from screen_disambig     import build_disambig_screen, hit_disambig, disambig_rects
from screen_ingame_menu    import build_ingame_menu_screen, hit_igmenu
from screen_resign_confirm import build_resign_confirm_screen, hit_resign_yes
from screen_time           import build_time_screen
from screen_board        import build_board_screen, hit_board_back
from screen_scoresheet   import (build_scoresheet_screen, hit_scoresheet_back,
                                  hit_scoresheet_more, next_score_end, SCORE_ROWS)
from screen_puzzle             import build_puzzle_screen, hit_puzzle
from screen_puzzle_loading     import build_puzzle_loading_screen, hit_puzzle_loading
from screen_puzzle_end_confirm import build_puzzle_end_confirm_screen, hit_puzzle_end_confirm
from screen_puzzle_difficulty  import (build_puzzle_difficulty_screen,
                                        hit_puzzle_difficulty_screen)
from screen_puzzle_hint        import build_puzzle_hint_screen, hit_puzzle_hint
from screen_stats      import build_stats_screen, hit_stats
from screen_game_stats import build_game_stats_screen, hit_game_stats
from screen_settings   import build_settings_screen, hit_settings
from screen_wifi      import (build_wifi_screen, hit_wifi,
                               build_wifi_result_screen, hit_wifi_result,
                               scan_networks, connect_open, connect_wpa,
                               forget_network, _KBD_NUM_PAGES)
import download_puzzles

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
log = logging.getLogger('zerofish')

# Background puzzle download state (written by download thread, read by main loop)
_dl: dict = {
    'running':    False,
    'done':       False,
    'stop_event': threading.Event(),
    'rows':       0,
    'found':      0,
}


def _start_puzzle_download() -> None:
    """Start a daemon thread that downloads puzzles if internet is available."""
    def _worker() -> None:
        # Retry connectivity: DHCP/DNS may lag a few seconds on first boot.
        connected = False
        for delay in (0, 5, 20):
            if delay:
                time.sleep(delay)
            if download_puzzles.has_internet():
                connected = True
                break
        if not connected:
            log.info('No internet after retries — skipping puzzle auto-download')
            _dl['done'] = True
            return
        _dl['running'] = True

        def _progress(rows: int, found: int) -> None:
            _dl['rows'] = rows
            _dl['found'] = found

        try:
            download_puzzles.run_download(
                stop_event=_dl['stop_event'],
                progress_cb=_progress,
            )
        except Exception:
            log.exception('Puzzle download error')
        finally:
            _dl['running'] = False
            _dl['done'] = True
            log.info('Puzzle download finished')

    threading.Thread(target=_worker, daemon=True, name='puzzle-dl').start()


class _TestHooks:
    """Test-seam wired up by integration tests; ignored in production runs."""

    def __init__(self):
        self.on_transition = None  # callable() – after every full-refresh transition
        self.on_startup    = None  # callable() – once after initial splash is ready
        self.stop          = False # True → exit the main loop on the next iteration


_test_hooks = _TestHooks()


_last_display_buf = None


def _transition(epd, img, partial_count):
    global _last_display_buf
    buf = epd.getbuffer(img)
    _last_display_buf = buf
    epd.init(epd.FULL_UPDATE)
    epd.displayPartBaseImage(buf)
    epd.init(epd.PART_UPDATE)
    partial_count[0] = 0
    if _test_hooks.on_transition is not None:
        _test_hooks.on_transition()


def _show(epd, img, partial_count):
    global _last_display_buf
    buf = epd.getbuffer(img)
    _last_display_buf = buf
    partial_count[0] += 1
    if partial_count[0] % 5 == 0:
        log.info('Full refresh to clear ghosting')
        epd.init(epd.FULL_UPDATE)
        epd.displayPartBaseImage(buf)
        epd.init(epd.PART_UPDATE)
    else:
        epd.displayPartial_Wait(buf)


def _sleep_until_touch(epd, dev, partial_count):
    log.info('Idle timeout — display sleep')
    epd.sleep()
    while dev.Touch == 0:
        time.sleep(0.5)
    log.info('Touch detected — waking display')
    epd.init(epd.FULL_UPDATE)
    if _last_display_buf is not None:
        epd.displayPartBaseImage(_last_display_buf)
    epd.init(epd.PART_UPDATE)
    partial_count[0] = 0


def _scan_move_buttons(lx, ly, sel_piece, sel_file, sel_rank):
    """Check piece/file/rank button grid for a touch.

    Returns (changed, new_sel_piece, new_sel_file, new_sel_rank).
    """
    for i in range(len(PIECES)):
        if hit_pm_piece(i, lx, ly) and i != sel_piece:
            return True, i, sel_file, sel_rank
    for i in range(len(FILES)):
        if hit_pm_file(i, lx, ly) and i != sel_file:
            return True, sel_piece, i, sel_rank
    for i in range(len(RANKS)):
        if hit_pm_rank(i, lx, ly) and i != sel_rank:
            return True, sel_piece, sel_file, i
    return False, sel_piece, sel_file, sel_rank


def main():
    if '--debug-remote' in sys.argv:
        import debug_remote as _dr
        _dr.start()
        epd = _dr.DebugEPD()
        gt  = _dr.DebugGT1151()
        dev = _dr.GTDevelopment()
        old = _dr.GTDevelopment()
    else:
        from TP_lib import epd2in13_V4, gt1151
        epd = epd2in13_V4.EPD()
        gt  = gt1151.GT1151()
        dev = gt1151.GT_Development()
        old = gt1151.GT_Development()

    log.info('ZeroFish v%s starting', config.VERSION)

    # Start puzzle download early so puzzles are ready when the user gets there.
    _start_puzzle_download()

    # Probe Stockfish in the background so the splash appears immediately.
    sf_info    = None
    _sf_result = [None]
    def _probe_sf():
        _sf_result[0] = get_sf_info()
        log.info('Engine: %s  %s', *_sf_result[0])
    sf_thread = threading.Thread(target=_probe_sf, daemon=True)
    sf_thread.start()

    saves_list = game_state.list_saves()
    log.info('Unfinished saves: %d', len(saves_list))

    epd.init(epd.FULL_UPDATE)
    gt.GT_Init()
    gt.GT_DumpConfig()
    epd.Clear(0xFF)
    global _last_display_buf
    _last_display_buf = epd.getbuffer(build_splash_screen(None))
    epd.displayPartBaseImage(_last_display_buf)
    epd.init(epd.PART_UPDATE)

    machine         = ScreenMachine()
    diff_sel        = None
    color_sel       = None
    partial_count   = [0]
    last_touch_time = time.time()

    # ── Game state ────────────────────────────────────────────────────────────
    board               = None
    engine              = None
    player_is_white     = True
    sel_piece           = None
    sel_file            = None
    sel_rank            = None
    inv_count           = 0
    cur_move_label      = ''
    move_history        = []
    prom_piece          = prom_file = prom_rank = None
    sel_promo           = None
    disambig_candidates = []
    disambig_labels     = []
    disambig_rects_cur  = []
    sel_disambig        = None
    save_path           = None
    resume_page         = 0
    sel_resume          = None
    game_start          = 0.0
    sf_time_acc         = [0.0]
    score_end           = None

    # ── Game-over / analyze state ─────────────────────────────────────────────
    game_over_outcome_code: str              = ''
    analyze_history:        list             = []
    analyze_player_white:   bool             = True
    analyze_idx:            int              = 0
    analyze_board:          chess.Board | None = None
    analyze_last_move:      chess.Move | None  = None
    analyze_played_san:     str              = ''
    analyze_best_san:       str              = ''

    # ── WiFi state ────────────────────────────────────────────────────────────
    wifi_nets:        list       = []
    wifi_sel:         int | None = None
    wifi_passwd:      str        = ''
    wifi_kbd_page:    int        = 0
    wifi_scroll_off:  int        = 0
    wifi_status:      str        = ''
    wifi_result_ssid: str        = ''
    wifi_result_msg:  str        = ''

    # ── Puzzle state ──────────────────────────────────────────────────────────
    pz = PuzzleSession()

    running = True
    def irq_poll():
        while running:
            if gt.digital_read(gt.INT) == 0:
                dev.Touch = 1
            time.sleep(0.005)
    threading.Thread(target=irq_poll, daemon=True).start()

    log.info('Ready — waiting for SF probe')

    try:
        while True:
            if _test_hooks.stop:
                break

            # Auto-advance loading screen once download finishes.
            if machine.is_at(ui.SCREEN_PUZZLE_LOADING) and _dl['done']:
                min_r = config.PUZZLE_DIFF_MIN.get(pz.diff_sel, 0)
                max_r = config.PUZZLE_DIFF_MAX.get(pz.diff_sel, 9999)
                pz.list = puzzle_state.load_unsolved_by_rating(min_r, max_r)
                pz.idx  = 0
                pz.load_current()
                machine.transition('play')
                _transition(epd, pz.screen(), partial_count)

            # Once the SF probe finishes, update the splash and show the button.
            if machine.is_at(ui.SCREEN_SPLASH) and sf_info is None and not sf_thread.is_alive():
                sf_info = _sf_result[0] or ('Stockfish', '')
                _show(epd, build_splash_screen(sf_info), partial_count)
                if _test_hooks.on_startup is not None:
                    _test_hooks.on_startup()

            had_irq = (dev.Touch == 1)
            gt.GT_Scan(dev, old)

            same_coords = (old.X[0] == dev.X[0]
                           and old.Y[0] == dev.Y[0]
                           and old.S[0] == dev.S[0])
            if same_coords:
                if had_irq and not dev.TouchpointFlag:
                    old.X[0] = old.Y[0] = old.S[0] = 0
                    dev.X[0] = dev.Y[0] = dev.S[0] = 0
                time.sleep(0.01)
                continue
            if not dev.TouchpointFlag:
                time.sleep(0.01)
                continue

            dev.TouchpointFlag = 0
            last_touch_time = time.time()

            lx, ly = ui.to_landscape(dev.X[0], dev.Y[0])
            tx, ty = dev.X[0], dev.Y[0]

            # ── Splash ───────────────────────────────────────────────────────
            if machine.is_at(ui.SCREEN_SPLASH):
                if sf_info is None:
                    pass  # buttons not yet visible — ignore all touches
                elif hit_splash_ok(lx, ly):
                    machine.transition('ok')
                    saves_list = game_state.list_saves()
                    _transition(epd, build_main_menu_screen(has_saves=bool(saves_list)),
                                partial_count)

            # ── Main menu ─────────────────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_MAIN_MENU):
                action = hit_main_menu(lx, ly)
                if action == 'new_game':
                    machine.transition('new_game')
                    diff_sel  = None
                    save_path = None
                    _transition(epd, build_difficulty_screen(), partial_count)

                elif action == 'cont':
                    saves_list = game_state.list_saves()
                    if saves_list:
                        resume_page = 0
                        sel_resume  = None
                        machine.transition('cont')
                        _transition(epd, build_resume_screen(saves_list, 0, None),
                                    partial_count)

                elif action == 'puzzle':
                    machine.transition('puzzle')
                    pz = PuzzleSession()
                    _transition(epd, build_puzzle_difficulty_screen(), partial_count)

                elif action == 'stats':
                    machine.transition('stats')
                    _transition(epd, build_stats_screen(), partial_count)

                elif action == 'settings':
                    machine.transition('settings')
                    _transition(epd, build_settings_screen(), partial_count)

                elif action == 'back':
                    machine.transition('back')
                    _transition(epd, build_splash_screen(sf_info), partial_count)

            # ── Puzzle difficulty selection ───────────────────────────────────
            elif machine.is_at(ui.SCREEN_PUZZLE_DIFFICULTY):
                action = hit_puzzle_difficulty_screen(lx, ly, selected=pz.diff_sel)
                if action == 'back':
                    machine.transition('back')
                    saves_list = game_state.list_saves()
                    _transition(epd,
                                build_main_menu_screen(has_saves=bool(saves_list)),
                                partial_count)
                elif action == 'ok' and pz.diff_sel is not None:
                    min_r = config.PUZZLE_DIFF_MIN[pz.diff_sel]
                    max_r = config.PUZZLE_DIFF_MAX[pz.diff_sel]
                    pz.list = puzzle_state.load_unsolved_by_rating(min_r, max_r)
                    pz.idx  = 0
                    pz.load_current()
                    if not _dl['done'] and not pz.list:
                        machine.transition('loading')
                        _transition(epd,
                                    build_puzzle_loading_screen(
                                        has_existing=False,
                                        rows_scanned=_dl['rows'],
                                        found=_dl['found']),
                                    partial_count)
                    else:
                        machine.transition('ok')
                        _transition(epd, pz.screen(), partial_count)
                elif action is not None and action.startswith('pz_diff:'):
                    lvl = int(action.split(':')[1])
                    if lvl != pz.diff_sel:
                        pz.diff_sel = lvl
                        _show(epd, build_puzzle_difficulty_screen(pz.diff_sel),
                              partial_count)

            # ── Puzzle loading (download in progress, no puzzles yet) ─────────
            elif machine.is_at(ui.SCREEN_PUZZLE_LOADING):
                _has_existing = bool(pz.list)
                action = hit_puzzle_loading(lx, ly, has_existing=_has_existing)
                if action == 'back':
                    machine.transition('back')
                    saves_list = game_state.list_saves()
                    _transition(epd,
                                build_main_menu_screen(has_saves=bool(saves_list)),
                                partial_count)
                elif action == 'play' and _has_existing:
                    machine.transition('play')
                    _transition(epd, pz.screen(), partial_count)
                else:
                    # Refresh progress display periodically (touch event cadence)
                    _show(epd,
                          build_puzzle_loading_screen(
                              has_existing=_has_existing,
                              rows_scanned=_dl['rows'],
                              found=_dl['found']),
                          partial_count)

            # ── Difficulty ────────────────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_DIFFICULTY):
                if ui.hit_sec(lx, ly):
                    machine.transition('back')
                    saves_list = game_state.list_saves()
                    _transition(epd, build_main_menu_screen(has_saves=bool(saves_list)),
                                partial_count)
                else:
                    for lvl in range(1, 16):
                        if hit_diff(lvl, lx, ly) and lvl != diff_sel:
                            diff_sel = lvl
                            _show(epd, build_difficulty_screen(diff_sel), partial_count)
                            break
                    if ui.hit_ok(lx, ly, split=True) and diff_sel is not None:
                        machine.transition('ok')
                        color_sel = None
                        _transition(epd, build_color_screen(), partial_count)

            # ── Side selection ────────────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_COLOR):
                if ui.hit_sec(lx, ly):
                    machine.transition('back')
                    _transition(epd, build_difficulty_screen(diff_sel), partial_count)
                else:
                    for i in range(len(COLORS)):
                        if hit_color(i, lx, ly) and i != color_sel:
                            color_sel = i
                            _show(epd, build_color_screen(color_sel), partial_count)
                            break
                    if ui.hit_ok(lx, ly, split=True) and color_sel is not None:
                        if color_sel == 2:
                            player_is_white = random.choice([True, False])
                        else:
                            player_is_white = (color_sel == 0)
                        log.info('Starting — player %s, diff %d',
                                 'White' if player_is_white else 'Black', diff_sel)
                        board        = chess.Board()
                        inv_count    = 0
                        move_history = []
                        sf_time_acc  = [0.0]
                        game_start   = time.time()
                        engine       = chess.engine.SimpleEngine.popen_uci(config.STOCKFISH_PATH)
                        engine.configure({'Skill Level': skill_level(diff_sel),
                                      'Hash': config.DIFF_HASH_MB.get(diff_sel, 16)})
                        engine_limit = think_limit(diff_sel)
                        log.info('Think limit: %.1fs', config.DIFF_THINK_SECS.get(diff_sel, 1.0))

                        save_path = None
                        if player_is_white:
                            cur_move_label = move_label(board)
                            sel_piece = sel_file = sel_rank = None
                            machine.transition('ok')
                            save_path = game_state.save(board, move_history,
                                                        player_is_white, diff_sel)
                            _transition(epd,
                                        build_player_move_screen(None, None, None, 0,
                                                                  cur_move_label),
                                        partial_count)
                        else:
                            sf_label = move_label(board)
                            machine.transition('ok_black')
                            try:
                                sf_san, elapsed = engine_move(
                                    board, engine, engine_limit,
                                    book_path=config.OPENING_BOOK_PATH,
                                    on_thinking=lambda: _transition(
                                        epd, build_thinking_screen(sf_label),
                                        partial_count),
                                )
                            except Exception as exc:
                                log.error('Engine.play failed on opening move: %s', exc)
                                engine.quit()
                                engine = None
                                board = None
                                move_history = []
                                machine.force(ui.SCREEN_GAME_OVER)
                                _transition(epd, build_game_over_screen('Engine error', ''),
                                            partial_count)
                                continue
                            sf_time_acc[0] += elapsed
                            move_history.append(sf_san)
                            log.info('%s (opening): %s',
                                     'Book' if elapsed == 0.0 else 'Stockfish', sf_san)
                            cur_move_label = sf_label
                            machine.transition('done')
                            save_path = game_state.save(board, move_history,
                                                        player_is_white, diff_sel)
                            _transition(epd,
                                        build_sf_move_screen(sf_san, sf_label),
                                        partial_count)

            # ── Stockfish move ────────────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_SF_MOVE):
                if ui.hit_ok(lx, ly, no_title=True):
                    if board.is_game_over():
                        line1, line2 = game_over_message(board, player_is_white)
                        game_over_outcome_code = game_over_outcome(board, player_is_white)
                        machine.transition('game_over')
                        _transition(epd, build_game_over_screen(line1, line2), partial_count)
                    else:
                        cur_move_label = move_label(board)
                        sel_piece = sel_file = sel_rank = None
                        machine.transition('ok')
                        save_path = game_state.save(board, move_history,
                                                    player_is_white, diff_sel,
                                                    save_path)
                        _transition(epd,
                                    build_player_move_screen(None, None, None,
                                                              inv_count, cur_move_label),
                                    partial_count)

            # ── Player move input ─────────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_PLAYER_MOVE):
                if ui.hit_sec(lx, ly, no_title=True):
                    machine.transition('menu')
                    _transition(epd, build_ingame_menu_screen(cur_move_label), partial_count)
                else:
                    changed, sel_piece, sel_file, sel_rank = _scan_move_buttons(
                        lx, ly, sel_piece, sel_file, sel_rank)
                    if changed:
                        _show(epd,
                              build_player_move_screen(sel_piece, sel_file, sel_rank,
                                                        inv_count, cur_move_label),
                              partial_count)
                    elif (ui.hit_ok(lx, ly, split=True, no_title=True)
                            and sel_piece is not None
                            and sel_file  is not None
                            and sel_rank  is not None):
                        if needs_promotion(board, sel_piece, sel_file, sel_rank):
                            prom_piece, prom_file, prom_rank = sel_piece, sel_file, sel_rank
                            sel_promo = None
                            machine.transition('promote')
                            _transition(epd, build_promotion_screen(None, cur_move_label),
                                        partial_count)
                        else:
                            candidates = find_candidates(board, sel_piece, sel_file, sel_rank)
                            if not candidates:
                                inv_count += 1
                                sel_piece = sel_file = sel_rank = None
                                _show(epd,
                                      build_player_move_screen(None, None, None,
                                                                inv_count, cur_move_label),
                                      partial_count)
                            elif len(candidates) == 1:
                                new_screen, cur_move_label = push_and_continue(
                                    board, candidates[0], move_history, engine,
                                    think_limit(diff_sel), epd, partial_count,
                                    player_is_white, inv_count, cur_move_label,
                                    sf_time_acc,
                                    transition_fn=_transition, show_fn=_show)
                                if new_screen == ui.SCREEN_GAME_OVER:
                                    game_over_outcome_code = game_over_outcome(board, player_is_white)
                                machine.force(new_screen)
                                if machine.is_at(ui.SCREEN_PLAYER_MOVE):
                                    sel_piece = sel_file = sel_rank = None
                                    save_path = game_state.save(board, move_history,
                                                                player_is_white, diff_sel,
                                                                save_path)
                            else:
                                disambig_candidates = candidates
                                disambig_labels = [
                                    PIECE_SYMBOLS[sel_piece]
                                    + chess.square_name(m.from_square)
                                    for m in candidates
                                ]
                                disambig_rects_cur = disambig_rects(len(candidates))
                                sel_disambig = None
                                machine.transition('disambig')
                                _transition(epd,
                                            build_disambig_screen(disambig_labels,
                                                                   disambig_rects_cur,
                                                                   None, cur_move_label),
                                            partial_count)

            # ── Pawn promotion ────────────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_PROMOTION):
                changed = False
                for i in range(4):
                    if hit_promo(i, lx, ly) and i != sel_promo:
                        sel_promo = i; changed = True; break
                if changed:
                    _show(epd, build_promotion_screen(sel_promo, cur_move_label),
                          partial_count)
                elif ui.hit_ok(lx, ly) and sel_promo is not None:
                    candidates = find_candidates(board, prom_piece, prom_file,
                                                 prom_rank, sel_promo)
                    if not candidates:
                        log.warning('Promotion move not found')
                        sel_promo = None
                        _show(epd, build_promotion_screen(None, cur_move_label),
                              partial_count)
                    elif len(candidates) == 1:
                        sel_piece = sel_file = sel_rank = None
                        prom_piece = prom_file = prom_rank = sel_promo = None
                        new_screen, cur_move_label = push_and_continue(
                            board, candidates[0], move_history, engine,
                            think_limit(diff_sel), epd, partial_count,
                            player_is_white, inv_count, cur_move_label,
                            sf_time_acc,
                            transition_fn=_transition, show_fn=_show)
                        if new_screen == ui.SCREEN_GAME_OVER:
                            game_over_outcome_code = game_over_outcome(board, player_is_white)
                        machine.force(new_screen)
                        if machine.is_at(ui.SCREEN_PLAYER_MOVE):
                            save_path = game_state.save(board, move_history,
                                                        player_is_white, diff_sel,
                                                        save_path)
                    else:
                        disambig_candidates = candidates
                        disambig_labels = [
                            PIECE_SYMBOLS[prom_piece]
                            + chess.square_name(m.from_square)
                            for m in candidates
                        ]
                        disambig_rects_cur = disambig_rects(len(candidates))
                        sel_disambig = None
                        prom_piece = prom_file = prom_rank = sel_promo = None
                        machine.transition('disambig')
                        _transition(epd,
                                    build_disambig_screen(disambig_labels,
                                                           disambig_rects_cur,
                                                           None, cur_move_label),
                                    partial_count)

            # ── Disambiguation (game) ─────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_DISAMBIG):
                changed = False
                for i in range(len(disambig_candidates)):
                    if hit_disambig(i, disambig_rects_cur, lx, ly) and i != sel_disambig:
                        sel_disambig = i; changed = True; break
                if changed:
                    _show(epd,
                          build_disambig_screen(disambig_labels, disambig_rects_cur,
                                                 sel_disambig, cur_move_label),
                          partial_count)
                elif ui.hit_ok(lx, ly) and sel_disambig is not None:
                    move = disambig_candidates[sel_disambig]
                    sel_disambig = None
                    sel_piece = sel_file = sel_rank = None
                    new_screen, cur_move_label = push_and_continue(
                        board, move, move_history, engine,
                        think_limit(diff_sel), epd, partial_count,
                        player_is_white, inv_count, cur_move_label,
                        sf_time_acc,
                        transition_fn=_transition, show_fn=_show)
                    if new_screen == ui.SCREEN_GAME_OVER:
                        game_over_outcome_code = game_over_outcome(board, player_is_white)
                    machine.force(new_screen)
                    if machine.is_at(ui.SCREEN_PLAYER_MOVE):
                        save_path = game_state.save(board, move_history,
                                                    player_is_white, diff_sel,
                                                    save_path)

            # ── In-game menu (2×2) ────────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_INGAME_MENU):
                if ui.hit_ok(lx, ly):
                    machine.transition('back')
                    _transition(epd,
                                build_player_move_screen(sel_piece, sel_file, sel_rank,
                                                          inv_count, cur_move_label),
                                partial_count)

                elif hit_igmenu(0, lx, ly):
                    machine.transition('resign')
                    _transition(epd, build_resign_confirm_screen(), partial_count)

                elif hit_igmenu(1, lx, ly):
                    machine.transition('board')
                    _transition(epd, build_board_screen(board, player_is_white),
                                partial_count)

                elif hit_igmenu(2, lx, ly):
                    score_end = None
                    machine.transition('scoresheet')
                    _transition(epd,
                                build_scoresheet_screen(move_history, cur_move_label),
                                partial_count)

                elif hit_igmenu(3, lx, ly):
                    machine.transition('time')
                    _transition(epd,
                                build_time_screen(game_start, sf_time_acc[0]),
                                partial_count)

            # ── Resign confirmation ───────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_RESIGN_CONFIRM):
                if hit_resign_yes(lx, ly):
                    log.info('Player resigned')
                    game_state.clear(save_path)
                    save_path = None
                    game_over_outcome_code = game_state.OUTCOME_RESIGNED
                    machine.transition('yes')
                    _transition(epd, build_game_over_screen('Resigned', ''), partial_count)
                elif ui.hit_ok(lx, ly):
                    machine.transition('no')
                    _transition(epd, build_ingame_menu_screen(cur_move_label), partial_count)

            # ── Board display ─────────────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_BOARD):
                if hit_board_back(lx, ly):
                    machine.transition('back')
                    _transition(epd, build_ingame_menu_screen(cur_move_label), partial_count)

            # ── Score sheet (portrait) ────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_SCORESHEET):
                _has_more = len(move_history) > SCORE_ROWS * 2
                if hit_scoresheet_back(tx, ty, has_more=_has_more):
                    machine.transition('back')
                    _transition(epd, build_ingame_menu_screen(cur_move_label), partial_count)
                elif _has_more and hit_scoresheet_more(tx, ty):
                    score_end = next_score_end(move_history, score_end)
                    _transition(epd,
                                build_scoresheet_screen(move_history, cur_move_label,
                                                        score_end=score_end),
                                partial_count)

            # ── Time screen ───────────────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_TIME):
                if ui.hit_ok(lx, ly):
                    machine.transition('ok')
                    _transition(epd, build_ingame_menu_screen(cur_move_label), partial_count)

            # ── Resume / game selection ───────────────────────────────────────
            elif machine.is_at(ui.SCREEN_RESUME):
                show_next = len(saves_list) > 6
                if hit_resume_back(lx, ly, show_next):
                    machine.transition('back')
                    saves_list = game_state.list_saves()
                    _transition(epd,
                                build_main_menu_screen(has_saves=bool(saves_list)),
                                partial_count)

                elif hit_resume_next(lx, ly, show_next):
                    num_pages   = max(1, (len(saves_list) + 5) // 6)
                    resume_page = (resume_page + 1) % num_pages
                    sel_resume  = None
                    machine.transition('next_page')
                    _show(epd,
                          build_resume_screen(saves_list, resume_page, None),
                          partial_count)

                elif hit_resume_ok(lx, ly, show_next) and sel_resume is not None:
                    actual_idx = resume_page * 6 + sel_resume
                    if actual_idx < len(saves_list):
                        sv              = saves_list[actual_idx]
                        save_path       = sv['path']
                        diff_sel        = sv['diff_sel']
                        player_is_white = sv['player_is_white']
                        move_history    = list(sv['move_history'])
                        board           = chess.Board(sv['fen'])
                        inv_count       = 0
                        game_start      = time.time()
                        sf_time_acc     = [0.0]
                        engine          = chess.engine.SimpleEngine.popen_uci(
                                            config.STOCKFISH_PATH)
                        engine.configure({
                            'Skill Level': skill_level(diff_sel),
                            'Hash':        config.DIFF_HASH_MB.get(diff_sel, 16),
                        })
                        cur_move_label = move_label(board)
                        sel_piece = sel_file = sel_rank = None
                        sel_resume = None
                        log.info('Resuming %s diff=%d player=%s fen=%s',
                                 save_path, diff_sel,
                                 'W' if player_is_white else 'B', board.fen())
                        machine.transition('ok')
                        _transition(epd,
                                    build_player_move_screen(None, None, None,
                                                              0, cur_move_label),
                                    partial_count)

                else:
                    page_start = resume_page * 6
                    page_saves = saves_list[page_start:page_start + 6]
                    for slot in range(len(page_saves)):
                        if hit_resume_game(slot, lx, ly) and slot != sel_resume:
                            sel_resume = slot
                            _show(epd,
                                  build_resume_screen(saves_list, resume_page,
                                                      sel_resume),
                                  partial_count)
                            break

            # ── Game over ─────────────────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_GAME_OVER):
                action = hit_game_over(lx, ly)
                if action in ('ok', 'analyze'):
                    if game_over_outcome_code:
                        game_state.record_result(game_over_outcome_code)
                    game_over_outcome_code = ''

                if action == 'ok':
                    game_state.clear(save_path)
                    save_path    = None
                    if engine:
                        engine.quit()
                        engine = None
                    board        = None
                    inv_count    = 0
                    move_history = []
                    game_start   = 0.0
                    sf_time_acc  = [0.0]
                    diff_sel     = None
                    color_sel    = None
                    sel_piece    = sel_file = sel_rank = None
                    saves_list   = game_state.list_saves()
                    machine.transition('ok')
                    _transition(epd, build_splash_screen(sf_info), partial_count)

                elif action == 'analyze':
                    game_state.clear(save_path)
                    save_path            = None
                    analyze_history      = list(move_history)
                    analyze_player_white = player_is_white
                    analyze_idx          = 0
                    analyze_board        = chess.Board()
                    analyze_last_move    = None
                    analyze_played_san   = ''
                    analyze_best_san     = ''
                    if engine and not analyze_board.is_game_over():
                        try:
                            r = engine.play(analyze_board, chess.engine.Limit(time=0.1))
                            analyze_best_san = analyze_board.san(r.move)
                        except Exception:
                            analyze_best_san = ''
                    machine.transition('analyze')
                    _transition(epd,
                                build_analyze_screen(analyze_board, 0,
                                                     len(analyze_history),
                                                     player_is_white=analyze_player_white,
                                                     played_san=analyze_played_san,
                                                     best_san=analyze_best_san),
                                partial_count)

            # ── Analyze: step through game move by move ────────────────────────
            elif machine.is_at(ui.SCREEN_ANALYZE):
                action = hit_analyze(lx, ly, analyze_idx, len(analyze_history))
                if action == 'next' and analyze_idx < len(analyze_history):
                    san = analyze_history[analyze_idx]
                    mv  = analyze_board.parse_san(san)
                    analyze_board.push(mv)
                    analyze_last_move  = mv
                    analyze_played_san = san
                    analyze_idx       += 1
                    if engine and not analyze_board.is_game_over():
                        try:
                            r = engine.play(analyze_board, chess.engine.Limit(time=0.1))
                            analyze_best_san = analyze_board.san(r.move)
                        except Exception:
                            analyze_best_san = ''
                    else:
                        analyze_best_san = ''
                    _show(epd,
                          build_analyze_screen(analyze_board, analyze_idx,
                                               len(analyze_history),
                                               last_move=analyze_last_move,
                                               player_is_white=analyze_player_white,
                                               played_san=analyze_played_san,
                                               best_san=analyze_best_san),
                          partial_count)

                elif action == 'end':
                    game_state.clear(save_path)
                    save_path         = None
                    if engine:
                        engine.quit()
                        engine = None
                    board             = None
                    inv_count         = 0
                    move_history      = []
                    analyze_history   = []
                    analyze_board     = None
                    analyze_last_move = None
                    analyze_played_san = ''
                    analyze_best_san  = ''
                    analyze_idx       = 0
                    game_start        = 0.0
                    sf_time_acc       = [0.0]
                    diff_sel          = None
                    color_sel         = None
                    sel_piece         = sel_file = sel_rank = None
                    saves_list        = game_state.list_saves()
                    machine.transition('end')
                    _transition(epd, build_splash_screen(sf_info), partial_count)

            # ── Puzzle display ────────────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_PUZZLE):
                action = hit_puzzle(lx, ly, board_available=(pz.board is not None))
                if action == 'end':
                    machine.transition('end')
                    _transition(epd, build_puzzle_end_confirm_screen(), partial_count)

                elif action == 'solve' and pz.board is not None:
                    machine.transition('solve')
                    sel_piece = sel_file = sel_rank = None
                    _transition(epd,
                                build_player_move_screen(None, None, None, 0,
                                                          'Puzzle', sec_label='Back'),
                                partial_count)

                elif action == 'skip' and pz.board is not None:
                    pz.last_result = 'skipped'
                    pz.skipped += 1
                    pz.advance()
                    machine.transition('skip')
                    _transition(epd, pz.screen(), partial_count)

            # ── Puzzle end confirmation ───────────────────────────────────────
            elif machine.is_at(ui.SCREEN_PUZZLE_END_CONFIRM):
                action = hit_puzzle_end_confirm(lx, ly)
                if action == 'yes':
                    machine.transition('yes')
                    _transition(epd, build_main_menu_screen(), partial_count)
                elif action == 'no':
                    machine.transition('no')
                    _transition(epd, pz.screen(), partial_count)

            # ── Puzzle move input ─────────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_PUZZLE_MOVE):
                if ui.hit_sec(lx, ly, no_title=True):
                    machine.transition('back')
                    _transition(epd, pz.screen(), partial_count)
                else:
                    changed, sel_piece, sel_file, sel_rank = _scan_move_buttons(
                        lx, ly, sel_piece, sel_file, sel_rank)
                    if changed:
                        _show(epd,
                              build_player_move_screen(sel_piece, sel_file, sel_rank,
                                                        0, 'Puzzle', 'Back'),
                              partial_count)
                    elif (ui.hit_ok(lx, ly, split=True, no_title=True)
                            and sel_piece is not None
                            and sel_file  is not None
                            and sel_rank  is not None):
                        if needs_promotion(pz.board, sel_piece, sel_file, sel_rank):
                            prom_piece, prom_file, prom_rank = sel_piece, sel_file, sel_rank
                            sel_promo = None
                            machine.transition('promote')
                            _transition(epd, build_promotion_screen(None, 'Puzzle'),
                                        partial_count)
                        else:
                            candidates = find_candidates(pz.board, sel_piece,
                                                         sel_file, sel_rank)
                            if not candidates:
                                pz.wrong += 1
                                pz.last_result = 'wrong'
                                pz.hint_fen      = pz.fen
                                pz.hint_moves    = list(pz.moves)
                                pz.hint_move_idx = pz.move_idx
                                log.info('Puzzle wrong: impossible move (p=%s f=%s r=%s)',
                                         sel_piece, sel_file, sel_rank)
                                sel_piece = sel_file = sel_rank = None
                                machine.transition('wrong')
                                _transition(epd, pz.hint_screen(), partial_count)
                            elif len(candidates) == 1:
                                move_uci = candidates[0].uci()
                                sel_piece = sel_file = sel_rank = None
                                result = pz.check_move(move_uci)
                                if result == 'wrong':
                                    machine.transition('wrong')
                                    _transition(epd, pz.hint_screen(), partial_count)
                                else:
                                    machine.transition('ok')
                                    _transition(epd, pz.screen(), partial_count)
                            else:
                                disambig_candidates = candidates
                                disambig_labels = [
                                    PIECE_SYMBOLS[sel_piece]
                                    + chess.square_name(m.from_square)
                                    for m in candidates
                                ]
                                disambig_rects_cur = disambig_rects(len(candidates))
                                sel_disambig = None
                                machine.transition('disambig')
                                _transition(epd,
                                            build_disambig_screen(disambig_labels,
                                                                   disambig_rects_cur,
                                                                   None, 'Puzzle'),
                                            partial_count)

            # ── Puzzle promotion ──────────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_PUZZLE_PROMOTION):
                changed = False
                for i in range(4):
                    if hit_promo(i, lx, ly) and i != sel_promo:
                        sel_promo = i; changed = True; break
                if changed:
                    _show(epd, build_promotion_screen(sel_promo, 'Puzzle'), partial_count)
                elif ui.hit_ok(lx, ly) and sel_promo is not None:
                    candidates = find_candidates(pz.board, prom_piece,
                                                 prom_file, prom_rank, sel_promo)
                    if not candidates:
                        log.warning('Puzzle promotion move not found')
                        sel_promo = None
                        _show(epd, build_promotion_screen(None, 'Puzzle'), partial_count)
                    elif len(candidates) == 1:
                        move_uci = candidates[0].uci()
                        sel_piece = sel_file = sel_rank = None
                        prom_piece = prom_file = prom_rank = None
                        sel_promo = None
                        result = pz.check_move(move_uci)
                        if result == 'wrong':
                            machine.transition('wrong')
                            _transition(epd, pz.hint_screen(), partial_count)
                        else:
                            machine.transition('ok')
                            _transition(epd, pz.screen(), partial_count)
                    else:
                        disambig_candidates = candidates
                        disambig_labels = [
                            PIECE_SYMBOLS[prom_piece]
                            + chess.square_name(m.from_square)
                            for m in candidates
                        ]
                        disambig_rects_cur = disambig_rects(len(candidates))
                        sel_disambig = None
                        prom_piece = prom_file = prom_rank = sel_promo = None
                        machine.transition('disambig')
                        _transition(epd,
                                    build_disambig_screen(disambig_labels,
                                                           disambig_rects_cur,
                                                           None, 'Puzzle'),
                                    partial_count)

            # ── Puzzle disambiguation ─────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_PUZZLE_DISAMBIG):
                changed = False
                for i in range(len(disambig_candidates)):
                    if hit_disambig(i, disambig_rects_cur, lx, ly) and i != sel_disambig:
                        sel_disambig = i; changed = True; break
                if changed:
                    _show(epd,
                          build_disambig_screen(disambig_labels, disambig_rects_cur,
                                                 sel_disambig, 'Puzzle'),
                          partial_count)
                elif ui.hit_ok(lx, ly) and sel_disambig is not None:
                    move_uci = disambig_candidates[sel_disambig].uci()
                    sel_disambig = None
                    sel_piece = sel_file = sel_rank = None
                    result = pz.check_move(move_uci)
                    if result == 'wrong':
                        machine.transition('wrong')
                        _transition(epd, pz.hint_screen(), partial_count)
                    else:
                        machine.transition('ok')
                        _transition(epd, pz.screen(), partial_count)

            # ── Puzzle hint (wrong move → show solution before advancing) ────
            elif machine.is_at(ui.SCREEN_PUZZLE_HINT):
                if hit_puzzle_hint(lx, ly) == 'ok':
                    pz.advance()
                    machine.transition('ok')
                    _transition(epd, pz.screen(), partial_count)

            # ── Stats (puzzle counts) ─────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_STATS):
                action = hit_stats(lx, ly)
                if action == 'back':
                    machine.transition('back')
                    saves_list = game_state.list_saves()
                    _transition(epd,
                                build_main_menu_screen(has_saves=bool(saves_list)),
                                partial_count)
                elif action == 'more':
                    machine.transition('more')
                    _transition(epd, build_game_stats_screen(), partial_count)

            # ── Stats page 2 (game outcomes) ──────────────────────────────────
            elif machine.is_at(ui.SCREEN_GAME_STATS):
                if hit_game_stats(lx, ly) == 'back':
                    machine.transition('back')
                    _transition(epd, build_stats_screen(), partial_count)

            # ── Settings ──────────────────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_SETTINGS):
                action = hit_settings(lx, ly)
                if action == 'back':
                    machine.transition('back')
                    saves_list = game_state.list_saves()
                    _transition(epd,
                                build_main_menu_screen(has_saves=bool(saves_list)),
                                partial_count)
                elif action == 'wifi':
                    machine.transition('wifi')
                    wifi_passwd    = ''
                    wifi_kbd_page  = 0
                    wifi_scroll_off = 0
                    wifi_status    = ''
                    _transition(epd,
                                build_wifi_screen([], None, '', 0, 0),
                                partial_count)
                    wifi_nets = scan_networks()
                    wifi_sel  = next((i for i, n in enumerate(wifi_nets)
                                      if n['in_use']), None)
                    _show(epd,
                          build_wifi_screen(wifi_nets, wifi_sel,
                                            wifi_passwd, wifi_kbd_page,
                                            wifi_scroll_off,
                                            status=wifi_status),
                          partial_count)

            # ── WiFi setup ────────────────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_WIFI):
                action = hit_wifi(lx, ly, wifi_nets, wifi_sel,
                                  wifi_kbd_page, wifi_scroll_off,
                                  status=wifi_status)
                if action == 'back':
                    machine.transition('back')
                    _transition(epd, build_settings_screen(), partial_count)

                elif action == 'back_kbd':
                    wifi_sel    = None
                    wifi_passwd = ''
                    _show(epd,
                          build_wifi_screen(wifi_nets, wifi_sel,
                                            wifi_passwd, wifi_kbd_page,
                                            wifi_scroll_off,
                                            status=wifi_status),
                          partial_count)

                elif action is not None and action.startswith('select:'):
                    new_sel = int(action.split(':')[1])
                    if new_sel != wifi_sel:
                        wifi_sel    = new_sel
                        wifi_passwd = ''
                        wifi_kbd_page = 0
                    wifi_status = ''
                    _show(epd,
                          build_wifi_screen(wifi_nets, wifi_sel,
                                            wifi_passwd, wifi_kbd_page,
                                            wifi_scroll_off,
                                            status=wifi_status),
                          partial_count)

                elif action is not None and action.startswith('char:'):
                    ch = action[5:]
                    wifi_passwd += ch
                    _show(epd,
                          build_wifi_screen(wifi_nets, wifi_sel,
                                            wifi_passwd, wifi_kbd_page,
                                            wifi_scroll_off,
                                            status=wifi_status),
                          partial_count)

                elif action == 'del':
                    wifi_passwd = wifi_passwd[:-1]
                    _show(epd,
                          build_wifi_screen(wifi_nets, wifi_sel,
                                            wifi_passwd, wifi_kbd_page,
                                            wifi_scroll_off,
                                            status=wifi_status),
                          partial_count)

                elif action == 'space':
                    wifi_passwd += ' '
                    _show(epd,
                          build_wifi_screen(wifi_nets, wifi_sel,
                                            wifi_passwd, wifi_kbd_page,
                                            wifi_scroll_off,
                                            status=wifi_status),
                          partial_count)

                elif action == 'prev_page':
                    wifi_kbd_page = (wifi_kbd_page - 1) % _KBD_NUM_PAGES
                    _show(epd,
                          build_wifi_screen(wifi_nets, wifi_sel,
                                            wifi_passwd, wifi_kbd_page,
                                            wifi_scroll_off,
                                            status=wifi_status),
                          partial_count)

                elif action == 'next_page':
                    wifi_kbd_page = (wifi_kbd_page + 1) % _KBD_NUM_PAGES
                    _show(epd,
                          build_wifi_screen(wifi_nets, wifi_sel,
                                            wifi_passwd, wifi_kbd_page,
                                            wifi_scroll_off,
                                            status=wifi_status),
                          partial_count)

                elif action == 'connect_open':
                    net = wifi_nets[wifi_sel]
                    wifi_result_ssid = net['ssid']
                    ok, msg = connect_open(net['ssid'])
                    if ok:
                        wifi_nets = scan_networks()
                        wifi_sel  = next((i for i, n in enumerate(wifi_nets)
                                          if n['in_use']), None)
                        wifi_status = ''
                        _show(epd,
                              build_wifi_screen(wifi_nets, wifi_sel,
                                                wifi_passwd, wifi_kbd_page,
                                                wifi_scroll_off,
                                                status=wifi_status),
                              partial_count)
                    else:
                        wifi_result_msg = msg
                        machine.transition('result')
                        _transition(epd,
                                    build_wifi_result_screen(wifi_result_ssid,
                                                             wifi_result_msg),
                                    partial_count)

                elif action == 'connect_wpa':
                    net = wifi_nets[wifi_sel]
                    wifi_result_ssid = net['ssid']
                    ok, msg = connect_wpa(net['ssid'], wifi_passwd)
                    if ok:
                        wifi_nets = scan_networks()
                        wifi_sel  = next((i for i, n in enumerate(wifi_nets)
                                          if n['in_use']), None)
                        wifi_passwd = ''
                        wifi_status = ''
                        _show(epd,
                              build_wifi_screen(wifi_nets, wifi_sel,
                                                wifi_passwd, wifi_kbd_page,
                                                wifi_scroll_off,
                                                status=wifi_status),
                              partial_count)
                    else:
                        wifi_result_msg = msg
                        machine.transition('result')
                        _transition(epd,
                                    build_wifi_result_screen(wifi_result_ssid,
                                                             wifi_result_msg),
                                    partial_count)

                elif action == 'forget':
                    forgotten_ssid = wifi_nets[wifi_sel]['ssid']
                    forget_network(forgotten_ssid)
                    wifi_nets = scan_networks()
                    # Re-select the forgotten network so user can see it
                    wifi_sel = next(
                        (i for i, n in enumerate(wifi_nets)
                         if n['ssid'] == forgotten_ssid),
                        None,
                    )
                    wifi_status = ('' if any(n['in_use'] for n in wifi_nets)
                                   else 'disconnected')
                    wifi_passwd = ''
                    _show(epd,
                          build_wifi_screen(wifi_nets, wifi_sel,
                                            wifi_passwd, wifi_kbd_page,
                                            wifi_scroll_off,
                                            status=wifi_status),
                          partial_count)

                elif action == 'rescan':
                    wifi_passwd    = ''
                    wifi_kbd_page  = 0
                    wifi_scroll_off = 0
                    wifi_status    = ''
                    _show(epd,
                          build_wifi_screen([], None, '', 0, 0),
                          partial_count)
                    wifi_nets = scan_networks()
                    wifi_sel  = next((i for i, n in enumerate(wifi_nets)
                                      if n['in_use']), None)
                    _show(epd,
                          build_wifi_screen(wifi_nets, wifi_sel,
                                            wifi_passwd, wifi_kbd_page,
                                            wifi_scroll_off,
                                            status=wifi_status),
                          partial_count)

            # ── WiFi result ───────────────────────────────────────────────────
            elif machine.is_at(ui.SCREEN_WIFI_RESULT):
                if hit_wifi_result(lx, ly) == 'ok':
                    machine.transition('ok')
                    _transition(epd,
                                build_wifi_screen(wifi_nets, wifi_sel,
                                                  wifi_passwd, wifi_kbd_page,
                                                  wifi_scroll_off,
                                                  status=wifi_status),
                                partial_count)

            if (config.IDLE_SLEEP_SECS > 0
                    and not machine.is_at(ui.SCREEN_THINKING)
                    and time.time() - last_touch_time > config.IDLE_SLEEP_SECS):
                _sleep_until_touch(epd, dev, partial_count)
                last_touch_time = time.time()
            else:
                time.sleep(0.1)

    except KeyboardInterrupt:
        log.info('Shutting down')
    finally:
        running = False
        if engine:
            engine.quit()
        epd.sleep()
        time.sleep(2)
        epd.Dev_exit()


if __name__ == '__main__':
    main()
