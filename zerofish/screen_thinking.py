from PIL import Image, ImageDraw
import ui


def build_thinking_screen(move_label='') -> Image.Image:
    img  = Image.new('1', (ui.W, ui.H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts('thinking')
    ui.draw_chrome(draw, f, move_label, no_title=True)
    ui.draw_centered(draw, ui.VSEP_X // 2, ui.H // 2 + 2, 'mhh..', f['move'], 0)
    return img
