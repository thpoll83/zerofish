import os
from PIL import Image, ImageDraw, ImageFont
import config

# ── Derived layout constants ──────────────────────────────────────────────────
W       = config.DISPLAY_W
H       = config.DISPLAY_H
TITLE_H = config.TITLE_H
VSEP_X  = config.VSEP_X
OK_X0   = config.VSEP_X + config.OK_GAP_X
OK_X1   = config.DISPLAY_W - config.OK_GAP_RIGHT
OK_Y0   = config.TITLE_H + config.OK_GAP_Y
OK_Y1   = config.DISPLAY_H - config.OK_GAP_Y
_OK_MID     = OK_Y0 + (OK_Y1 - OK_Y0) // 2
OK_Y1_SPLIT = _OK_MID - 2
SEC_Y0      = _OK_MID + 2
SEC_Y1      = OK_Y1

# ── Screen IDs ────────────────────────────────────────────────────────────────
SCREEN_DIFFICULTY  = 0
SCREEN_COLOR       = 1
SCREEN_THINKING    = 2
SCREEN_SF_MOVE     = 3
SCREEN_PLAYER_MOVE = 4
SCREEN_GAME_OVER   = 5
SCREEN_PROMOTION   = 6
SCREEN_DISAMBIG    = 7
SCREEN_INGAME_MENU = 8
SCREEN_SCORESHEET  = 9
SCREEN_BOARD       = 10
SCREEN_SPLASH      = 11
SCREEN_TIME        = 12

# ── Font cache ────────────────────────────────────────────────────────────────
_fonts = None


def load_fonts() -> dict:
    global _fonts
    if _fonts is not None:
        return _fonts
    try:
        bold = next((p for p in config.FONT_BOLD_PATHS if os.path.exists(p)),
                    config.FONT_BOLD_PATHS[-1])
        reg  = next((p for p in config.FONT_REG_PATHS  if os.path.exists(p)),
                    config.FONT_REG_PATHS[-1])
        plain_reg = next((p for p in config.FONT_PLAIN_PATHS if os.path.exists(p)),
                         config.FONT_PLAIN_PATHS[-1])
        fonts = {
            'title':    ImageFont.truetype(bold,      config.SIZE_HEADLINE),
            'ver':      ImageFont.truetype(reg,        config.SIZE_VERSION),
            'btn':      ImageFont.truetype(bold,      config.SIZE_BTN),
            'ok':       ImageFont.truetype(bold,      config.SIZE_BTN_OK),
            'move':     ImageFont.truetype(bold,      config.SIZE_MOVE),
            'result':   ImageFont.truetype(bold,      config.SIZE_RESULT),
            'small':    ImageFont.truetype(reg,        config.SIZE_LABEL),
            'plain':    ImageFont.truetype(plain_reg,  config.SIZE_TEXT),
            'plain_lg': ImageFont.truetype(plain_reg,  config.SIZE_TEXT_LG),
        }
        piece_path = next((p for p in config.FONT_PIECE_PATHS if os.path.exists(p)), None)
        if piece_path:
            fonts['piece']      = ImageFont.truetype(piece_path, config.SIZE_PIECE)
            fonts['move_piece'] = ImageFont.truetype(piece_path, config.SIZE_MOVE)
            fonts['promo']      = ImageFont.truetype(piece_path, config.SIZE_PROMO)
            fonts['board']      = ImageFont.truetype(piece_path, config.SIZE_BOARD_PIECE)
        else:
            fonts['piece']      = fonts['btn']
            fonts['move_piece'] = fonts['move']
            fonts['promo']      = fonts['move']
            fonts['board']      = fonts['btn']
        _fonts = fonts
    except Exception:
        f = ImageFont.load_default()
        _fonts = {k: f for k in (
            'title', 'ver', 'btn', 'ok', 'move', 'result', 'small',
            'plain', 'plain_lg', 'piece', 'move_piece', 'promo', 'board',
        )}
    return _fonts


def invalidate_fonts():
    global _fonts
    _fonts = None


# ── Drawing helpers ───────────────────────────────────────────────────────────

def draw_centered(draw, cx, cy, text, font, fill):
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    ascent, descent = font.getmetrics()
    draw.text(
        (cx - tw // 2 - bb[0],
         cy - (ascent + descent) // 2),
        text, font=font, fill=fill,
    )


def draw_chrome(draw, f, screen_title='', ok_active=False, sec_label=None, ok_label='OK'):
    draw.rectangle([(0, 0), (W - 1, TITLE_H - 1)], fill=0)
    label = f'ZeroFish: {screen_title}' if screen_title else 'ZeroFish'
    draw.text((4, 3), label, font=f['title'], fill=255)
    ver = f'v{config.VERSION}'
    vw = draw.textbbox((0, 0), ver, font=f['ver'])[2]
    draw.text((W - vw - 4, 5), ver, font=f['ver'], fill=255)

    draw.line([(VSEP_X, TITLE_H), (VSEP_X, H - 1)], fill=0)

    cx    = (OK_X0 + OK_X1) // 2
    ok_y1 = OK_Y1_SPLIT if sec_label else OK_Y1
    ok_cy = (OK_Y0 + ok_y1) // 2
    if ok_active:
        draw.rectangle([(OK_X0, OK_Y0), (OK_X1, ok_y1)], fill=0)
        draw_centered(draw, cx, ok_cy, ok_label, f['ok'], 255)
    else:
        draw.rectangle([(OK_X0, OK_Y0), (OK_X1, ok_y1)], outline=0)
        draw_centered(draw, cx, ok_cy, ok_label, f['ok'], 0)

    if sec_label:
        sec_cy = (SEC_Y0 + SEC_Y1) // 2
        draw.rectangle([(OK_X0, SEC_Y0), (OK_X1, SEC_Y1)], outline=0)
        draw_centered(draw, cx, sec_cy, sec_label, f['btn'], 0)


# ── Touch helpers ─────────────────────────────────────────────────────────────

def to_landscape(tx: int, ty: int) -> tuple[int, int]:
    return (249 - ty, tx)


def hit_ok(lx: int, ly: int, split: bool = False) -> bool:
    y1 = OK_Y1_SPLIT if split else OK_Y1
    return OK_X0 <= lx <= OK_X1 and OK_Y0 <= ly <= y1


def hit_sec(lx: int, ly: int) -> bool:
    return OK_X0 <= lx <= OK_X1 and SEC_Y0 <= ly <= SEC_Y1


# ── SAN glyph substitution ────────────────────────────────────────────────────
_SAN_TO_GLYPH = {'N': '♞', 'B': '♝', 'R': '♜', 'Q': '♛', 'K': '♚'}


def san_with_glyph(san: str) -> str:
    if san and san[0] in _SAN_TO_GLYPH:
        san = _SAN_TO_GLYPH[san[0]] + san[1:]
    eq = san.find('=')
    if eq != -1 and eq + 1 < len(san) and san[eq + 1] in _SAN_TO_GLYPH:
        san = san[:eq + 1] + _SAN_TO_GLYPH[san[eq + 1]] + san[eq + 2:]
    return san
