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

# Ensure the repo root is on sys.path so hardware_stubs is importable
_REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import hardware_stubs
hardware_stubs.install()
