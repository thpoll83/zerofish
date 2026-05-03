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

# No-title chrome: two-line black header above OK button; no title bar drawn
NT_LABEL_H     = 36
_NT_LABEL_CY1  = NT_LABEL_H // 4          # = 9  (centre of line 1)
_NT_LABEL_CY2  = NT_LABEL_H * 3 // 4      # = 27 (centre of line 2)
NT_OK_Y0       = NT_LABEL_H + 4           # = 40
NT_OK_Y1       = config.DISPLAY_H - 2     # = 120
_NT_MID_Y      = (NT_OK_Y0 + NT_OK_Y1) // 2  # = 80
NT_OK_Y1_SPLIT = _NT_MID_Y - 2           # = 78
NT_SEC_Y0      = _NT_MID_Y + 2           # = 82
NT_SEC_Y1      = NT_OK_Y1               # = 120

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
SCREEN_BOARD          = 10
SCREEN_SPLASH         = 11
SCREEN_TIME           = 12
SCREEN_RESIGN_CONFIRM = 13
SCREEN_RESUME         = 14

# ── Font cache (keyed by family name) ─────────────────────────────────────────
_fonts_cache: dict = {}


def load_fonts(screen: str = 'default') -> dict:
    """Return the font dict for *screen*, resolved via config.SCREEN_FONT_FAMILY.

    Results are cached per font family so switching between two screens that
    share a family costs nothing.
    """
    family = config.SCREEN_FONT_FAMILY.get(
        screen,
        config.SCREEN_FONT_FAMILY.get('default', 'dejavu_cond'),
    )

    if family in _fonts_cache:
        return _fonts_cache[family]

    fam_paths = config.FONT_FAMILIES.get(family, config.FONT_FAMILIES['dejavu_cond'])
    bold_paths = fam_paths['bold']
    reg_paths  = fam_paths['reg']
    bold = next((p for p in bold_paths if os.path.exists(p)), bold_paths[-1])
    reg  = next((p for p in reg_paths  if os.path.exists(p)), reg_paths[-1])

    try:
        fonts = {
            'title':    ImageFont.truetype(bold, config.SIZE_HEADLINE),
            'ver':      ImageFont.truetype(reg,  config.SIZE_VERSION),
            'btn':      ImageFont.truetype(bold, config.SIZE_BTN),
            'btn_diff': ImageFont.truetype(bold, config.SIZE_BTN_DIFF),
            'ok':       ImageFont.truetype(bold, config.SIZE_BTN_OK),
            'move':     ImageFont.truetype(bold, config.SIZE_MOVE),
            'result':   ImageFont.truetype(bold, config.SIZE_RESULT),
            'small':    ImageFont.truetype(reg,  config.SIZE_LABEL),
            'plain':    ImageFont.truetype(reg,  config.SIZE_TEXT),
            'plain_lg': ImageFont.truetype(reg,  config.SIZE_TEXT_LG),
        }
        piece_path = next(
            (p for p in config.FONT_PIECE_PATHS if os.path.exists(p)), None
        )
        if piece_path:
            fonts['piece']      = ImageFont.truetype(piece_path, config.SIZE_PIECE)
            fonts['sf_piece']   = ImageFont.truetype(piece_path, config.SIZE_MOVE_PIECE)
            fonts['move_piece'] = fonts['move']
            fonts['promo']      = ImageFont.truetype(piece_path, config.SIZE_PROMO)
            fonts['board']      = ImageFont.truetype(piece_path, config.SIZE_BOARD_PIECE)
        else:
            fonts['piece']      = fonts['btn']
            fonts['sf_piece']   = fonts['move']
            fonts['move_piece'] = fonts['move']
            fonts['promo']      = fonts['move']
            fonts['board']      = fonts['btn']
    except Exception:
        f = ImageFont.load_default()
        fonts = {k: f for k in (
            'title', 'ver', 'btn', 'btn_diff', 'ok', 'move', 'result', 'small',
            'plain', 'plain_lg', 'piece', 'sf_piece', 'move_piece', 'promo', 'board',
        )}

    _fonts_cache[family] = fonts
    return fonts


def invalidate_fonts() -> None:
    _fonts_cache.clear()


# ── Drawing helpers ───────────────────────────────────────────────────────────

_BTN_RADIUS  = 3
_BTN_BAR_H   = 5   # height of bottom-bar active indicator in pixels


def draw_btn(draw, coords, *, fill=None, outline=None, width=1):
    """Draw a button rectangle with rounded corners (radius 3 px)."""
    draw.rounded_rectangle(coords, radius=_BTN_RADIUS, fill=fill, outline=outline, width=width)


def draw_btn_bar(draw, coords):
    """Draw a button with a solid black bar across the bottom 5 rows (active indicator)."""
    x0, y0 = coords[0]
    x1, y1 = coords[1]
    draw.rounded_rectangle(coords, radius=_BTN_RADIUS, outline=0)
    draw.rectangle([(x0 + 1, y1 - _BTN_BAR_H), (x1 - 1, y1 - 1)], fill=0)


def draw_btn_bar_inv(draw, coords):
    """Black-filled button with a white bar at the bottom (selected state for dark buttons)."""
    x0, y0 = coords[0]
    x1, y1 = coords[1]
    draw.rounded_rectangle(coords, radius=_BTN_RADIUS, fill=0)
    draw.rectangle([(x0 + 1, y1 - _BTN_BAR_H), (x1 - 1, y1 - 1)], fill=255)


def draw_centered(draw, cx, cy, text, font, fill, line_spacing=None):
    lines = text.split('\n')
    ascent, descent = font.getmetrics()
    line_h = line_spacing if line_spacing is not None else (ascent + descent)
    y_top = cy - line_h * len(lines) // 2
    for i, line in enumerate(lines):
        bb = draw.textbbox((0, 0), line, font=font)
        tw = bb[2] - bb[0]
        draw.text(
            (cx - tw // 2 - bb[0], y_top + i * line_h),
            line, font=font, fill=fill,
        )


def draw_chrome(draw, f, screen_title='', ok_active=False, sec_label=None,
                ok_label='OK', no_title=False, nt_sub=''):
    cx = (OK_X0 + OK_X1) // 2
    if no_title:
        # Black header across the right panel; white text, same font as title bar
        draw.rectangle([(VSEP_X, 0), (W - 1, NT_LABEL_H - 1)], fill=0)
        draw.line([(VSEP_X, NT_LABEL_H), (VSEP_X, H - 1)], fill=0)
        if screen_title:
            draw_centered(draw, cx, _NT_LABEL_CY1, screen_title, f['title'], 255)
        if nt_sub:
            draw_centered(draw, cx, _NT_LABEL_CY2, nt_sub, f['title'], 255)
        ok_y0 = NT_OK_Y0
        ok_y1 = NT_OK_Y1_SPLIT if sec_label else NT_OK_Y1
        ok_cy = (ok_y0 + ok_y1) // 2
    else:
        draw.rectangle([(0, 0), (W - 1, TITLE_H - 1)], fill=0)
        label = f'ZeroFish: {screen_title}' if screen_title else 'ZeroFish'
        draw.text((4, 3), label, font=f['title'], fill=255)
        draw.line([(VSEP_X, TITLE_H), (VSEP_X, H - 1)], fill=0)
        ok_y0 = OK_Y0
        ok_y1 = OK_Y1_SPLIT if sec_label else OK_Y1
        ok_cy = (ok_y0 + ok_y1) // 2

    if ok_active:
        draw_btn_bar(draw, [(OK_X0, ok_y0), (OK_X1, ok_y1)])
        draw_centered(draw, cx, ok_cy, ok_label, f['ok'], 0)
    else:
        draw_btn(draw, [(OK_X0, ok_y0), (OK_X1, ok_y1)], outline=0)
        draw_centered(draw, cx, ok_cy, ok_label, f['ok'], 0)

    if sec_label:
        sec_y0 = NT_SEC_Y0 if no_title else SEC_Y0
        sec_y1 = NT_SEC_Y1 if no_title else SEC_Y1
        sec_cy = (sec_y0 + sec_y1) // 2
        draw_btn_bar(draw, [(OK_X0, sec_y0), (OK_X1, sec_y1)])
        draw_centered(draw, cx, sec_cy, sec_label, f['btn'], 0)


# ── Touch helpers ─────────────────────────────────────────────────────────────

def to_landscape(tx: int, ty: int) -> tuple[int, int]:
    return (249 - ty, tx)


def hit_ok(lx: int, ly: int, split: bool = False, no_title: bool = False) -> bool:
    y0 = NT_OK_Y0       if no_title else OK_Y0
    y1 = (NT_OK_Y1_SPLIT if no_title else OK_Y1_SPLIT) if split \
         else (NT_OK_Y1  if no_title else OK_Y1)
    return OK_X0 <= lx <= OK_X1 and y0 <= ly <= y1


def hit_sec(lx: int, ly: int, no_title: bool = False) -> bool:
    y0 = NT_SEC_Y0 if no_title else SEC_Y0
    y1 = NT_SEC_Y1 if no_title else SEC_Y1
    return OK_X0 <= lx <= OK_X1 and y0 <= ly <= y1


# ── SAN glyph substitution ────────────────────────────────────────────────────
_SAN_TO_GLYPH = {'N': '♞', 'B': '♝', 'R': '♜', 'Q': '♛', 'K': '♚'}


def san_with_glyph(san: str) -> str:
    if san and san[0] in _SAN_TO_GLYPH:
        san = _SAN_TO_GLYPH[san[0]] + san[1:]
    eq = san.find('=')
    if eq != -1 and eq + 1 < len(san) and san[eq + 1] in _SAN_TO_GLYPH:
        san = san[:eq + 1] + _SAN_TO_GLYPH[san[eq + 1]] + san[eq + 2:]
    return san


# ── Button ────────────────────────────────────────────────────────────────────

class Button:
    """Renderable, hittable button with one of three visual styles.

    Styles
    ------
    OUTLINE  – rounded outline only; black text (inactive option)
    FILLED   – black fill; white text (selected option)
    BAR      – outline + solid black bar at bottom; black text (action button)
    """

    OUTLINE = 'outline'
    FILLED  = 'filled'
    BAR     = 'bar'

    def __init__(self, rect: tuple[int, int, int, int],
                 label: str = '',
                 style: str = OUTLINE,
                 text_offset: tuple[int, int] = (0, 0)) -> None:
        self.rect        = rect   # (x0, y0, x1, y1)
        self.label       = label
        self.style       = style
        self.text_offset = text_offset  # (dx, dy) applied to the text centre

    def draw(self, draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont) -> None:
        x0, y0, x1, y1 = self.rect
        coords = [(x0, y0), (x1, y1)]
        dx, dy = self.text_offset
        cx, cy = (x0 + x1) // 2 + dx, (y0 + y1) // 2 + dy
        if self.style == Button.FILLED:
            draw_btn(draw, coords, fill=0)
            draw_centered(draw, cx, cy, self.label, font, 255)
        elif self.style == Button.BAR:
            draw_btn_bar(draw, coords)
            draw_centered(draw, cx, cy, self.label, font, 0)
        else:  # OUTLINE
            draw_btn(draw, coords, outline=0)
            draw_centered(draw, cx, cy, self.label, font, 0)

    def hit(self, lx: int, ly: int) -> bool:
        x0, y0, x1, y1 = self.rect
        return x0 <= lx <= x1 and y0 <= ly <= y1


# ── Screen base class ─────────────────────────────────────────────────────────

class Screen:
    """Base class for ZeroFish screen modules.

    Subclasses set ``name`` and implement ``build()`` / ``hit()``.
    The ``fonts`` property returns a cached font dict for ``self.name``.
    ``new_image()`` creates a correctly-sized PIL image plus its draw handle.
    """

    name: str = 'default'

    @property
    def fonts(self) -> dict:
        return load_fonts(self.name)

    def new_image(self, portrait: bool = False) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        if portrait:
            img = Image.new('1', (config.SCORE_W, config.SCORE_H), 255)
        else:
            img = Image.new('1', (W, H), 255)
        return img, ImageDraw.Draw(img)

    def build(self, **kw) -> Image.Image:
        raise NotImplementedError(f'{type(self).__name__}.build()')

    def hit(self, lx: int, ly: int, **kw) -> str | None:
        """Return an action-name string if (lx, ly) hits a button, else None."""
        raise NotImplementedError(f'{type(self).__name__}.hit()')
