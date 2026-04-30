import os

_REPO     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FONT_DIR = os.path.join(_REPO, 'Touch_e-Paper_Code', 'python', 'pic')

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

# ── Font paths (first existing path wins) ─────────────────────────────────────
FONT_BOLD_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    os.path.join(_FONT_DIR, 'Roboto-Bold.ttf'),
]
FONT_REG_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    os.path.join(_FONT_DIR, 'Roboto-Regular.ttf'),
]
FONT_PLAIN_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    os.path.join(_FONT_DIR, 'Roboto-Regular.ttf'),
]
FONT_PIECE_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSerif.ttf',
]

# ── Font sizes ────────────────────────────────────────────────────────────────
SIZE_HEADLINE    = 15   # title bar label (bold)
SIZE_VERSION     = 10   # version tag in title bar (regular)
SIZE_BTN_OK      = 16   # OK / Back / confirm button (bold)
SIZE_BTN         = 14   # grid buttons: numbers, files, ranks, menu items (bold)
SIZE_MOVE        = 42   # large SAN move display (bold)
SIZE_RESULT      = 28   # game-over result headline (bold)
SIZE_LABEL       = 11   # secondary labels, small annotations (regular)
SIZE_TEXT        = 11   # score sheet, plain body text (plain regular)
SIZE_TEXT_LG     = 13   # time screen, larger prose (plain regular)
SIZE_PIECE       = 26   # piece glyphs in move-input buttons (piece font)
SIZE_PROMO       = 36   # piece glyphs in promotion chooser (piece font)
SIZE_BOARD_PIECE = 14   # piece glyphs on the board view (piece font)

# ── Board view ────────────────────────────────────────────────────────────────
BOARD_SQ         = 15  # square size in px
BOARD_OFFSET_X   = 0   # extra X offset from auto-centred board position
BOARD_OFFSET_Y   = 0   # extra Y offset from auto-centred board position
BOARD_PIECE_OFFSET_X = 0  # horizontal nudge of piece glyph center within its square
BOARD_PIECE_OFFSET_Y = 0  # vertical nudge of piece glyph center within its square
