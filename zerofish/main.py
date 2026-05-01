#!/usr/bin/env python3
"""ZeroFish — chess computer for the WaveShare 2.13" Touch e-Paper HAT V4.

Landscape orientation: hold the device with the short edge at top/bottom
(rotated 90° clockwise from portrait, USB port on the left side).
Score sheet uses portrait orientation (USB at bottom).
"""

import time
import random
import logging
import threading
import subprocess

from TP_lib import epd2in13_V4, gt1151
import chess
import chess.engine

import config
import game_state
import ui
from screen_splash       import (get_sf_info, build_splash_screen,
                                  hit_splash_ok, hit_splash_resume)
from screen_difficulty   import build_difficulty_screen, hit_diff
from screen_color        import build_color_screen, hit_color, COLORS
from screen_thinking     import build_thinking_screen
from screen_sf_move      import build_sf_move_screen
from screen_game_over    import build_game_over_screen, game_over_message
from screen_player_move  import (build_player_move_screen, hit_pm_piece, hit_pm_file,
                                  hit_pm_rank, find_candidates, needs_promotion,
                                  PIECES, PIECE_SYMBOLS, FILES, RANKS)
from screen_promotion    import build_promotion_screen, hit_promo, PROMO_PIECE_TYPES
from screen_disambig     import build_disambig_screen, hit_disambig, disambig_rects
from screen_ingame_menu    import build_ingame_menu_screen, hit_igmenu
from screen_resign_confirm import build_resign_confirm_screen, hit_resign_yes
from screen_time           import build_time_screen
from screen_board        import build_board_screen, hit_board_back
from screen_scoresheet   import build_scoresheet_screen, hit_scoresheet_back

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
log = logging.getLogger('zerofish')

def _skill_level(difficulty):
    return config.DIFF_SKILL_LEVELS.get(difficulty, 0)


def _think_limit(difficulty):
    return chess.engine.Limit(time=config.DIFF_THINK_SECS.get(difficulty, 1.0))


def _move_label(board: chess.Board) -> str:
    n = board.fullmove_number
    return f'#{n}' if board.turn == chess.WHITE else f'#…{n}'


_last_display_buf = None


def _transition(epd, img, partial_count):
    global _last_display_buf
    buf = epd.getbuffer(img)
    _last_display_buf = buf
    epd.init(epd.FULL_UPDATE)
    epd.displayPartBaseImage(buf)
    epd.init(epd.PART_UPDATE)
    partial_count[0] = 0


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


def _set_cpu_governor(gov):
    subprocess.run(['sudo', '/usr/local/bin/zerofish-set-governor', gov],
                   check=False, capture_output=True)


def _push_and_continue(board, move, move_history, engine, think_limit,
                        epd, partial_count, player_is_white, inv_count,
                        cur_move_label, sf_time_acc=None):
    """Push player move → check game over → Stockfish reply.
    Returns (new_screen, new_move_label).
    """
    san = board.san(move)
    board.push(move)
    move_history.append(san)
    log.info('Player: %s', san)

    if board.is_game_over():
        log.info('Game over: %s', board.result())
        line1, line2 = game_over_message(board, player_is_white)
        _transition(epd, build_game_over_screen(line1, line2), partial_count)
        return ui.SCREEN_GAME_OVER, cur_move_label

    sf_label = _move_label(board)
    _transition(epd, build_thinking_screen(), partial_count)
    t0     = time.time()
    _set_cpu_governor('performance')
    result = engine.play(board, think_limit)
    _set_cpu_governor('powersave')
    if sf_time_acc is not None:
        sf_time_acc[0] += time.time() - t0
    sf_san = board.san(result.move)
    board.push(result.move)
    move_history.append(sf_san)
    log.info('Stockfish: %s', sf_san)
    _transition(epd, build_sf_move_screen(sf_san, sf_label), partial_count)
    return ui.SCREEN_SF_MOVE, sf_label


def main():
    epd = epd2in13_V4.EPD()
    gt  = gt1151.GT1151()
    dev = gt1151.GT_Development()
    old = gt1151.GT_Development()

    log.info('ZeroFish v%s starting', config.VERSION)

    log.info('Probing Stockfish…')
    sf_info   = get_sf_info()
    log.info('Engine: %s  %s', sf_info[0], sf_info[1])
    save_data = game_state.load()
    log.info('Resume available: %s', save_data is not None)

    epd.init(epd.FULL_UPDATE)
    gt.GT_Init()
    epd.Clear(0xFF)
    epd.displayPartBaseImage(epd.getbuffer(
        build_splash_screen(sf_info, has_resume=(save_data is not None))
    ))
    epd.init(epd.PART_UPDATE)

    screen          = ui.SCREEN_SPLASH
    diff_sel        = None
    color_sel       = None
    partial_count   = [0]
    last_touch_time = time.time()

    # Game state
    board               = None
    engine              = None
    think_limit         = chess.engine.Limit(time=1.0)
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
    # Time tracking
    game_start  = 0.0
    sf_time_acc = [0.0]

    running = True
    def irq_poll():
        while running:
            dev.Touch = 1 if gt.digital_read(gt.INT) == 0 else 0
    threading.Thread(target=irq_poll, daemon=True).start()

    log.info('Ready')

    try:
        while True:
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

            lx, ly = ui.to_landscape(dev.X[0], dev.Y[0])   # landscape coords
            tx, ty = dev.X[0], dev.Y[0]                     # portrait / raw

            # ── Splash ───────────────────────────────────────────────────────
            if screen == ui.SCREEN_SPLASH:
                if hit_splash_ok(lx, ly, has_resume=(save_data is not None)):
                    save_data = None
                    game_state.clear()
                    screen = ui.SCREEN_DIFFICULTY
                    diff_sel = None
                    _transition(epd, build_difficulty_screen(), partial_count)

                elif save_data is not None and hit_splash_resume(lx, ly):
                    diff_sel        = save_data['diff_sel']
                    player_is_white = save_data['player_is_white']
                    move_history    = list(save_data['move_history'])
                    board           = chess.Board(save_data['fen'])
                    inv_count       = 0
                    game_start      = time.time()
                    sf_time_acc     = [0.0]
                    engine          = chess.engine.SimpleEngine.popen_uci(config.STOCKFISH_PATH)
                    engine.configure({'Skill Level': _skill_level(diff_sel),
                                      'Hash': config.DIFF_HASH_MB.get(diff_sel, 16)})
                    think_limit     = _think_limit(diff_sel)
                    cur_move_label  = _move_label(board)
                    sel_piece = sel_file = sel_rank = None
                    save_data       = None
                    log.info('Resuming game: diff=%d player=%s fen=%s',
                             diff_sel, 'W' if player_is_white else 'B', board.fen())
                    screen = ui.SCREEN_PLAYER_MOVE
                    _transition(epd,
                                build_player_move_screen(None, None, None, 0, cur_move_label),
                                partial_count)

            # ── Difficulty ────────────────────────────────────────────────────
            elif screen == ui.SCREEN_DIFFICULTY:
                for lvl in range(1, 16):
                    if hit_diff(lvl, lx, ly) and lvl != diff_sel:
                        diff_sel = lvl
                        _show(epd, build_difficulty_screen(diff_sel), partial_count)
                        break
                if ui.hit_ok(lx, ly) and diff_sel is not None:
                    screen = ui.SCREEN_COLOR
                    color_sel = None
                    _transition(epd, build_color_screen(), partial_count)

            # ── Side selection ────────────────────────────────────────────────
            elif screen == ui.SCREEN_COLOR:
                if ui.hit_sec(lx, ly):
                    screen = ui.SCREEN_DIFFICULTY
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
                        engine.configure({'Skill Level': _skill_level(diff_sel),
                                      'Hash': config.DIFF_HASH_MB.get(diff_sel, 16)})
                        think_limit  = _think_limit(diff_sel)
                        log.info('Think limit: %.1fs', config.DIFF_THINK_SECS.get(diff_sel, 1.0))

                        if player_is_white:
                            cur_move_label = _move_label(board)
                            sel_piece = sel_file = sel_rank = None
                            screen = ui.SCREEN_PLAYER_MOVE
                            game_state.save(board, move_history, player_is_white, diff_sel)
                            _transition(epd,
                                        build_player_move_screen(None, None, None, 0,
                                                                  cur_move_label),
                                        partial_count)
                        else:
                            sf_label = _move_label(board)
                            _transition(epd, build_thinking_screen(), partial_count)
                            t0 = time.time()
                            _set_cpu_governor('performance')
                            result = engine.play(board, think_limit)
                            _set_cpu_governor('powersave')
                            sf_time_acc[0] += time.time() - t0
                            sf_san = board.san(result.move)
                            board.push(result.move)
                            move_history.append(sf_san)
                            log.info('Stockfish: %s', sf_san)
                            cur_move_label = sf_label
                            screen = ui.SCREEN_SF_MOVE
                            game_state.save(board, move_history, player_is_white, diff_sel)
                            _transition(epd,
                                        build_sf_move_screen(sf_san, sf_label),
                                        partial_count)

            # ── Stockfish move ────────────────────────────────────────────────
            elif screen == ui.SCREEN_SF_MOVE:
                if ui.hit_ok(lx, ly):
                    if board.is_game_over():
                        line1, line2 = game_over_message(board, player_is_white)
                        screen = ui.SCREEN_GAME_OVER
                        _transition(epd, build_game_over_screen(line1, line2), partial_count)
                    else:
                        cur_move_label = _move_label(board)
                        sel_piece = sel_file = sel_rank = None
                        screen = ui.SCREEN_PLAYER_MOVE
                        game_state.save(board, move_history, player_is_white, diff_sel)
                        _transition(epd,
                                    build_player_move_screen(None, None, None,
                                                              inv_count, cur_move_label),
                                    partial_count)

            # ── Player move input ─────────────────────────────────────────────
            elif screen == ui.SCREEN_PLAYER_MOVE:
                if ui.hit_sec(lx, ly):
                    screen = ui.SCREEN_INGAME_MENU
                    _transition(epd, build_ingame_menu_screen(cur_move_label), partial_count)
                else:
                    changed = False
                    for i in range(len(PIECES)):
                        if hit_pm_piece(i, lx, ly) and i != sel_piece:
                            sel_piece = i; changed = True; break
                    if not changed:
                        for i in range(len(FILES)):
                            if hit_pm_file(i, lx, ly) and i != sel_file:
                                sel_file = i; changed = True; break
                    if not changed:
                        for i in range(len(RANKS)):
                            if hit_pm_rank(i, lx, ly) and i != sel_rank:
                                sel_rank = i; changed = True; break

                    if changed:
                        _show(epd,
                              build_player_move_screen(sel_piece, sel_file, sel_rank,
                                                        inv_count, cur_move_label),
                              partial_count)
                    elif (ui.hit_ok(lx, ly, split=True)
                            and sel_piece is not None
                            and sel_file  is not None
                            and sel_rank  is not None):
                        if needs_promotion(board, sel_piece, sel_file, sel_rank):
                            prom_piece, prom_file, prom_rank = sel_piece, sel_file, sel_rank
                            sel_promo = None
                            screen = ui.SCREEN_PROMOTION
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
                                screen, cur_move_label = _push_and_continue(
                                    board, candidates[0], move_history, engine,
                                    think_limit, epd, partial_count,
                                    player_is_white, inv_count, cur_move_label,
                                    sf_time_acc)
                                if screen == ui.SCREEN_PLAYER_MOVE:
                                    sel_piece = sel_file = sel_rank = None
                                    game_state.save(board, move_history,
                                                    player_is_white, diff_sel)
                            else:
                                disambig_candidates = candidates
                                disambig_labels = [
                                    PIECE_SYMBOLS[sel_piece]
                                    + chess.square_name(m.from_square)
                                    for m in candidates
                                ]
                                disambig_rects_cur = disambig_rects(len(candidates))
                                sel_disambig = None
                                screen = ui.SCREEN_DISAMBIG
                                _transition(epd,
                                            build_disambig_screen(disambig_labels,
                                                                   disambig_rects_cur,
                                                                   None, cur_move_label),
                                            partial_count)

            # ── Pawn promotion ────────────────────────────────────────────────
            elif screen == ui.SCREEN_PROMOTION:
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
                        screen, cur_move_label = _push_and_continue(
                            board, candidates[0], move_history, engine,
                            think_limit, epd, partial_count,
                            player_is_white, inv_count, cur_move_label,
                            sf_time_acc)
                        if screen == ui.SCREEN_PLAYER_MOVE:
                            game_state.save(board, move_history, player_is_white, diff_sel)
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
                        screen = ui.SCREEN_DISAMBIG
                        _transition(epd,
                                    build_disambig_screen(disambig_labels,
                                                           disambig_rects_cur,
                                                           None, cur_move_label),
                                    partial_count)

            # ── Disambiguation ────────────────────────────────────────────────
            elif screen == ui.SCREEN_DISAMBIG:
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
                    screen, cur_move_label = _push_and_continue(
                        board, move, move_history, engine,
                        think_limit, epd, partial_count,
                        player_is_white, inv_count, cur_move_label,
                        sf_time_acc)
                    if screen == ui.SCREEN_PLAYER_MOVE:
                        game_state.save(board, move_history, player_is_white, diff_sel)

            # ── In-game menu (2×2) ────────────────────────────────────────────
            elif screen == ui.SCREEN_INGAME_MENU:
                if ui.hit_ok(lx, ly):               # Back → player move
                    screen = ui.SCREEN_PLAYER_MOVE
                    _transition(epd,
                                build_player_move_screen(sel_piece, sel_file, sel_rank,
                                                          inv_count, cur_move_label),
                                partial_count)

                elif hit_igmenu(0, lx, ly):          # Resign → confirm first
                    screen = ui.SCREEN_RESIGN_CONFIRM
                    _transition(epd, build_resign_confirm_screen(), partial_count)

                elif hit_igmenu(1, lx, ly):          # Board
                    screen = ui.SCREEN_BOARD
                    _transition(epd, build_board_screen(board, player_is_white),
                                partial_count)

                elif hit_igmenu(2, lx, ly):          # Score sheet
                    screen = ui.SCREEN_SCORESHEET
                    _transition(epd,
                                build_scoresheet_screen(move_history, cur_move_label),
                                partial_count)

                elif hit_igmenu(3, lx, ly):          # Time
                    screen = ui.SCREEN_TIME
                    _transition(epd,
                                build_time_screen(game_start, sf_time_acc[0]),
                                partial_count)

            # ── Resign confirmation ───────────────────────────────────────────
            elif screen == ui.SCREEN_RESIGN_CONFIRM:
                if hit_resign_yes(lx, ly):           # Yes → resign
                    log.info('Player resigned')
                    game_state.clear()
                    screen = ui.SCREEN_GAME_OVER
                    _transition(epd, build_game_over_screen('Resigned', ''), partial_count)
                elif ui.hit_ok(lx, ly):              # No → back to in-game menu
                    screen = ui.SCREEN_INGAME_MENU
                    _transition(epd, build_ingame_menu_screen(cur_move_label), partial_count)

            # ── Board display ─────────────────────────────────────────────────
            elif screen == ui.SCREEN_BOARD:
                if hit_board_back(lx, ly):
                    screen = ui.SCREEN_INGAME_MENU
                    _transition(epd, build_ingame_menu_screen(cur_move_label), partial_count)

            # ── Score sheet (portrait) ────────────────────────────────────────
            elif screen == ui.SCREEN_SCORESHEET:
                if hit_scoresheet_back(tx, ty):
                    screen = ui.SCREEN_INGAME_MENU
                    _transition(epd, build_ingame_menu_screen(cur_move_label), partial_count)

            # ── Time screen ───────────────────────────────────────────────────
            elif screen == ui.SCREEN_TIME:
                if ui.hit_ok(lx, ly):
                    screen = ui.SCREEN_INGAME_MENU
                    _transition(epd, build_ingame_menu_screen(cur_move_label), partial_count)

            # ── Game over ─────────────────────────────────────────────────────
            elif screen == ui.SCREEN_GAME_OVER:
                if ui.hit_ok(lx, ly):
                    game_state.clear()
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
                    save_data    = None
                    screen = ui.SCREEN_SPLASH
                    _transition(epd,
                                build_splash_screen(sf_info, has_resume=False),
                                partial_count)

            if (config.IDLE_SLEEP_SECS > 0
                    and screen != ui.SCREEN_THINKING
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
