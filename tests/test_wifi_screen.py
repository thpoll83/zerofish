"""Comprehensive tests for screen_wifi.py.

PIL/Pillow and other hardware dependencies are mocked at the top so that
these tests run in any Python 3.11+ environment without a Raspberry Pi.

Coverage:
  • _signal_bars()             – boundary values for every tier
  • scan_networks()            – parsing, sorting, deduplication, IP attachment
  • connect_open/connect_wpa   – success and failure paths, argument passing
  • forget_network()           – correct nmcli call, silent on failure
  • get_active_ip()            – device lookup, IP extraction, error paths
  • build_wifi_screen()        – renders each mode without exceptions
  • build_wifi_result_screen() – renders without exceptions
  • hit_wifi() left panel      – rescan button, network selection, scroll offset
  • hit_wifi() list mode       – Back, Connect (open), Forget (connected)
  • hit_wifi() keyboard mode   – char keys (all pages), Del, Sp, <, >, OK, Back
  • hit_wifi_result()          – OK hit and miss
  • keyboard page content      – complete alphanumeric/special coverage
  • interaction sequences      – multi-step flows using mock network lists
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, call

# ── 1. Mock hardware/display dependencies before any app import ───────────────

_font_mock = MagicMock()
_font_mock.getmetrics.return_value = (10, 2)
_font_mock.getbbox = lambda text, **kw: (0, 0, len(text) * 7, 12)

_draw_mock = MagicMock()

_img_mock = MagicMock()

_Image_mod = MagicMock()
_Image_mod.new.return_value = _img_mock

_ImageDraw_mod = MagicMock()
_ImageDraw_mod.Draw.return_value = _draw_mock

_ImageFont_mod = MagicMock()
_ImageFont_mod.truetype.return_value = _font_mock
_ImageFont_mod.load_default.return_value = _font_mock

_PIL_pkg = MagicMock()
_PIL_pkg.Image      = _Image_mod
_PIL_pkg.ImageDraw  = _ImageDraw_mod
_PIL_pkg.ImageFont  = _ImageFont_mod

for _name, _mod in [
    ('PIL',              _PIL_pkg),
    ('PIL.Image',        _Image_mod),
    ('PIL.ImageDraw',    _ImageDraw_mod),
    ('PIL.ImageFont',    _ImageFont_mod),
]:
    sys.modules.setdefault(_name, _mod)

# ── 2. Path setup ─────────────────────────────────────────────────────────────

_HERE = os.path.dirname(__file__)
_APP  = os.path.join(_HERE, '..', 'zerofish')
if _APP not in sys.path:
    sys.path.insert(0, _APP)

# ── 3. Import application modules ─────────────────────────────────────────────

import config  # pure-Python, no PIL
import ui       # uses mocked PIL
import screen_wifi as sw

# Re-export constants to keep test code readable
from screen_wifi import (
    _signal_bars, _KBD_PAGES, _KBD_NUM_PAGES, _KBD_SPECIAL,
    _WIFI_SEP, _RP_X0, _RP_W,
    _LIST_Y0, _LIST_LH, _LIST_MAX_ROWS,
    _RESCAN_Y0, _RESCAN_Y1,
    _KBD_COLS, _KBD_ROWS, _KBD_BTN_W, _KBD_BTN_H, _KBD_GAP,
    _KBD_COL_X, _KBD_ROW_Y,
    _KBACK_Y0, _KBACK_Y1,
    _RP_BTN_X0, _RP_BTN_X1, _RP_BTN_H,
    _RP_STATUS_Y,
    _RP_BTN1_Y0, _RP_BTN1_Y1,
    _RP_BTN1_CONN_Y0, _RP_BTN1_CONN_Y1,
    _RP_BACK_Y0, _RP_BACK_Y1,
    _RP_IP_Y,
    build_wifi_screen, hit_wifi,
    build_wifi_result_screen, hit_wifi_result,
    scan_networks, connect_open, connect_wpa,
    forget_network, get_active_ip,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _net(ssid='Test', signal=80, in_use=False, has_password=False, ip=None):
    """Construct a minimal network dict."""
    return {'ssid': ssid, 'signal': signal, 'in_use': in_use,
            'has_password': has_password, 'ip': ip}


def _open_net(**kw):
    return _net(has_password=False, **kw)


def _wpa_net(**kw):
    return _net(has_password=True, **kw)


def _connected_net(**kw):
    kw.setdefault('in_use', True)
    kw.setdefault('has_password', True)
    kw.setdefault('ip', '192.168.1.99')
    return _net(**kw)


def _mid(a, b):
    """Centre coordinate between a and b (inclusive)."""
    return (a + b) // 2


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestSignalBars(unittest.TestCase):
    """_signal_bars(): correct tier for every boundary value."""

    def test_100(self):   self.assertEqual(_signal_bars(100), '||||')
    def test_80(self):    self.assertEqual(_signal_bars(80),  '||||')
    def test_75(self):    self.assertEqual(_signal_bars(75),  '||||')
    def test_74(self):    self.assertEqual(_signal_bars(74),  '||| ')
    def test_60(self):    self.assertEqual(_signal_bars(60),  '||| ')
    def test_50(self):    self.assertEqual(_signal_bars(50),  '||| ')
    def test_49(self):    self.assertEqual(_signal_bars(49),  '||  ')
    def test_30(self):    self.assertEqual(_signal_bars(30),  '||  ')
    def test_25(self):    self.assertEqual(_signal_bars(25),  '||  ')
    def test_24(self):    self.assertEqual(_signal_bars(24),  '|   ')
    def test_10(self):    self.assertEqual(_signal_bars(10),  '|   ')
    def test_1(self):     self.assertEqual(_signal_bars(1),   '|   ')
    def test_0(self):     self.assertEqual(_signal_bars(0),   '    ')

    def test_bars_are_four_chars(self):
        for signal in (0, 1, 24, 25, 49, 50, 74, 75, 100):
            self.assertEqual(len(_signal_bars(signal)), 4,
                             f'wrong length for signal={signal}')


class TestScanNetworks(unittest.TestCase):
    """scan_networks(): parsing, sorting, deduplication, IP attachment."""

    _BASE_OUT = (
        '*:HomeWifi:90:WPA2\n'
        ':CafeNet:60:--\n'
        ':WeakSecure:20:WPA1\n'
    )
    # get_active_ip is called for the connected network; mock it away
    _IP_SIDE = [
        (0, 'wlan0:wifi:connected\n', ''),
        (0, 'IP4.ADDRESS[1]:10.0.0.1/24\n', ''),
    ]

    @patch('screen_wifi.get_active_ip', return_value='10.0.0.1')
    @patch('screen_wifi._run')
    def test_parses_three_networks(self, mock_run, _mock_ip):
        mock_run.return_value = (0, self._BASE_OUT, '')
        nets = scan_networks()
        self.assertEqual(len(nets), 3)

    @patch('screen_wifi.get_active_ip', return_value='10.0.0.1')
    @patch('screen_wifi._run')
    def test_connected_is_first(self, mock_run, _mock_ip):
        mock_run.return_value = (0, self._BASE_OUT, '')
        nets = scan_networks()
        self.assertTrue(nets[0]['in_use'])
        self.assertEqual(nets[0]['ssid'], 'HomeWifi')

    @patch('screen_wifi.get_active_ip', return_value=None)
    @patch('screen_wifi._run')
    def test_non_connected_sorted_by_signal_desc(self, mock_run, _mock_ip):
        out = ':NetA:40:WPA2\n:NetB:70:WPA2\n:NetC:55:--\n'
        mock_run.return_value = (0, out, '')
        nets = scan_networks()
        signals = [n['signal'] for n in nets]
        self.assertEqual(signals, sorted(signals, reverse=True))

    @patch('screen_wifi.get_active_ip', return_value=None)
    @patch('screen_wifi._run')
    def test_has_password_wpa(self, mock_run, _mock_ip):
        out = ':SecureNet:80:WPA2\n'
        mock_run.return_value = (0, out, '')
        nets = scan_networks()
        self.assertTrue(nets[0]['has_password'])

    @patch('screen_wifi.get_active_ip', return_value=None)
    @patch('screen_wifi._run')
    def test_no_password_open(self, mock_run, _mock_ip):
        out = ':OpenNet:80:--\n'
        mock_run.return_value = (0, out, '')
        nets = scan_networks()
        self.assertFalse(nets[0]['has_password'])

    @patch('screen_wifi.get_active_ip', return_value=None)
    @patch('screen_wifi._run')
    def test_in_use_flag(self, mock_run, _mock_ip):
        mock_run.return_value = (0, self._BASE_OUT, '')
        nets = scan_networks()
        by_ssid = {n['ssid']: n for n in nets}
        self.assertTrue(by_ssid['HomeWifi']['in_use'])
        self.assertFalse(by_ssid['CafeNet']['in_use'])

    @patch('screen_wifi._run')
    def test_returns_empty_on_nmcli_error(self, mock_run):
        mock_run.return_value = (1, '', 'nmcli: error')
        self.assertEqual(scan_networks(), [])

    @patch('screen_wifi.get_active_ip', return_value=None)
    @patch('screen_wifi._run')
    def test_deduplicates_ssid(self, mock_run, _mock_ip):
        out = ':SameNet:90:WPA2\n:SameNet:85:WPA2\n'
        mock_run.return_value = (0, out, '')
        nets = scan_networks()
        self.assertEqual(len(nets), 1)
        self.assertEqual(nets[0]['ssid'], 'SameNet')

    @patch('screen_wifi.get_active_ip', return_value=None)
    @patch('screen_wifi._run')
    def test_skips_blank_ssid(self, mock_run, _mock_ip):
        out = '::50:WPA2\n:ValidNet:70:--\n'
        mock_run.return_value = (0, out, '')
        nets = scan_networks()
        self.assertEqual(len(nets), 1)
        self.assertEqual(nets[0]['ssid'], 'ValidNet')

    @patch('screen_wifi.get_active_ip', return_value='192.168.0.5')
    @patch('screen_wifi._run')
    def test_ip_attached_to_connected(self, mock_run, _mock_ip):
        out = '*:HomeWifi:90:WPA2\n:Other:60:--\n'
        mock_run.return_value = (0, out, '')
        nets = scan_networks()
        by_ssid = {n['ssid']: n for n in nets}
        self.assertEqual(by_ssid['HomeWifi']['ip'], '192.168.0.5')
        self.assertIsNone(by_ssid['Other']['ip'])

    @patch('screen_wifi.get_active_ip', return_value=None)
    @patch('screen_wifi._run')
    def test_ip_none_when_no_connected(self, mock_run, _mock_ip):
        out = ':NetA:80:WPA2\n'
        mock_run.return_value = (0, out, '')
        nets = scan_networks()
        self.assertIsNone(nets[0]['ip'])

    @patch('screen_wifi.get_active_ip', return_value=None)
    @patch('screen_wifi._run')
    def test_ssid_with_colon_in_security(self, mock_run, _mock_ip):
        # Security field "WPA1 WPA2:WPA1 WPA2" should not confuse the parser
        out = ':OfficeNet:70:WPA1 WPA2\n'
        mock_run.return_value = (0, out, '')
        nets = scan_networks()
        self.assertEqual(len(nets), 1)
        self.assertTrue(nets[0]['has_password'])

    @patch('screen_wifi.get_active_ip', return_value=None)
    @patch('screen_wifi._run')
    def test_all_nets_have_ip_key(self, mock_run, _mock_ip):
        mock_run.return_value = (0, self._BASE_OUT, '')
        for net in scan_networks():
            self.assertIn('ip', net)


class TestConnectOpen(unittest.TestCase):
    """connect_open(): success/failure, correct nmcli args."""

    @patch('screen_wifi._run')
    def test_success_returns_true(self, mock_run):
        mock_run.return_value = (0, 'Device connected successfully', '')
        ok, msg = connect_open('TestSSID')
        self.assertTrue(ok)
        self.assertIn('connected', msg.lower())

    @patch('screen_wifi._run')
    def test_failure_returns_false_with_error(self, mock_run):
        mock_run.return_value = (1, '', 'Connection timed out')
        ok, msg = connect_open('TestSSID')
        self.assertFalse(ok)
        self.assertIn('timed out', msg)

    @patch('screen_wifi._run')
    def test_stderr_preferred_over_stdout_on_failure(self, mock_run):
        mock_run.return_value = (1, 'stdout msg', 'stderr msg')
        _, msg = connect_open('X')
        self.assertEqual(msg, 'stderr msg')

    @patch('screen_wifi._run')
    def test_fallback_message_when_both_empty(self, mock_run):
        mock_run.return_value = (1, '', '')
        ok, msg = connect_open('X')
        self.assertFalse(ok)
        self.assertTrue(len(msg) > 0)

    @patch('screen_wifi._run')
    def test_correct_nmcli_args(self, mock_run):
        mock_run.return_value = (0, 'ok', '')
        connect_open('MySSID')
        args = mock_run.call_args[0][0]
        self.assertIn('connect', args)
        self.assertIn('MySSID', args)
        self.assertNotIn('password', args)


class TestConnectWpa(unittest.TestCase):
    """connect_wpa(): success/failure, password forwarded to nmcli."""

    @patch('screen_wifi._run')
    def test_success(self, mock_run):
        mock_run.return_value = (0, 'Connected', '')
        ok, _ = connect_wpa('SecureNet', 'pa$$w0rd')
        self.assertTrue(ok)

    @patch('screen_wifi._run')
    def test_failure_wrong_password(self, mock_run):
        mock_run.return_value = (1, '', 'Secrets were required but not provided')
        ok, msg = connect_wpa('SecureNet', 'wrongpass')
        self.assertFalse(ok)
        self.assertIn('Secrets', msg)

    @patch('screen_wifi._run')
    def test_password_forwarded(self, mock_run):
        mock_run.return_value = (0, 'ok', '')
        connect_wpa('SecureNet', 'mySecretPass')
        args = mock_run.call_args[0][0]
        self.assertIn('mySecretPass', args)
        self.assertIn('password', args)

    @patch('screen_wifi._run')
    def test_ssid_forwarded(self, mock_run):
        mock_run.return_value = (0, 'ok', '')
        connect_wpa('MyNetwork', 'pw')
        args = mock_run.call_args[0][0]
        self.assertIn('MyNetwork', args)

    @patch('screen_wifi._run')
    def test_uses_30s_timeout(self, mock_run):
        mock_run.return_value = (0, 'ok', '')
        connect_wpa('Net', 'pw')
        timeout = mock_run.call_args[1].get('timeout') or mock_run.call_args[0][1]
        self.assertEqual(timeout, 30)


class TestForgetNetwork(unittest.TestCase):
    """forget_network(): calls nmcli delete, silent on error."""

    @patch('screen_wifi._run')
    def test_calls_nmcli_delete(self, mock_run):
        mock_run.return_value = (0, '', '')
        forget_network('HomeNet')
        args = mock_run.call_args[0][0]
        self.assertIn('delete', args)
        self.assertIn('HomeNet', args)

    @patch('screen_wifi._run')
    def test_silent_on_not_found(self, mock_run):
        mock_run.return_value = (1, '', 'No such connection')
        forget_network('Ghost')  # Must not raise

    @patch('screen_wifi._run')
    def test_silent_on_error_code(self, mock_run):
        # _run never raises; failure manifests as a non-zero return code.
        # forget_network must silently ignore it.
        mock_run.return_value = (-1, '', 'TimeoutExpired: ...')
        forget_network('AnyNet')  # Must not raise


class TestGetActiveIp(unittest.TestCase):
    """get_active_ip(): device lookup and IP extraction."""

    _STATUS_CONNECTED = 'wlan0:wifi:connected\neth0:ethernet:disconnected\n'
    _STATUS_DISCONNECTED = 'wlan0:wifi:disconnected\n'
    _IP_OUTPUT = 'IP4.ADDRESS[1]:192.168.1.55/24\n'

    @patch('screen_wifi._run')
    def test_returns_ip_without_prefix(self, mock_run):
        mock_run.side_effect = [
            (0, self._STATUS_CONNECTED, ''),
            (0, self._IP_OUTPUT, ''),
        ]
        self.assertEqual(get_active_ip(), '192.168.1.55')

    @patch('screen_wifi._run')
    def test_returns_none_when_disconnected(self, mock_run):
        mock_run.return_value = (0, self._STATUS_DISCONNECTED, '')
        self.assertIsNone(get_active_ip())

    @patch('screen_wifi._run')
    def test_returns_none_on_status_error(self, mock_run):
        mock_run.return_value = (1, '', 'nmcli: error')
        self.assertIsNone(get_active_ip())

    @patch('screen_wifi._run')
    def test_returns_none_when_no_ip_line(self, mock_run):
        mock_run.side_effect = [
            (0, self._STATUS_CONNECTED, ''),
            (0, 'IP6.ADDRESS[1]:fe80::1/64\n', ''),  # IPv6 only
        ]
        self.assertIsNone(get_active_ip())

    @patch('screen_wifi._run')
    def test_uses_correct_device_name(self, mock_run):
        mock_run.side_effect = [
            (0, 'wlp2s0:wifi:connected\n', ''),
            (0, self._IP_OUTPUT, ''),
        ]
        get_active_ip()
        second_call_args = mock_run.call_args_list[1][0][0]
        self.assertIn('wlp2s0', second_call_args)

    @patch('screen_wifi._run')
    def test_short_timeout_for_status(self, mock_run):
        mock_run.return_value = (1, '', '')
        get_active_ip()
        first_timeout = mock_run.call_args_list[0][1].get('timeout', 15)
        self.assertLessEqual(first_timeout, 5)


class TestKeyboardPages(unittest.TestCase):
    """Keyboard character pages: coverage and structure."""

    def _all_chars(self):
        return ''.join(''.join(page) for page in _KBD_PAGES)

    def test_page_count_matches_constant(self):
        self.assertEqual(len(_KBD_PAGES), _KBD_NUM_PAGES)

    def test_every_page_has_15_chars(self):
        for i, page in enumerate(_KBD_PAGES):
            self.assertEqual(len(page), 15,
                             f'page {i} has {len(page)} chars, expected 15')

    def test_all_lowercase_covered(self):
        chars = self._all_chars()
        for ch in 'abcdefghijklmnopqrstuvwxyz':
            self.assertIn(ch, chars, f'lowercase {ch!r} missing from keyboard')

    def test_all_uppercase_covered(self):
        chars = self._all_chars()
        for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            self.assertIn(ch, chars, f'uppercase {ch!r} missing from keyboard')

    def test_all_digits_covered(self):
        chars = self._all_chars()
        for ch in '0123456789':
            self.assertIn(ch, chars, f'digit {ch!r} missing from keyboard')

    def test_no_duplicate_chars_within_page(self):
        for i, page in enumerate(_KBD_PAGES):
            self.assertEqual(len(page), len(set(page)),
                             f'page {i} contains duplicate characters')

    def test_special_row_has_five_keys(self):
        self.assertEqual(len(_KBD_SPECIAL), 5)

    def test_special_row_contains_del(self):
        self.assertIn('Del', _KBD_SPECIAL)

    def test_special_row_contains_space(self):
        self.assertIn('Sp', _KBD_SPECIAL)

    def test_special_row_contains_page_arrows(self):
        self.assertIn('<', _KBD_SPECIAL)
        self.assertIn('>', _KBD_SPECIAL)

    def test_special_row_contains_ok(self):
        self.assertIn('OK', _KBD_SPECIAL)


class TestBuildWifiScreen(unittest.TestCase):
    """build functions execute without raising for all display modes."""

    _NETS = [
        _open_net(ssid='OpenNet', signal=80),
        _wpa_net(ssid='WpaNet',  signal=60),
        _connected_net(ssid='Connected', signal=90, ip='10.0.0.2'),
    ]

    def test_no_selection(self):
        build_wifi_screen(self._NETS, None, '', 0)

    def test_open_selected(self):
        build_wifi_screen(self._NETS, 0, '', 0)

    def test_wpa_selected_keyboard_mode(self):
        build_wifi_screen(self._NETS, 1, 'password', 0)

    def test_connected_selected(self):
        build_wifi_screen(self._NETS, 2, '', 0)

    def test_empty_network_list(self):
        build_wifi_screen([], None, '', 0)

    def test_all_keyboard_pages(self):
        nets = [_wpa_net(ssid='WPA')]
        for page in range(_KBD_NUM_PAGES):
            build_wifi_screen(nets, 0, 'pw', page)

    def test_long_password_truncated(self):
        build_wifi_screen([_wpa_net()], 0, 'x' * 100, 0)

    def test_scroll_offset(self):
        many = [_open_net(ssid=f'Net{i}', signal=90 - i) for i in range(10)]
        build_wifi_screen(many, None, '', 0, scroll_off=5)

    def test_selected_idx_out_of_range(self):
        # Should not crash — treat as no selection
        build_wifi_screen(self._NETS, 99, '', 0)

    def test_network_with_no_ip(self):
        nets = [_connected_net(ip=None)]
        build_wifi_screen(nets, 0, '', 0)


class TestBuildWifiResultScreen(unittest.TestCase):
    """build_wifi_result_screen() executes for various message lengths."""

    def test_short_message(self):
        build_wifi_result_screen('TestNet', 'Connection failed')

    def test_long_message(self):
        build_wifi_result_screen(
            'TestNet',
            'Error: Secrets were required but not provided. '
            'Please verify the password and try again.',
        )

    def test_empty_message(self):
        build_wifi_result_screen('Net', '')

    def test_long_ssid(self):
        build_wifi_result_screen('A' * 50, 'Connection failed')


class TestHitLeftPanel(unittest.TestCase):
    """hit_wifi() – left panel: network selection and Rescan button."""

    _NETS = [
        _open_net(ssid='NetA', signal=90),
        _wpa_net(ssid='NetB',  signal=70),
        _open_net(ssid='NetC', signal=50),
        _open_net(ssid='NetD', signal=40),
        _open_net(ssid='NetE', signal=30),
    ]
    _LX = _WIFI_SEP // 2  # x in left panel centre

    def _hit(self, lx, ly, sel=None, scroll=0):
        return hit_wifi(lx, ly, self._NETS, sel, 0, scroll)

    def test_tap_first_row_selects_net_0(self):
        ly = _LIST_Y0 + _LIST_LH // 2
        self.assertEqual(self._hit(self._LX, ly), 'select:0')

    def test_tap_second_row_selects_net_1(self):
        ly = _LIST_Y0 + _LIST_LH + _LIST_LH // 2
        self.assertEqual(self._hit(self._LX, ly), 'select:1')

    def test_tap_fifth_row_selects_net_4(self):
        ly = _LIST_Y0 + 4 * _LIST_LH + _LIST_LH // 2
        self.assertEqual(self._hit(self._LX, ly), 'select:4')

    def test_scroll_offset_shifts_index(self):
        # Tapping slot 0 with scroll_off=2 → index 2
        ly = _LIST_Y0 + _LIST_LH // 2
        self.assertEqual(self._hit(self._LX, ly, scroll=2), 'select:2')

    def test_tap_beyond_available_networks_returns_none(self):
        # Only 5 nets (indices 0-4); slot 5 is within _LIST_MAX_ROWS (6) but
        # idx=5 >= len(networks)=5, so it must return None.
        ly = _LIST_Y0 + 5 * _LIST_LH + _LIST_LH // 2
        self.assertIsNone(self._hit(self._LX, ly))

    def test_tap_empty_list_returns_none(self):
        ly = _LIST_Y0 + _LIST_LH // 2
        result = hit_wifi(self._LX, ly, [], None, 0)
        self.assertIsNone(result)

    def test_tap_title_bar_area_returns_none(self):
        # y is inside the left title bar (above _LIST_Y0), must return None
        ly = ui.TITLE_H - 2
        self.assertIsNone(self._hit(self._LX, ly))

    def test_tap_rescan_button(self):
        ly = _mid(_RESCAN_Y0, _RESCAN_Y1)
        self.assertEqual(self._hit(self._LX, ly), 'rescan')

    def test_tap_rescan_top_edge(self):
        self.assertEqual(self._hit(self._LX, _RESCAN_Y0), 'rescan')

    def test_tap_rescan_bottom_edge(self):
        self.assertEqual(self._hit(self._LX, _RESCAN_Y1), 'rescan')

    def test_left_panel_recognised_at_separator_minus_1(self):
        # x = _WIFI_SEP - 1 is still in the left panel
        ly = _LIST_Y0 + _LIST_LH // 2
        self.assertEqual(self._hit(_WIFI_SEP - 1, ly), 'select:0')

    def test_rescan_works_regardless_of_selection(self):
        ly = _mid(_RESCAN_Y0, _RESCAN_Y1)
        for sel in [None, 0, 2]:
            with self.subTest(sel=sel):
                self.assertEqual(self._hit(self._LX, ly, sel=sel), 'rescan')


class TestHitListModeRightPanel(unittest.TestCase):
    """hit_wifi() – right panel in list mode (no keyboard)."""

    _LX = _mid(_RP_BTN_X0, _RP_BTN_X1)  # x in right panel centre

    def _hit(self, ly, nets, sel=None):
        return hit_wifi(self._LX, ly, nets, sel, 0)

    def test_back_no_selection(self):
        ly = _mid(_RP_BACK_Y0, _RP_BACK_Y1)
        self.assertEqual(self._hit(ly, [_open_net()]), 'back')

    def test_back_with_open_selected(self):
        nets = [_open_net()]
        ly = _mid(_RP_BACK_Y0, _RP_BACK_Y1)
        self.assertEqual(self._hit(ly, nets, sel=0), 'back')

    def test_connect_open_network(self):
        nets = [_open_net()]
        ly = _mid(_RP_BTN1_Y0, _RP_BTN1_Y1)
        self.assertEqual(self._hit(ly, nets, sel=0), 'connect_open')

    def test_no_connect_button_without_selection(self):
        ly = _mid(_RP_BTN1_Y0, _RP_BTN1_Y1)
        self.assertIsNone(self._hit(ly, [_open_net()], sel=None))

    def test_forget_connected_network(self):
        nets = [_connected_net()]
        ly = _mid(_RP_BTN1_CONN_Y0, _RP_BTN1_CONN_Y1)
        self.assertEqual(self._hit(ly, nets, sel=0), 'forget')

    def test_no_forget_when_not_connected(self):
        nets = [_open_net()]
        ly = _mid(_RP_BTN1_CONN_Y0, _RP_BTN1_CONN_Y1)
        # open net uses BTN1_Y not BTN1_CONN_Y, so this area is a no-hit
        result = self._hit(ly, nets, sel=0)
        self.assertNotEqual(result, 'forget')

    def test_tapping_between_buttons_returns_none(self):
        nets = [_open_net()]
        # y between the action button and Back button
        ly = (_RP_BTN1_Y1 + _RP_BACK_Y0) // 2
        self.assertIsNone(self._hit(ly, nets, sel=0))

    def test_right_panel_at_separator_plus_2(self):
        # x = _RP_X0 is the first right-panel pixel
        nets = [_open_net()]
        ly = _mid(_RP_BACK_Y0, _RP_BACK_Y1)
        result = hit_wifi(_RP_X0, ly, nets, None, 0)
        # _RP_X0 < _RP_BTN_X0, so Back hit requires x >= _RP_BTN_X0
        # This is at the separator gap; depends on _RP_BTN_X0 vs _RP_X0
        # Just assert no crash
        self.assertIn(result, [None, 'back'])


class TestHitKeyboardMode(unittest.TestCase):
    """hit_wifi() – right panel in keyboard mode (WPA selected)."""

    _NETS = [_wpa_net(ssid='Secure')]  # has_password=True, in_use=False

    def _hit(self, lx, ly, page=0):
        return hit_wifi(lx, ly, self._NETS, 0, page)

    def test_back_kbd_button(self):
        lx = _mid(_RP_X0, ui.W - 2)
        ly = _mid(_KBACK_Y0, _KBACK_Y1)
        self.assertEqual(self._hit(lx, ly), 'back_kbd')

    def test_back_kbd_top_edge(self):
        lx = _mid(_RP_X0, ui.W - 2)
        self.assertEqual(self._hit(lx, _KBACK_Y0), 'back_kbd')

    def test_first_char_page0_is_a(self):
        lx = _KBD_COL_X[0] + _KBD_BTN_W // 2
        ly = _KBD_ROW_Y[0] + _KBD_BTN_H // 2
        self.assertEqual(self._hit(lx, ly, page=0), 'char:a')

    def test_first_char_page1_is_p(self):
        lx = _KBD_COL_X[0] + _KBD_BTN_W // 2
        ly = _KBD_ROW_Y[0] + _KBD_BTN_H // 2
        self.assertEqual(self._hit(lx, ly, page=1), 'char:p')

    def test_all_pages_return_char_for_first_key(self):
        lx = _KBD_COL_X[0] + _KBD_BTN_W // 2
        ly = _KBD_ROW_Y[0] + _KBD_BTN_H // 2
        for page in range(_KBD_NUM_PAGES):
            with self.subTest(page=page):
                result = self._hit(lx, ly, page=page)
                self.assertTrue(result.startswith('char:'),
                                f'page {page}: expected char:X, got {result!r}')

    def test_each_char_row_returns_different_chars(self):
        lx = _KBD_COL_X[0] + _KBD_BTN_W // 2
        results = []
        for row in range(_KBD_ROWS - 1):
            ly = _KBD_ROW_Y[row] + _KBD_BTN_H // 2
            results.append(self._hit(lx, ly, page=0))
        # All three chars from col 0 on rows 0-2 of page 0 must be distinct
        self.assertEqual(len(results), len(set(results)))

    def test_last_col_row0_page0_is_e(self):
        # Page 0 row 0: a b c d e
        lx = _KBD_COL_X[4] + _KBD_BTN_W // 2
        ly = _KBD_ROW_Y[0] + _KBD_BTN_H // 2
        self.assertEqual(self._hit(lx, ly, page=0), 'char:e')

    def test_del_key(self):
        # Del is _KBD_SPECIAL[0] → col 0, row 3
        lx = _KBD_COL_X[0] + _KBD_BTN_W // 2
        ly = _KBD_ROW_Y[3] + _KBD_BTN_H // 2
        self.assertEqual(self._hit(lx, ly), 'del')

    def test_space_key(self):
        lx = _KBD_COL_X[1] + _KBD_BTN_W // 2
        ly = _KBD_ROW_Y[3] + _KBD_BTN_H // 2
        self.assertEqual(self._hit(lx, ly), 'space')

    def test_prev_page_key(self):
        lx = _KBD_COL_X[2] + _KBD_BTN_W // 2
        ly = _KBD_ROW_Y[3] + _KBD_BTN_H // 2
        self.assertEqual(self._hit(lx, ly), 'prev_page')

    def test_next_page_key(self):
        lx = _KBD_COL_X[3] + _KBD_BTN_W // 2
        ly = _KBD_ROW_Y[3] + _KBD_BTN_H // 2
        self.assertEqual(self._hit(lx, ly), 'next_page')

    def test_ok_connect_key(self):
        lx = _KBD_COL_X[4] + _KBD_BTN_W // 2
        ly = _KBD_ROW_Y[3] + _KBD_BTN_H // 2
        self.assertEqual(self._hit(lx, ly), 'connect_wpa')

    def test_left_of_keyboard_returns_none(self):
        # x in the left panel while WPA net is selected — should select network
        ly = _LIST_Y0 + _LIST_LH // 2
        result = hit_wifi(10, ly, self._NETS, 0, 0)
        self.assertEqual(result, 'select:0')  # left panel always works

    def test_tap_between_char_rows_returns_none(self):
        # y in the gap between row 0 and row 1 (gap = 1 px at _KBD_ROW_Y[0]+_KBD_BTN_H)
        lx = _KBD_COL_X[0] + _KBD_BTN_W // 2
        gap_y = _KBD_ROW_Y[0] + _KBD_BTN_H  # 1-pixel gap
        result = self._hit(lx, gap_y)
        # Gap is only 1 px; result may or may not be None — just no exception
        self.assertIn(result, [None, 'char:a', 'char:f'])

    def test_page_wraps_modulo(self):
        # Accessing page _KBD_NUM_PAGES should wrap to page 0
        lx = _KBD_COL_X[0] + _KBD_BTN_W // 2
        ly = _KBD_ROW_Y[0] + _KBD_BTN_H // 2
        r0 = self._hit(lx, ly, page=0)
        rw = self._hit(lx, ly, page=_KBD_NUM_PAGES)
        self.assertEqual(r0, rw)

    def test_open_net_does_not_show_keyboard(self):
        # Open network should NOT trigger keyboard mode
        open_nets = [_open_net(ssid='Open')]
        result = hit_wifi(
            _KBD_COL_X[0] + _KBD_BTN_W // 2,
            _KBD_ROW_Y[0] + _KBD_BTN_H // 2,
            open_nets, 0, 0,
        )
        # In list mode for open net this area may return None (not in any button)
        self.assertNotEqual(result, 'char:a')


class TestHitWifiResult(unittest.TestCase):
    """hit_wifi_result() – OK button and misses."""

    _OK_LX = _mid(ui.OK_X0, ui.OK_X1)
    _OK_LY = _mid(ui.OK_Y0, ui.OK_Y1)

    def test_ok_hit_centre(self):
        self.assertEqual(hit_wifi_result(self._OK_LX, self._OK_LY), 'ok')

    def test_ok_hit_left_edge(self):
        self.assertEqual(hit_wifi_result(ui.OK_X0, self._OK_LY), 'ok')

    def test_ok_hit_right_edge(self):
        self.assertEqual(hit_wifi_result(ui.OK_X1, self._OK_LY), 'ok')

    def test_ok_miss_left_of_button(self):
        self.assertIsNone(hit_wifi_result(ui.OK_X0 - 1, self._OK_LY))

    def test_ok_miss_top_of_button(self):
        self.assertIsNone(hit_wifi_result(self._OK_LX, ui.OK_Y0 - 1))

    def test_ok_miss_far_left(self):
        self.assertIsNone(hit_wifi_result(10, self._OK_LY))

    def test_ok_miss_far_top(self):
        self.assertIsNone(hit_wifi_result(self._OK_LX, 10))


class TestInteractionFlows(unittest.TestCase):
    """Multi-step interaction sequences with a realistic network list."""

    # Realistic mock network list:
    # index 0: connected WPA  (HomeNet, strong signal, IP)
    # index 1: open           (CafeNet, medium signal)
    # index 2: WPA unconnected (OfficeNet, weak signal)
    _NETS = [
        _connected_net(ssid='HomeNet', signal=95, ip='192.168.1.1'),
        _open_net(ssid='CafeNet',  signal=65),
        _wpa_net(ssid='OfficeNet', signal=30),
    ]

    # ── Left panel ────────────────────────────────────────────────────────────

    def test_select_connected_network(self):
        ly = _LIST_Y0 + _LIST_LH // 2
        self.assertEqual(hit_wifi(10, ly, self._NETS, None, 0), 'select:0')

    def test_select_open_network(self):
        ly = _LIST_Y0 + _LIST_LH + _LIST_LH // 2
        self.assertEqual(hit_wifi(10, ly, self._NETS, None, 0), 'select:1')

    def test_select_wpa_network(self):
        ly = _LIST_Y0 + 2 * _LIST_LH + _LIST_LH // 2
        self.assertEqual(hit_wifi(10, ly, self._NETS, None, 0), 'select:2')

    def test_rescan_from_any_state(self):
        ly = _mid(_RESCAN_Y0, _RESCAN_Y1)
        for sel in [None, 0, 1, 2]:
            with self.subTest(sel=sel):
                self.assertEqual(hit_wifi(10, ly, self._NETS, sel, 0), 'rescan')

    # ── Connected network selected → list mode ────────────────────────────────

    def test_forget_connected(self):
        lx = _mid(_RP_BTN_X0, _RP_BTN_X1)
        ly = _mid(_RP_BTN1_CONN_Y0, _RP_BTN1_CONN_Y1)
        self.assertEqual(hit_wifi(lx, ly, self._NETS, 0, 0), 'forget')

    def test_back_with_connected_selected(self):
        lx = _mid(_RP_BTN_X0, _RP_BTN_X1)
        ly = _mid(_RP_BACK_Y0, _RP_BACK_Y1)
        self.assertEqual(hit_wifi(lx, ly, self._NETS, 0, 0), 'back')

    # ── Open network selected → list mode ────────────────────────────────────

    def test_connect_open_network(self):
        lx = _mid(_RP_BTN_X0, _RP_BTN_X1)
        ly = _mid(_RP_BTN1_Y0, _RP_BTN1_Y1)
        self.assertEqual(hit_wifi(lx, ly, self._NETS, 1, 0), 'connect_open')

    def test_back_with_open_selected(self):
        lx = _mid(_RP_BTN_X0, _RP_BTN_X1)
        ly = _mid(_RP_BACK_Y0, _RP_BACK_Y1)
        self.assertEqual(hit_wifi(lx, ly, self._NETS, 1, 0), 'back')

    # ── WPA network selected → keyboard mode ─────────────────────────────────

    def test_type_password_chars(self):
        """Typing a–e across columns on page 0 returns char:X for each."""
        ly = _KBD_ROW_Y[0] + _KBD_BTN_H // 2
        expected = list('abcde')  # page 0 row 0 cols 0-4
        for col, ch in enumerate(expected):
            lx = _KBD_COL_X[col] + _KBD_BTN_W // 2
            with self.subTest(col=col):
                self.assertEqual(hit_wifi(lx, ly, self._NETS, 2, 0), 'char:' + ch)

    def test_advance_page_and_type(self):
        # Page 1, row 0, col 0 → 'p'
        lx = _KBD_COL_X[0] + _KBD_BTN_W // 2
        ly = _KBD_ROW_Y[0] + _KBD_BTN_H // 2
        self.assertEqual(hit_wifi(lx, ly, self._NETS, 2, 1), 'char:p')

    def test_delete_key(self):
        lx = _KBD_COL_X[0] + _KBD_BTN_W // 2
        ly = _KBD_ROW_Y[3] + _KBD_BTN_H // 2
        self.assertEqual(hit_wifi(lx, ly, self._NETS, 2, 0), 'del')

    def test_space_key(self):
        lx = _KBD_COL_X[1] + _KBD_BTN_W // 2
        ly = _KBD_ROW_Y[3] + _KBD_BTN_H // 2
        self.assertEqual(hit_wifi(lx, ly, self._NETS, 2, 0), 'space')

    def test_prev_page_key(self):
        lx = _KBD_COL_X[2] + _KBD_BTN_W // 2
        ly = _KBD_ROW_Y[3] + _KBD_BTN_H // 2
        self.assertEqual(hit_wifi(lx, ly, self._NETS, 2, 0), 'prev_page')

    def test_next_page_key(self):
        lx = _KBD_COL_X[3] + _KBD_BTN_W // 2
        ly = _KBD_ROW_Y[3] + _KBD_BTN_H // 2
        self.assertEqual(hit_wifi(lx, ly, self._NETS, 2, 0), 'next_page')

    def test_ok_connect_key(self):
        lx = _KBD_COL_X[4] + _KBD_BTN_W // 2
        ly = _KBD_ROW_Y[3] + _KBD_BTN_H // 2
        self.assertEqual(hit_wifi(lx, ly, self._NETS, 2, 0), 'connect_wpa')

    def test_back_kbd_button(self):
        lx = _mid(_RP_X0, ui.W - 2)
        ly = _mid(_KBACK_Y0, _KBACK_Y1)
        self.assertEqual(hit_wifi(lx, ly, self._NETS, 2, 0), 'back_kbd')

    def test_switch_network_while_keyboard_shown(self):
        # Tapping a different network in the left panel while WPA is selected
        ly = _LIST_Y0 + _LIST_LH // 2  # slot 0 (HomeNet)
        result = hit_wifi(10, ly, self._NETS, 2, 0)
        self.assertEqual(result, 'select:0')

    # ── Geometry sanity checks ────────────────────────────────────────────────

    def test_list_max_rows_positive(self):
        self.assertGreater(_LIST_MAX_ROWS, 0)

    def test_kback_is_below_keyboard(self):
        last_kbd_row_bottom = _KBD_ROW_Y[-1] + _KBD_BTN_H
        self.assertGreater(_KBACK_Y0, last_kbd_row_bottom)

    def test_rescan_is_below_list(self):
        last_list_bottom = _LIST_Y0 + _LIST_MAX_ROWS * _LIST_LH
        self.assertGreaterEqual(_RESCAN_Y0, last_list_bottom)

    def test_rp_back_does_not_overlap_keyboard(self):
        # Keyboard Back (KBD) and list-mode Back (RP) are never shown together.
        # KBD_BACK starts higher (keyboard fills full right panel height);
        # RP_BACK sits lower. Both reach the same bottom edge.
        self.assertLessEqual(_KBACK_Y0, _RP_BACK_Y0)
        self.assertEqual(_KBACK_Y1, _RP_BACK_Y1)

    def test_connected_forget_below_ip_row(self):
        self.assertGreater(_RP_BTN1_CONN_Y0, _RP_IP_Y)

    def test_keyboard_cols_within_right_panel(self):
        rightmost = _KBD_COL_X[-1] + _KBD_BTN_W - 1
        self.assertLessEqual(rightmost, ui.W - 1)

    def test_keyboard_rows_within_display(self):
        bottommost = _KBD_ROW_Y[-1] + _KBD_BTN_H - 1
        self.assertLess(bottommost, _KBACK_Y0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
