#!/bin/bash
# Run this script ON the Raspberry Pi Zero 2 W after flashing a fresh 64-bit image.
# It enables the required interfaces, installs Python dependencies, and verifies
# the GT1151 touch controller is visible on the I2C bus.
#
# Usage (from dev machine, after SSH key is set up):
#   ssh zero@192.168.68.55 bash deploy/rpi_setup.sh

set -e

echo "=== 1. Enabling SPI and I2C ==="
sudo raspi-config nonint do_spi 0
sudo raspi-config nonint do_i2c 0
echo "SPI and I2C enabled."

echo ""
echo "=== 2. Installing Python dependencies ==="
sudo apt update
sudo apt install -y \
    python3-gpiozero \
    python3-smbus \
    python3-spidev \
    python3-pil \
    python3-numpy \
    python3-pip \
    i2c-tools \
    stockfish
pip3 install chess --break-system-packages

echo ""
echo "=== 3. Verifying I2C bus (GT1151 touch controller should appear at 0x14) ==="
sudo i2cdetect -y 1

echo ""
echo "=== Setup complete ==="
echo "Reboot recommended if SPI/I2C were just enabled for the first time:"
echo "  sudo reboot"
