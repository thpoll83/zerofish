# ZeroFish — Chess Computer on RPi Zero 2 W

## Hardware
- Raspberry Pi Zero 2 W
- WaveShare 2.13" Touch e-Paper HAT **V4**
  - Display driver: SPI
  - Touch controller: GT1151 at I2C address `0x14`

## RPi access
- **IP:** 192.168.68.55 (check router if it changes)
- **User / password:** zero / zero
- **SSH key** is installed — no password prompt from this machine
- `raspberrypi.local` does not resolve; always use the IP

## First-time RPi setup

1. Flash 64-bit Raspberry Pi OS to the SD card (Trixie / arm64).
2. Enable SSH and configure Wi-Fi via RPi Imager advanced options.
3. Run the setup script from this machine (after SSH key is copied):

```bash
ssh zero@192.168.68.55 bash deploy/rpi_setup.sh
```

Or copy and run it manually on the RPi:

```bash
scp deploy/rpi_setup.sh zero@192.168.68.55:~
ssh zero@192.168.68.55 bash rpi_setup.sh
```

4. Reboot:

```bash
ssh zero@192.168.68.55 sudo reboot
```

## Deploy project files

From this machine (repo root):

```bash
bash deploy/deploy.sh                  # default: 192.168.68.55
bash deploy/deploy.sh 192.168.1.42     # override IP if needed
```

## Run ZeroFish

```bash
# Foreground (output to terminal, Ctrl+C to stop)
ssh zero@192.168.68.55 python3 ~/zerofish/main.py

# Background (log to file)
ssh zero@192.168.68.55 'python3 ~/zerofish/main.py > /tmp/zerofish.log 2>&1 &'
ssh zero@192.168.68.55 cat /tmp/zerofish.log
```

Hold the device in **landscape orientation** (rotated 90° clockwise from portrait — USB port on the left).

## How to play

1. **Select difficulty** (1–10) and press OK.
2. **Select your side** (White / Black / Random) and press OK.
3. If you're **Black**, Stockfish plays first and shows its move in large notation — make the move on your physical board, then press OK.
4. **Input your move** using the 3 button rows:
   - Row 1: piece (P N B R Q K)
   - Row 2: file (a–h)
   - Row 3: rank (1–8)
   Press OK when all three are selected.
5. If the combination is illegal, the selection resets — pick again.
6. Stockfish replies, then repeat from step 3/4.

## Smoke test (WaveShare sample)

```bash
ssh zero@192.168.68.55
cd ~/Touch_e-Paper_Code/python/examples
python3 TP2in13_V4_test.py
```

Press Ctrl+C to exit cleanly.

## Troubleshooting

### "GPIO busy" error on startup

The `lgpio` library claims GPIO pins at kernel level. If a previous Python process
exited uncleanly (e.g. killed mid-run), the pins stay locked until the process is gone.

Fix — kill any lingering Python process on the RPi:

```bash
ssh zero@192.168.68.55 'pkill -f python3'
```

Then start the app again normally.

### App starts but display stays blank

The display needs a full refresh on first use. If it stays blank, restart the app (kill and relaunch). This typically only happens if a previous run exited without calling `epd.sleep()`.

### Touch not responding

Verify the GT1151 is visible on the I2C bus:

```bash
ssh zero@192.168.68.55 sudo i2cdetect -y 1
# Should show 0x14
```

If missing, check that I2C is enabled (`sudo raspi-config` → Interface Options → I2C).

### Check live log

```bash
ssh zero@192.168.68.55 cat /tmp/zerofish.log
```

Each touch, difficulty selection, and Stockfish move is logged at INFO level.

## Project layout

```
zerofish/
  main.py                     ← ZeroFish application (landscape UI + Stockfish)
deploy/
  deploy.sh                   ← rsync project to RPi (run from this machine)
  rpi_setup.sh                ← first-time RPi setup: SPI/I2C + apt packages
  README.md                   ← this file
Touch_e-Paper_Code/
  python/
    examples/
      TP2in13_V4_test.py      ← WaveShare sample / smoke test
    lib/TP_lib/
      epdconfig.py            ← GPIO/SPI/I2C wiring (I2C address = 0x14)
      epd2in13_V4.py          ← display driver
      gt1151.py               ← touch controller driver
```

## Pin mapping (WaveShare 2.13" Touch HAT V4)

| Signal   | BCM GPIO |
|----------|----------|
| EPD RST  | 17       |
| EPD DC   | 25       |
| EPD CS   | 8 (CE0)  |
| EPD BUSY | 24       |
| TP RST   | 22       |
| TP INT   | 27       |
| SPI CLK  | 11       |
| SPI MOSI | 10       |
| I2C SDA  | 2        |
| I2C SCL  | 3        |
