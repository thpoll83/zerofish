"""
Inject no-op hardware modules so ZeroFish screen code can be imported and
used on a non-RPi development machine.

Call install() once before importing anything from the zerofish/ source tree.
Safe to call multiple times — subsequent calls are no-ops.
"""
import os
import sys
import types

_REPO = os.path.dirname(os.path.abspath(__file__))
SRC   = os.path.join(_REPO, 'zerofish')


def install() -> None:
    if SRC not in sys.path:
        sys.path.insert(0, SRC)

    for pkg in ('gpiozero', 'spidev', 'smbus'):
        sys.modules.setdefault(pkg, types.ModuleType(pkg))

    if 'TP_lib.epdconfig' in sys.modules:
        return   # already installed

    ec = types.ModuleType('TP_lib.epdconfig')

    # Pin constants (mirrors epdconfig.py)
    ec.EPD_RST_PIN  = 17
    ec.EPD_DC_PIN   = 25
    ec.EPD_CS_PIN   = 8
    ec.EPD_BUSY_PIN = 24
    ec.TRST         = 22
    ec.INT          = 27
    ec.address      = 0x14

    # Stub bus so gt1151.GT_WriteConfig can reference config.bus without error
    ec.bus = types.SimpleNamespace(
        write_i2c_block_data=lambda *a, **kw: None,
        read_byte=lambda *a: 0,
    )

    # All hardware operations become silent no-ops
    ec.digital_write  = lambda pin, value: None
    ec.digital_read   = lambda pin: 0   # 0 == not-busy / not-touched
    ec.delay_ms       = lambda ms: None
    ec.spi_writebyte  = lambda data: None
    ec.spi_writebyte2 = lambda data: None
    ec.i2c_writebyte  = lambda reg, value: None
    ec.i2c_write      = lambda reg: None
    ec.i2c_readbyte   = lambda reg, n: [0] * n
    ec.module_init    = lambda: 0
    ec.module_exit    = lambda: None

    tp = types.ModuleType('TP_lib')
    tp.__path__ = [os.path.join(SRC, 'TP_lib')]
    sys.modules['TP_lib']           = tp
    sys.modules['TP_lib.epdconfig'] = ec
