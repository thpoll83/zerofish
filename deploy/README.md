# ZeroFish — Deploy Guide

## One-time: copy your SSH key

```bash
ssh-copy-id zero@<rpi-ip>
```

Run this once per development machine. Without it every `rsync` call in `deploy.sh` prompts for a password and the final `sudo systemctl restart` step fails (sudo requires a TTY when SSH uses password auth).

## First-time RPi setup

After flashing Raspberry Pi OS (64-bit Trixie) and enabling SSH, run the setup script once:

```bash
ssh-copy-id zero@<rpi-ip>
ssh -t zero@<rpi-ip> bash deploy/rpi_setup.sh
```

`rpi_setup.sh` enables SPI/I2C, installs all Python dependencies, and writes a sudoers entry so future deploys can restart the service without a password.

Reboot after setup:

```bash
ssh zero@<rpi-ip> sudo reboot
```

## Everyday deploy

```bash
bash deploy/deploy.sh                   # default host: 192.168.68.55
bash deploy/deploy.sh 192.168.1.42      # override IP
```

Syncs all code, installs/updates the systemd unit, and restarts the service. New code is live immediately.

## Service management

```bash
ssh zero@<rpi-ip> systemctl status zerofish
ssh zero@<rpi-ip> journalctl -fu zerofish    # live log
```

## Run manually (debugging)

```bash
ssh zero@<rpi-ip> python3 ~/zerofish/main.py
```

Ctrl+C to stop. Each touch event, move, and Stockfish reply is logged at INFO level.

## Smoke test (WaveShare sample)

```bash
ssh zero@<rpi-ip>
cd ~/Touch_e-Paper_Code/python/examples
python3 TP2in13_V4_test.py
```

Ctrl+C to exit cleanly.

## Troubleshooting

### "GPIO busy" error on startup

A previous process exited uncleanly and the kernel still holds the GPIO pins:

```bash
ssh zero@<rpi-ip> 'pkill -f python3'
```

### Display stays blank

Restart the app — this clears stale display state left by a previous unclean exit.

### Touch not responding

```bash
ssh zero@<rpi-ip> sudo i2cdetect -y 1   # should show 0x14
```

If missing, re-enable I2C: `sudo raspi-config` → Interface Options → I2C.
