import random
from PIL import Image, ImageDraw
import ui

_THINK_SOUNDS = [
    'Hh..', 'Hm..', 'Hmm?', 'Ooh..', 'Ah...',
    'Aha!', 'Umm..', 'Uh...', 'Oh!', 'Ohh...',
    'Mmm..', 'Whoa..', 'Heh...', 'Oof...', 'Phew.',
    'Now...', 'Yes...', 'Aha..', 'Hmm..', 'Uhh..',
    'Wait...', 'Zzz..', 'Um...', 'Ah ha!', 'Hmh..',
    'Right..', 'Hmph..', 'Huh..', 'Yeah..', 'Nah...',
    'Yep..', 'Bah..', 'Right..', 'So...', 'Me..',
    'Ugh..', 'Heh..', 'Go go..', 'Hmm ok', "Let's..",
    'I see.', 'And...', 'Then...', 'Next..', 'Jup...',
    'Hmm!!', 'Erm...', 'Err...', 'Well..', 'Ok...',
]


def build_thinking_screen(move_label='') -> Image.Image:
    img  = Image.new('1', (ui.W, ui.H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts('thinking')
    ui.draw_chrome(draw, f, move_label, no_title=True)
    ui.draw_centered(draw, ui.VSEP_X // 2, ui.H // 2 + 2,
                     random.choice(_THINK_SOUNDS), f['move'], 0)
    return img
