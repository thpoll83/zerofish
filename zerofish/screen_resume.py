"""Game-selection screen shown when the user taps Cont on the splash.

Layout (landscape 250×122):
  - Standard title bar: "ZeroFish: Games"
  - Left content area (x 0–191): 2 rows × 3 cols of game buttons
      each button shows: line 1 = short date, line 2 = first 2 moves
  - Right panel (x 195–247):
      • ≤6 saves → OK (top half) + Back (bottom half)
      • >6 saves → Next (top) + OK (middle) + Back (bottom)
"""
from PIL import Image, ImageDraw
import ui
import config

# ── Grid geometry ─────────────────────────────────────────────────────────────
_COLS  = 3
_ROWS  = 2
_OM    = 2   # outer margin (left/right/top)
_GAP   = 3   # gap between buttons

_GBW = (ui.VSEP_X - 2 * _OM - (_COLS - 1) * _GAP) // _COLS  # ≈ 60 px
_GBH = (ui.H - ui.TITLE_H - 2 * _OM - (_ROWS - 1) * _GAP) // _ROWS  # ≈ 47 px

# ── Right-panel button Y ranges ───────────────────────────────────────────────
_RY0   = ui.OK_Y0   # 27
_RY1   = ui.OK_Y1   # 116
_TOTAL = _RY1 - _RY0  # 89 px

# 2-button layout (no Next)
_OK2_Y0   = _RY0
_OK2_Y1   = _RY0 + (_TOTAL - 2) // 2   # 70
_BACK2_Y0 = _OK2_Y1 + 2                 # 72
_BACK2_Y1 = _RY1                         # 116

# 3-button layout (Next + OK + Back)
_THIRD    = (_TOTAL - 4) // 3            # 28
_NEXT3_Y0 = _RY0                         # 27
_NEXT3_Y1 = _RY0 + _THIRD               # 55
_OK3_Y0   = _NEXT3_Y1 + 2               # 57
_OK3_Y1   = _OK3_Y0 + _THIRD            # 85
_BACK3_Y0 = _OK3_Y1 + 2                 # 87
_BACK3_Y1 = _RY1                         # 116

_BTN_CX = (ui.OK_X0 + ui.OK_X1) // 2   # 221


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slot_rect(slot: int) -> tuple[int, int, int, int]:
    row, col = divmod(slot, _COLS)
    x0 = _OM + col * (_GBW + _GAP)
    y0 = ui.TITLE_H + _OM + row * (_GBH + _GAP)
    return x0, y0, x0 + _GBW - 1, y0 + _GBH - 1


def _moves_label(move_history: list) -> str:
    if not move_history:
        return '(new)'
    label = '1.' + move_history[0]
    if len(move_history) >= 2:
        label += ' ' + move_history[1]
    return label


def _short_date(start_date: str) -> str:
    """Return DDMmmYY from YYYY-MM-DD (e.g. '01May26'), or raw value on error."""
    from datetime import datetime
    try:
        return datetime.strptime(start_date, '%Y-%m-%d').strftime('%d%b%y')
    except Exception:
        return start_date


def _btn_label(sv: dict) -> str:
    """Three-line label: date / strength / first 2 moves."""
    date_str   = _short_date(sv.get('start_date', '?'))
    diff_label = config.DIFF_LABELS.get(sv.get('diff_sel', 1), '?')
    moves_str  = _moves_label(sv.get('move_history', []))
    return f'{date_str}\n{diff_label}\n{moves_str}'


def _draw_right_btn(draw, f, y0: int, y1: int, label: str, active: bool) -> None:
    cy = (y0 + y1) // 2
    if active:
        ui.draw_btn_bar(draw, [(ui.OK_X0, y0), (ui.OK_X1, y1)])
    else:
        ui.draw_btn(draw, [(ui.OK_X0, y0), (ui.OK_X1, y1)], outline=0)
    ui.draw_centered(draw, _BTN_CX, cy, label, f['ok'], 0)


# ── Public API ────────────────────────────────────────────────────────────────

def build_resume_screen(saves: list, page: int = 0,
                        sel: int | None = None) -> Image.Image:
    """
    saves  – full list of save dicts (sorted newest-first)
    page   – current page index (0-based)
    sel    – selected slot on this page (0–5), or None
    """
    img  = Image.new('1', (ui.W, ui.H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts('resume_games')

    show_next = len(saves) > 6
    num_pages = max(1, (len(saves) + 5) // 6)
    page      = page % num_pages
    start_idx = page * 6
    page_saves = saves[start_idx:start_idx + 6]

    # Title bar
    draw.rectangle([(0, 0), (ui.W - 1, ui.TITLE_H - 1)], fill=0)
    draw.text((4, 3), 'ZeroFish: Games', font=f['title'], fill=255)

    # Vertical separator
    draw.line([(ui.VSEP_X, ui.TITLE_H), (ui.VSEP_X, ui.H - 1)], fill=0)

    # Game buttons — white bg for white player, black bg for black player
    for slot, sv in enumerate(page_saves):
        x0, y0, x1, y1 = _slot_rect(slot)
        active          = (slot == sel)
        is_white_player = sv.get('player_is_white', True)

        if is_white_player:
            if active:
                ui.draw_btn_bar(draw, [(x0, y0), (x1, y1)])  # black bar at bottom
            else:
                ui.draw_btn(draw, [(x0, y0), (x1, y1)], outline=0)
            text_fill = 0
        else:
            if active:
                ui.draw_btn_bar_inv(draw, [(x0, y0), (x1, y1)])  # white bar at bottom
            else:
                ui.draw_btn(draw, [(x0, y0), (x1, y1)], fill=0)
            text_fill = 255

        cx = (x0 + x1) // 2
        cy = (y0 + y1 - 5) // 2 - 2
        ui.draw_centered(draw, cx, cy, _btn_label(sv), f['small'], text_fill, line_spacing=13)

    # Right-panel buttons
    if show_next:
        _draw_right_btn(draw, f, _NEXT3_Y0, _NEXT3_Y1, 'Next', False)
        _draw_right_btn(draw, f, _OK3_Y0,   _OK3_Y1,   'OK',   sel is not None)
        _draw_right_btn(draw, f, _BACK3_Y0, _BACK3_Y1, 'Back', False)
    else:
        _draw_right_btn(draw, f, _OK2_Y0,   _OK2_Y1,   'OK',   sel is not None)
        _draw_right_btn(draw, f, _BACK2_Y0, _BACK2_Y1, 'Back', False)

    return img


def hit_game_btn(slot: int, lx: int, ly: int) -> bool:
    x0, y0, x1, y1 = _slot_rect(slot)
    return x0 <= lx <= x1 and y0 <= ly <= y1


def hit_next(lx: int, ly: int, show_next: bool) -> bool:
    return (show_next
            and ui.OK_X0 <= lx <= ui.OK_X1
            and _NEXT3_Y0 <= ly <= _NEXT3_Y1)


def hit_ok(lx: int, ly: int, show_next: bool) -> bool:
    if show_next:
        return ui.OK_X0 <= lx <= ui.OK_X1 and _OK3_Y0 <= ly <= _OK3_Y1
    return ui.OK_X0 <= lx <= ui.OK_X1 and _OK2_Y0 <= ly <= _OK2_Y1


def hit_back(lx: int, ly: int, show_next: bool) -> bool:
    if show_next:
        return ui.OK_X0 <= lx <= ui.OK_X1 and _BACK3_Y0 <= ly <= _BACK3_Y1
    return ui.OK_X0 <= lx <= ui.OK_X1 and _BACK2_Y0 <= ly <= _BACK2_Y1
