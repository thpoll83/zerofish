from PIL import Image, ImageDraw
import ui

_YES_W  = 90
_YES_H  = 52
_YES_X0 = (ui.VSEP_X - _YES_W) // 2
_YES_X1 = _YES_X0 + _YES_W
_YES_Y0 = ui.TITLE_H + 30
_YES_Y1 = _YES_Y0 + _YES_H
_TEXT_CY = ui.TITLE_H + 16


def build_resign_confirm_screen() -> Image.Image:
    img  = Image.new('1', (ui.W, ui.H), 255)
    draw = ImageDraw.Draw(img)
    f    = ui.load_fonts('ingame_menu')
    ui.draw_chrome(draw, f, 'Resign?', ok_active=False, ok_label='No')
    ui.draw_centered(draw, ui.VSEP_X // 2, _TEXT_CY, 'Are you sure?', f['small'], 0)
    cx = (_YES_X0 + _YES_X1) // 2
    cy = (_YES_Y0 + _YES_Y1) // 2
    ui.draw_btn(draw, [(_YES_X0, _YES_Y0), (_YES_X1, _YES_Y1)], fill=0)
    ui.draw_centered(draw, cx, cy, 'Yes', f['btn'], 255)
    return img


def hit_resign_yes(lx: int, ly: int) -> bool:
    return _YES_X0 <= lx <= _YES_X1 and _YES_Y0 <= ly <= _YES_Y1
