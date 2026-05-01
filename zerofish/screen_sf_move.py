from PIL import Image, ImageDraw
import ui

_PIECE_GLYPHS = set('♔♕♖♗♘♙♚♛♜♝♞♟')


def _draw_move(draw, san_glyph, f, cx, cy):
    """Render SAN: leading piece glyph in Merida (sf_piece), rest in Noto (move)."""
    if san_glyph and san_glyph[0] in _PIECE_GLYPHS:
        glyph, rest = san_glyph[0], san_glyph[1:]
        g_bb = draw.textbbox((0, 0), glyph, font=f['sf_piece'])
        r_bb = draw.textbbox((0, 0), rest,  font=f['move'])
        glyph_w = g_bb[2] - g_bb[0]
        rest_w  = r_bb[2] - r_bb[0]
        x0 = cx - (glyph_w + rest_w) // 2
        # Align both parts to the same baseline (larger font sets it)
        ascent_g = f['sf_piece'].getmetrics()[0]
        ascent_m = f['move'].getmetrics()[0]
        lh_g     = sum(f['sf_piece'].getmetrics())
        baseline = cy - lh_g // 2 + ascent_g
        draw.text((x0 - g_bb[0],         baseline - ascent_g), glyph, font=f['sf_piece'], fill=0)
        draw.text((x0 + glyph_w - r_bb[0], baseline - ascent_m), rest,  font=f['move'],     fill=0)
    else:
        ui.draw_centered(draw, cx, cy, san_glyph, f['move'], 0)


def build_sf_move_screen(san, move_label) -> Image.Image:
    img  = Image.new('1', (ui.W, ui.H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts('sf_move')
    ui.draw_chrome(draw, f, move_label, ok_active=True, no_title=True)
    _draw_move(draw, ui.san_with_glyph(san), f, ui.VSEP_X // 2, ui.H // 2 + 2)
    return img
