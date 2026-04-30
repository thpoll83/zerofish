import os

VERSION        = '0.1'
STOCKFISH_PATH = '/usr/games/stockfish'

# ── Display ───────────────────────────────────────────────────────────────────
DISPLAY_W = 250
DISPLAY_H = 122

# ── Chrome layout ─────────────────────────────────────────────────────────────
TITLE_H      = 21
VSEP_X       = 192
OK_GAP_X     = 3   # separator → OK button left edge
OK_GAP_RIGHT = 3   # display right edge → OK button right edge
OK_GAP_Y     = 6   # content area top/bottom → OK button edges

# ── Score sheet (portrait) ────────────────────────────────────────────────────
SCORE_W      = 122
SCORE_H      = 250
SCORE_BACK_H = 22

# ── Game state persistence ────────────────────────────────────────────────────
SAVE_PATH = os.path.expanduser('~/.zerofish_save.json')

# ── Idle sleep ────────────────────────────────────────────────────────────────
IDLE_SLEEP_SECS = 120  # seconds of no touch before display sleeps; 0 = disabled

# ── Font sizes ────────────────────────────────────────────────────────────────
SIZE_HEADLINE    = 14   # title bar label (bold)
SIZE_VERSION     = 12   # version tag in title bar (regular)
SIZE_BTN_OK      = 16   # OK / Back / confirm button (bold)
SIZE_BTN         = 15   # grid buttons: numbers, files, ranks, menu items (bold)
SIZE_MOVE        = 48   # large SAN move display (bold)
SIZE_RESULT      = 28   # game-over result headline (bold)
SIZE_LABEL       = 11   # secondary labels, small annotations (regular)
SIZE_TEXT        = 11   # score sheet, plain body text (regular)
SIZE_TEXT_LG     = 13   # time screen, larger prose (regular)
SIZE_PIECE       = 28   # piece glyphs in move-input buttons (piece font)
SIZE_PROMO       = 36   # piece glyphs in promotion chooser (piece font)
SIZE_BOARD_PIECE = 14   # piece glyphs on the board view (piece font)

# ── Board view ────────────────────────────────────────────────────────────────
BOARD_SQ         = 15  # square size in px
BOARD_OFFSET_X   = 0
BOARD_OFFSET_Y   = 0
BOARD_PIECE_OFFSET_X = 0
BOARD_PIECE_OFFSET_Y = 1

# ── Font families ─────────────────────────────────────────────────────────────
# Each family maps to bold and regular (non-piece) font search paths.
# First existing path on the system wins.
#
# Installed by rpi_setup.sh:
#   fonts-noto-core     → /usr/share/fonts/truetype/noto/NotoSans-{Bold,Regular}.ttf
#   fonts-dejavu-extra  → /usr/share/fonts/truetype/dejavu/DejaVuSansCondensed{-Bold,}.ttf
#   fonts-dejavu-core   → /usr/share/fonts/truetype/dejavu/DejaVuSans{-Bold,}.ttf
#
FONT_FAMILIES = {
    # Noto Sans — clean, modern; no condensed variant in fonts-noto-core
    'noto': {
        'bold': [
            '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        ],
        'reg': [
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        ],
    },
    # DejaVu Sans Condensed — space-efficient; ideal for tight 250×122 layouts
    'dejavu_cond': {
        'bold': [
            '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf',
            '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        ],
        'reg': [
            '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf',
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        ],
    },
    # DejaVu Sans — regular width variant
    'dejavu': {
        'bold': ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'],
        'reg':  ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'],
    },
}

# ── Per-screen font family ────────────────────────────────────────────────────
# Maps screen name → key in FONT_FAMILIES above.
# Changing a value here switches the font for that entire screen.
#
#   Screen            bold/reg used for
#   ─────────────     ─────────────────────────────────────────────────────────
#   splash            title text block
#   difficulty        number buttons, title bar
#   color             White/Black/Random buttons, title bar
#   thinking          "Thinking…" label
#   sf_move           large SAN glyph (SIZE_MOVE), move-number label
#   game_over         headline ("You win!"), reason line
#   player_move       piece/file/rank grid buttons, invalid-count title
#   promotion         promotion piece chooser buttons
#   disambig          disambiguation buttons
#   ingame_menu       Resign/Board/Score/Time buttons
#   scoresheet        move list body (portrait)
#   time              elapsed-time prose
#   board             board coordinate labels
#
SCREEN_FONT_FAMILY = {
    'default':      'dejavu_cond',   # fallback for any unlisted screen
    'splash':       'noto',
    'difficulty':   'dejavu_cond',
    'color':        'dejavu_cond',
    'thinking':     'noto',
    'sf_move':      'noto',          # large move glyph benefits from regular-width Noto
    'game_over':    'noto',
    'player_move':  'dejavu_cond',
    'promotion':    'noto',
    'disambig':     'dejavu_cond',
    'ingame_menu':  'dejavu_cond',
    'scoresheet':   'dejavu_cond',   # condensed fits more moves per line
    'time':         'noto',
    'board':        'dejavu_cond',
}

# ── Piece / chess-glyph font ──────────────────────────────────────────────────
# Separate from the family system because glyph coverage matters more than style.
# DejaVu Sans confirmed to render ♟♞♝♜♛♚ correctly.
# Used for: piece buttons (SIZE_PIECE), large move glyph (SIZE_MOVE),
#           promotion chooser (SIZE_PROMO), board view (SIZE_BOARD_PIECE).
FONT_PIECE_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSerif.ttf',
]
