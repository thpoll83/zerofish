"""
Configure sys.path and stub out RPi-only hardware before any test imports.

The real TP_lib/epdconfig.py instantiates gpiozero, spidev, and smbus objects
at module level, so it cannot be imported on a non-RPi machine at all.  We
inject a fake epdconfig module into sys.modules before anything else loads
TP_lib, which means epd2in13_V4 and gt1151 get the stub transparently when
they do `from . import epdconfig`.
"""
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC  = os.path.normpath(os.path.join(_HERE, '..', 'zerofish'))

sys.path.insert(0, _SRC)

# ── Stub RPi-only C extensions (not installable on a dev machine) ─────────
for _pkg in ('gpiozero', 'spidev', 'smbus'):
    sys.modules.setdefault(_pkg, types.ModuleType(_pkg))

# ── Build a fake TP_lib.epdconfig module ──────────────────────────────────
_ec = types.ModuleType('TP_lib.epdconfig')

# Pin constants (mirrors epdconfig.py)
_ec.EPD_RST_PIN  = 17
_ec.EPD_DC_PIN   = 25
_ec.EPD_CS_PIN   = 8
_ec.EPD_BUSY_PIN = 24
_ec.TRST         = 22
_ec.INT          = 27
_ec.address      = 0x14

# Stub bus so gt1151.GT_WriteConfig can reference config.bus without error
_ec.bus = types.SimpleNamespace(
    write_i2c_block_data=lambda *a, **kw: None,
    read_byte=lambda *a: 0,
)

# All hardware operations become silent no-ops
_ec.digital_write  = lambda pin, value: None
_ec.digital_read   = lambda pin: 0   # 0 == not-busy / not-touched
_ec.delay_ms       = lambda ms: None
_ec.spi_writebyte  = lambda data: None
_ec.spi_writebyte2 = lambda data: None
_ec.i2c_writebyte  = lambda reg, value: None
_ec.i2c_write      = lambda reg: None
_ec.i2c_readbyte   = lambda reg, n: [0] * n
_ec.module_init    = lambda: 0
_ec.module_exit    = lambda: None

# Register TP_lib as a package and expose our fake as its epdconfig
_tp = types.ModuleType('TP_lib')
_tp.__path__ = [os.path.join(_SRC, 'TP_lib')]
sys.modules['TP_lib']           = _tp
sys.modules['TP_lib.epdconfig'] = _ec
