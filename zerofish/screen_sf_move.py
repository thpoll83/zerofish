from PIL import Image, ImageDraw
import ui


def build_sf_move_screen(san, move_label) -> Image.Image:
    img  = Image.new('1', (ui.W, ui.H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts()
    ui.draw_chrome(draw, f, move_label, ok_active=True)
    cx = ui.VSEP_X // 2
    ui.draw_centered(draw, cx, (ui.TITLE_H + ui.H) // 2 - 4,
                     ui.san_with_glyph(san), f['move_piece'], 0)
    return img
