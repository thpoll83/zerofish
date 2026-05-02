"""
RPi-specific pytest configuration.

Stops the zerofish systemd service before the test session so that GPIO pins
are free for the tests to claim, then restarts it afterwards.
"""
import subprocess
import pytest


def _is_rpi() -> bool:
    try:
        with open('/sys/firmware/devicetree/base/model') as f:
            return 'Raspberry Pi' in f.read()
    except OSError:
        return False


@pytest.fixture(scope='session', autouse=True)
def manage_zerofish_service():
    if not _is_rpi():
        yield
        return

    subprocess.run(['sudo', 'systemctl', 'stop', 'zerofish'], check=False)
    try:
        yield
    finally:
        subprocess.run(['sudo', 'systemctl', 'start', 'zerofish'], check=False)
