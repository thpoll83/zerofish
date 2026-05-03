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


class ThinkingScreen(ui.Screen):
    name = 'thinking'

    def build(self, move_label='') -> Image.Image:
        img, draw = self.new_image()
        f = self.fonts
        ui.draw_chrome(draw, f, move_label, no_title=True)
        ui.draw_centered(draw, ui.VSEP_X // 2, ui.H // 2 + 2,
                         random.choice(_THINK_SOUNDS), f['move'], 0)
        return img

    def hit(self, lx: int, ly: int, **kw) -> str | None:
        return None  # no touch interaction while thinking


_screen = ThinkingScreen()


def build_thinking_screen(move_label='') -> Image.Image:
    return _screen.build(move_label=move_label)
