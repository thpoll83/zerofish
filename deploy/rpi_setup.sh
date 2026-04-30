#!/bin/bash
# Run this script ON the Raspberry Pi Zero 2 W after flashing a fresh 64-bit image.
# It enables the required interfaces, installs Python dependencies, and verifies
# the GT1151 touch controller is visible on the I2C bus.
#
# Usage (run with an interactive terminal so sudo can prompt for a password):
#   ssh -t zero@192.168.68.55 bash deploy/rpi_setup.sh

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
    stockfish \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fonts-noto-core
pip3 install chess --break-system-packages

echo ""
echo "=== 3. Allowing passwordless sudo for deploy script ==="
echo 'zero ALL=(ALL) NOPASSWD: /bin/cp, /usr/bin/systemctl, /usr/local/bin/zerofish-set-governor' \
    | sudo tee /etc/sudoers.d/zerofish > /dev/null
sudo chmod 0440 /etc/sudoers.d/zerofish
echo "Sudoers entry written."

echo ""
echo "=== 4. CPU governor helper ==="
sudo tee /usr/local/bin/zerofish-set-governor > /dev/null << 'EOF'
#!/bin/bash
case "$1" in
    performance|powersave|ondemand|conservative)
        for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
            echo "$1" > "$f"
        done
        ;;
    *)
        echo "Unknown governor: $1" >&2
        exit 1
        ;;
esac
EOF
sudo chmod +x /usr/local/bin/zerofish-set-governor
echo "Governor helper installed."

echo ""
echo "=== 5. Power tuning ==="
CONFIG=/boot/firmware/config.txt
# Reduce GPU memory to minimum (e-paper needs no framebuffer; frees 48 MB)
if ! grep -q 'gpu_mem=16' "$CONFIG"; then
    echo 'gpu_mem=16' | sudo tee -a "$CONFIG" > /dev/null
    echo "GPU memory reduced to 16 MB."
else
    echo "GPU memory already at 16 MB."
fi
# Disable Bluetooth (unused; saves ~10–15 mA)
if ! grep -q 'dtparam=bt=off' "$CONFIG"; then
    echo 'dtparam=bt=off' | sudo tee -a "$CONFIG" > /dev/null
    echo "Bluetooth disabled."
else
    echo "Bluetooth already disabled."
fi
# CPU governor: powersave (caps frequency when idle; saves ~15–25 mA)
sudo tee /etc/systemd/system/cpu-powersave.service > /dev/null << 'EOF'
[Unit]
Description=Set CPU scaling governor to powersave
After=sysinit.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'for gov in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo powersave > "$gov"; done'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable cpu-powersave.service
echo "CPU powersave governor service installed."

echo ""
echo "=== 6. Verifying I2C bus (GT1151 touch controller should appear at 0x14) ==="
sudo i2cdetect -y 1

echo ""
echo "=== Setup complete ==="
echo "Reboot recommended if SPI/I2C were just enabled for the first time:"
echo "  sudo reboot"
