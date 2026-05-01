import os

VERSION        = '0.2'
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
SIZE_BTN_OK      = 18   # OK / Back / confirm button (bold)
SIZE_BTN         = 18   # grid buttons: numbers, files, ranks, menu items (bold)
SIZE_BTN_DIFF    = 16   # difficulty level grid buttons (bold) — 2pt smaller than BTN
SIZE_MOVE        = 48   # large SAN move display (bold)
SIZE_MOVE_PIECE  = 54   # piece glyph in SF move screen (Merida) — larger than SIZE_MOVE
SIZE_RESULT      = 28   # game-over result headline (bold)
SIZE_LABEL       = 12   # secondary labels, small annotations (regular)
SIZE_TEXT        = 12   # score sheet, plain body text (regular)
SIZE_TEXT_LG     = 18   # time screen, larger prose (regular)
SIZE_PIECE       = 30   # piece glyphs in move-input buttons (piece font)
SIZE_PROMO       = 36   # piece glyphs in promotion chooser (piece font)
SIZE_BOARD_PIECE = 14   # piece glyphs on the board view (piece font)

# ── Board view ────────────────────────────────────────────────────────────────
BOARD_SQ         = 15  # square size in px
BOARD_OFFSET_X   = 0
BOARD_OFFSET_Y   = 0
BOARD_PIECE_OFFSET_X = 0
BOARD_PIECE_OFFSET_Y = 1

# ── Difficulty levels ─────────────────────────────────────────────────────────
# 15 levels in a 3×5 grid.  Labels show approximate ELO; skill/time/hash are
# tuned so each step feels meaningfully stronger.
#
# Level | Label | SF Skill | Think (s) | Hash (MB)
#   1     1k       0          1.0         16
#   2     1k2      2          1.0         16
#   3     1k4      4          1.0         16
#   4     1k5      5          1.5         16
#   5     1k6      6          2.0         16
#   6     1k7      7          3.0         16
#   7     1k8      8          3.0         32
#   8     1k9      9          5.0         32
#   9     2k      10          5.0         32
#  10     2k1     11         10.0         32
#  11     2k2     12         10.0         64
#  12     2k4     14         15.0         64
#  13     2k6     16         20.0         64
#  14     2k8     18         30.0        128
#  15     Max     20         60.0        128
DIFF_LABELS = {
    1: '1k',  2: '1k2', 3: '1k4', 4: '1k5', 5: '1k6',
    6: '1k7', 7: '1k8', 8: '1k9', 9: '2k',  10: '2k1',
    11: '2k2', 12: '2k4', 13: '2k6', 14: '2k8', 15: '∞',
}
DIFF_SKILL_LEVELS = {
    1: 0,  2: 2,  3: 4,  4: 5,  5: 6,
    6: 7,  7: 8,  8: 9,  9: 10, 10: 11,
    11: 12, 12: 14, 13: 16, 14: 18, 15: 20,
}
DIFF_THINK_SECS = {
    1: 1.0, 2: 1.0,  3: 1.0,  4: 1.5,  5: 2.0,
    6: 3.0, 7: 3.0,  8: 5.0,  9: 5.0,  10: 10.0,
    11: 10.0, 12: 15.0, 13: 20.0, 14: 30.0, 15: 60.0,
}
DIFF_HASH_MB = {
    1: 16,  2: 16,  3: 16,  4: 16,  5: 16,
    6: 16,  7: 32,  8: 32,  9: 32,  10: 32,
    11: 64, 12: 64, 13: 64, 14: 128, 15: 128,
}

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
    'default':      'noto',   # fallback for any unlisted screen
    'splash':       'noto',
    'difficulty':   'noto',
    'color':        'noto',
    'thinking':     'noto',
    'sf_move':      'noto',          # large move glyph benefits from regular-width Noto
    'game_over':    'noto',
    'player_move':  'noto',
    'promotion':    'noto',
    'disambig':     'noto',
    'ingame_menu':  'noto',
    'scoresheet':   'noto',   # condensed fits more moves per line
    'time':         'noto',
    'board':        'noto',
}

# ── Piece / chess-glyph font ──────────────────────────────────────────────────
# Separate from the family system because glyph coverage matters more than style.
# Chess Merida Unicode is tried first; it places traditional figurines at the
# Unicode chess code points (U+2654–U+265F) used throughout the UI.
# Install manually: copy Chess_Merida_Unicode.ttf to one of the paths below.
# Falls back to DejaVu Sans (confirmed to render ♟♞♝♜♛♚ correctly).
FONT_PIECE_PATHS = [
    # Chess Merida Unicode — traditional figurine look; manual install required
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'Chess_Merida_Unicode.ttf'),
    '/usr/local/share/fonts/Chess_Merida_Unicode.ttf',
    '/usr/share/fonts/truetype/chess-merida/Chess_Merida_Unicode.ttf',
    # DejaVu Sans — confirmed fallback
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSerif.ttf',
]
