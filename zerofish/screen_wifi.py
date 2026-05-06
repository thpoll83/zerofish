"""WiFi setup screen.

Custom left/right split at x=_WIFI_SEP (100px) — wider right panel needed
for the 5x4 on-screen keyboard.

Layout (keyboard mode, WPA network selected):
  Left  (0..99):   "Wifi Setup" headline + network list
  Right (102..249): password field, 4 rows of char keys (5 cols), Back

Layout (list mode):
  Left  (0..99):   as above
  Right (102..249): status text + action buttons (Connect / Forget) + Back

Network scanning uses nmcli; returns [] on failure.
"""

import subprocess
import textwrap
import ui

# ── Custom geometry ───────────────────────────────────────────────────────────
_WIFI_SEP = 100           # vertical separator x-coordinate
_RP_X0    = _WIFI_SEP + 2  # right-panel content left edge  (= 102)
_RP_W     = ui.W - _RP_X0  # right-panel content width      (= 148)

# Network list (left panel)
_LIST_LH    = 12          # network list row height
_LIST_HDR_H = 15          # "Wifi Setup" header height
_LIST_Y0    = ui.TITLE_H + _LIST_HDR_H + 2  # list rows start y

# Password field (keyboard mode)
_PW_Y0 = ui.TITLE_H + 2
_PW_Y1 = _PW_Y0 + 14     # = 37
_PW_X0 = _RP_X0
_PW_X1 = ui.W - 2

# On-screen keyboard grid: 5 cols x 4 rows (3 char rows + 1 special row)
_KBD_COLS  = 5
_KBD_ROWS  = 4
_KBD_BTN_W = (_RP_W - (_KBD_COLS - 1)) // _KBD_COLS  # = (148-4)//5 = 28
_KBD_BTN_H = 16
_KBD_GAP   = 1
_KBD_Y0    = _PW_Y1 + 2  # = 39
_KBD_COL_X = [_RP_X0 + j * (_KBD_BTN_W + _KBD_GAP) for j in range(_KBD_COLS)]
_KBD_ROW_Y = [_KBD_Y0 + i * (_KBD_BTN_H + _KBD_GAP) for i in range(_KBD_ROWS)]

# Special keys in row 3 (Del, Space, prev page, next page, Connect)
_KBD_SPECIAL = ['Del', 'Sp', '<', '>', 'OK']

# Back button (keyboard mode, below the 4th keyboard row)
_KBACK_Y0 = _KBD_ROW_Y[-1] + _KBD_BTN_H + 2  # = 108
_KBACK_Y1 = ui.H - 2                           # = 120

# Right panel buttons (list mode)
_RP_BTN_X0  = _RP_X0 + 2
_RP_BTN_X1  = ui.W - 3
_RP_BTN_H   = 22
_RP_STATUS_Y = ui.TITLE_H + 7
_RP_BTN1_Y0 = ui.TITLE_H + 20
_RP_BTN1_Y1 = _RP_BTN1_Y0 + _RP_BTN_H
_RP_BTN2_Y0 = _RP_BTN1_Y1 + 4
_RP_BTN2_Y1 = _RP_BTN2_Y0 + _RP_BTN_H
_RP_BACK_Y0 = ui.H - 14
_RP_BACK_Y1 = ui.H - 2

# Keyboard character pages: 3 char rows x 5 cols = 15 chars per page.
_KBD_PAGES = [
    list('abcdefghijklmno'),      # page 0: a-o
    list('pqrstuvwxyzABCD'),      # page 1: p-z + A-D
    list('EFGHIJKLMNOPQRS'),      # page 2: E-S
    list('TUVWXYZ01234567'),      # page 3: T-Z + 0-7
    list('89!@#$%^&*()-_='),      # page 4: 8-9 + specials
    list("+[]{}|;:'\",.<>/"),     # page 5: more specials
]
_KBD_NUM_PAGES = len(_KBD_PAGES)

_SSID_MAX_CHARS = 12


# ── WiFi OS helpers ───────────────────────────────────────────────────────────

def _run(args, timeout=15):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, '', str(e)


def scan_networks():
    """Return sorted list of visible WiFi networks."""
    code, out, _ = _run(
        ['nmcli', '-t', '-f', 'IN-USE,SSID,SIGNAL,SECURITY',
         'device', 'wifi', 'list', '--rescan', 'yes'],
        timeout=20,
    )
    if code != 0:
        return []
    nets = []
    seen = set()
    for line in out.splitlines():
        parts = line.split(':')
        if len(parts) < 4:
            continue
        in_use = parts[0] == '*'
        ssid   = parts[1]
        if not ssid:
            continue
        try:
            signal = int(parts[2])
        except ValueError:
            signal = 0
        security     = ':'.join(parts[3:]).strip()
        has_password = bool(security) and security != '--'
        if ssid not in seen:
            seen.add(ssid)
            nets.append({'ssid': ssid, 'signal': signal,
                         'in_use': in_use, 'has_password': has_password})
    nets.sort(key=lambda n: (not n['in_use'], -n['signal']))
    return nets


def connect_open(ssid):
    """Connect to an open network. Returns (success, message)."""
    code, out, err = _run(['nmcli', 'device', 'wifi', 'connect', ssid], timeout=30)
    if code == 0:
        return True, out.strip() or 'Connected'
    return False, (err or out or 'Connection failed').strip()


def connect_wpa(ssid, password):
    """Connect to a WPA-protected network. Returns (success, message)."""
    code, out, err = _run(
        ['nmcli', 'device', 'wifi', 'connect', ssid, 'password', password],
        timeout=30,
    )
    if code == 0:
        return True, out.strip() or 'Connected'
    return False, (err or out or 'Connection failed').strip()


def forget_network(ssid):
    """Delete saved connection profile for ssid."""
    _run(['nmcli', 'connection', 'delete', ssid], timeout=10)


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _signal_bars(signal):
    if signal >= 75: return '||||'
    if signal >= 50: return '||| '
    if signal >= 25: return '||  '
    if signal >  0:  return '|   '
    return '    '


def _draw_separator(draw):
    draw.line([(_WIFI_SEP, ui.TITLE_H), (_WIFI_SEP, ui.H - 1)], fill=0)


def _draw_network_list(draw, f, networks, selected_idx, scroll_off=0):
    hf = f['small']
    draw.text((2, ui.TITLE_H + 2), 'Wifi Setup', font=hf, fill=0)
    draw.line([(0, _LIST_Y0 - 1), (_WIFI_SEP - 1, _LIST_Y0 - 1)], fill=0)

    visible_rows = (ui.H - _LIST_Y0) // _LIST_LH
    for slot in range(visible_rows):
        idx = scroll_off + slot
        if idx >= len(networks):
            break
        net      = networks[idx]
        y0       = _LIST_Y0 + slot * _LIST_LH
        bars     = _signal_bars(net['signal'])
        ssid     = net['ssid'][:_SSID_MAX_CHARS]
        label    = bars + ' ' + ssid
        selected = (idx == selected_idx)
        if selected:
            draw.rectangle([(0, y0), (_WIFI_SEP - 1, y0 + _LIST_LH - 1)], fill=0)
            draw.text((2, y0), label, font=hf, fill=255)
        else:
            draw.text((2, y0), label, font=hf, fill=0)


def _draw_rp_btn(draw, f, y0, y1, label, active=True):
    cx     = (_RP_BTN_X0 + _RP_BTN_X1) // 2
    cy     = (y0 + y1) // 2
    coords = [(_RP_BTN_X0, y0), (_RP_BTN_X1, y1)]
    if active:
        ui.draw_btn_bar(draw, coords)
    else:
        ui.draw_btn(draw, coords, outline=0)
    ui.draw_centered(draw, cx, cy, label, f['btn_diff'], 0)


def _rp_hit(lx, ly, y0, y1):
    return _RP_BTN_X0 <= lx <= _RP_BTN_X1 and y0 <= ly <= y1


# ── Screen class ──────────────────────────────────────────────────────────────

class WifiScreen(ui.Screen):
    name = 'wifi'

    def build(self, networks, selected_idx, passwd, kbd_page, scroll_off=0):
        img, draw = self.new_image()
        f = self.fonts

        draw.rectangle([(0, 0), (ui.W - 1, ui.TITLE_H - 1)], fill=0)
        draw.text((4, 3), 'ZeroFish: Wifi', font=f['title'], fill=255)

        _draw_separator(draw)
        _draw_network_list(draw, f, networks, selected_idx, scroll_off)

        net = (networks[selected_idx]
               if selected_idx is not None and selected_idx < len(networks)
               else None)

        if net is not None and net['has_password'] and not net['in_use']:
            self._draw_keyboard_panel(draw, f, passwd, kbd_page)
        else:
            self._draw_list_panel(draw, f, net)

        return img

    def _draw_keyboard_panel(self, draw, f, passwd, kbd_page):
        hf = f['small']

        # Password field
        draw.rectangle([(_PW_X0, _PW_Y0), (_PW_X1, _PW_Y1)], outline=0)
        visible_pw = passwd[-16:] if len(passwd) > 16 else passwd
        draw.text((_PW_X0 + 2, _PW_Y0 + 1), visible_pw + '_', font=hf, fill=0)

        # Char rows (rows 0–2)
        chars = _KBD_PAGES[kbd_page % _KBD_NUM_PAGES]
        for row in range(_KBD_ROWS - 1):
            for col in range(_KBD_COLS):
                char_idx = row * _KBD_COLS + col
                x0 = _KBD_COL_X[col]
                y0 = _KBD_ROW_Y[row]
                x1 = x0 + _KBD_BTN_W - 1
                y1 = y0 + _KBD_BTN_H - 1
                ch = chars[char_idx] if char_idx < len(chars) else ''
                if ch:
                    ui.draw_btn(draw, [(x0, y0), (x1, y1)], outline=0)
                    ui.draw_centered(draw, (x0 + x1) // 2, (y0 + y1) // 2,
                                     ch, f['small'], 0)

        # Special row (row 3)
        for col, label in enumerate(_KBD_SPECIAL):
            x0 = _KBD_COL_X[col]
            y0 = _KBD_ROW_Y[3]
            x1 = x0 + _KBD_BTN_W - 1
            y1 = y0 + _KBD_BTN_H - 1
            ui.draw_btn_bar(draw, [(x0, y0), (x1, y1)])
            ui.draw_centered(draw, (x0 + x1) // 2, (y0 + y1) // 2,
                             label, f['small'], 0)

        # Back button below keyboard
        cx = (_KBD_COL_X[0] + _KBD_COL_X[-1] + _KBD_BTN_W - 1) // 2
        ui.draw_btn_bar(draw, [(_RP_X0, _KBACK_Y0), (ui.W - 2, _KBACK_Y1)])
        ui.draw_centered(draw, cx, (_KBACK_Y0 + _KBACK_Y1) // 2,
                         'Back', f['btn_diff'], 0)

    def _draw_list_panel(self, draw, f, net):
        hf = f['small']
        if net is not None:
            if net['in_use']:
                draw.text((_RP_BTN_X0, _RP_STATUS_Y), 'Connected', font=hf, fill=0)
                _draw_rp_btn(draw, f, _RP_BTN1_Y0, _RP_BTN1_Y1, 'Forget')
            else:
                draw.text((_RP_BTN_X0, _RP_STATUS_Y), 'Open', font=hf, fill=0)
                _draw_rp_btn(draw, f, _RP_BTN1_Y0, _RP_BTN1_Y1, 'Connect')
        _draw_rp_btn(draw, f, _RP_BACK_Y0, _RP_BACK_Y1, 'Back')

    def hit(self, lx, ly, networks, selected_idx, kbd_page, scroll_off=0):
        net = (networks[selected_idx]
               if selected_idx is not None and selected_idx < len(networks)
               else None)
        keyboard_mode = (net is not None and net['has_password'] and not net['in_use'])

        if lx < _WIFI_SEP:
            if ly >= _LIST_Y0:
                slot = (ly - _LIST_Y0) // _LIST_LH
                idx  = scroll_off + slot
                if idx < len(networks):
                    return 'select:' + str(idx)
            return None

        if keyboard_mode:
            return self._hit_keyboard(lx, ly, kbd_page)
        return self._hit_list_panel(lx, ly, net)

    def _hit_keyboard(self, lx, ly, kbd_page):
        if _RP_X0 <= lx <= ui.W - 2 and _KBACK_Y0 <= ly <= _KBACK_Y1:
            return 'back_kbd'

        for row in range(_KBD_ROWS - 1):
            for col in range(_KBD_COLS):
                x0 = _KBD_COL_X[col]
                y0 = _KBD_ROW_Y[row]
                if (x0 <= lx <= x0 + _KBD_BTN_W - 1
                        and y0 <= ly <= y0 + _KBD_BTN_H - 1):
                    chars    = _KBD_PAGES[kbd_page % _KBD_NUM_PAGES]
                    char_idx = row * _KBD_COLS + col
                    if char_idx < len(chars):
                        return 'char:' + chars[char_idx]
                    return None

        for col, key in enumerate(_KBD_SPECIAL):
            x0 = _KBD_COL_X[col]
            y0 = _KBD_ROW_Y[3]
            if (x0 <= lx <= x0 + _KBD_BTN_W - 1
                    and y0 <= ly <= y0 + _KBD_BTN_H - 1):
                if key == 'Del': return 'del'
                if key == 'Sp':  return 'space'
                if key == '<':   return 'prev_page'
                if key == '>':   return 'next_page'
                if key == 'OK':  return 'connect_wpa'
        return None

    def _hit_list_panel(self, lx, ly, net):
        if _rp_hit(lx, ly, _RP_BACK_Y0, _RP_BACK_Y1):
            return 'back'
        if net is not None:
            if _rp_hit(lx, ly, _RP_BTN1_Y0, _RP_BTN1_Y1):
                return 'forget' if net['in_use'] else 'connect_open'
        return None


_screen = WifiScreen()


def build_wifi_screen(networks, selected_idx, passwd, kbd_page, scroll_off=0):
    return _screen.build(networks, selected_idx, passwd, kbd_page, scroll_off)


def hit_wifi(lx, ly, networks, selected_idx, kbd_page, scroll_off=0):
    return _screen.hit(lx, ly, networks, selected_idx, kbd_page, scroll_off)


# ── WiFi result screen ────────────────────────────────────────────────────────

class WifiResultScreen(ui.Screen):
    name = 'wifi_result'

    def build(self, ssid, message):
        img, draw = self.new_image()
        f = self.fonts
        ui.draw_chrome(draw, f, 'Wifi', ok_active=True, ok_label='OK')

        hf = f['small']
        x  = 4
        y  = ui.TITLE_H + 6
        lh = 13

        draw.text((x, y), '"' + ssid + '"', font=hf, fill=0)
        y += lh + 2

        chars_per_line = max(1, (ui.VSEP_X - 8) // 7)
        for line in textwrap.wrap(message, width=chars_per_line):
            draw.text((x, y), line, font=hf, fill=0)
            y += lh
            if y > ui.H - lh:
                break

        return img

    def hit(self, lx, ly):
        return 'ok' if ui.hit_ok(lx, ly) else None


_result_screen = WifiResultScreen()


def build_wifi_result_screen(ssid, message):
    return _result_screen.build(ssid, message)


def hit_wifi_result(lx, ly):
    return _result_screen.hit(lx, ly)
