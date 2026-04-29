# ZeroFish

A standalone chess computer built on a Raspberry Pi Zero 2 W with a WaveShare 2.13" touch e-paper display. Stockfish runs as the engine; the player makes physical moves on a real board, then enters each move by tapping piece type and target square on the display.

## Hardware

| Part | Detail |
|------|--------|
| Raspberry Pi Zero 2 W | Host board |
| WaveShare 2.13" Touch e-Paper HAT V4 | 122 × 250 px B/W, SPI display + GT1151 I2C touch |
| Standard chess board | Any physical board |

The display attaches to the GPIO header. No additional wiring is needed beyond the HAT.

## First-time setup

1. Flash a 64-bit Raspberry Pi OS (Trixie / Debian 13) image.
2. Enable SSH, set hostname/user to `zero`, copy your SSH key.
3. Clone or copy this repo to your development machine.
4. Deploy files and run the setup script **once** (password prompt requires an interactive terminal):

```bash
bash deploy/deploy.sh          # copies files to the RPi
ssh -t zero@192.168.68.55 bash deploy/rpi_setup.sh
```

`rpi_setup.sh` handles:
- Enabling SPI and I2C via `raspi-config`
- Installing all Python dependencies (`gpiozero`, `spidev`, `smbus`, `pillow`, `numpy`, `chess`, `fonts-dejavu-core`, `stockfish`)
- Writing a sudoers entry so that future deploys can restart the service non-interactively

5. Reboot the RPi. ZeroFish starts automatically on every boot via systemd.

## Deploying changes

From your development machine:

```bash
bash deploy/deploy.sh
```

This syncs all code, installs/updates the systemd service, and restarts it. The new code is live immediately.

```bash
# Check service status
ssh zero@192.168.68.55 systemctl status zerofish

# Follow live logs
ssh zero@192.168.68.55 journalctl -fu zerofish
```

## How to play

Hold the device landscape (short edge top/bottom, USB port on the left).

1. **Difficulty** — tap 1–10 to choose engine strength, then OK.
2. **Side** — tap White, Black, or Random, then OK.
3. **Game loop:**
   - *Stockfish's turn:* the display shows its move in large SAN notation. Make the move on the physical board, then tap OK.
   - *Your turn:* tap the three button rows — piece type (♟♞♝♜♛♚), file (a–h), rank (1–8) — then OK. If the combination is illegal the selection resets (illegal count shown in the title bar).
4. **Game over:** when the game ends for any reason (checkmate, stalemate, draw) a result screen appears. Tap OK to start a new game from the difficulty selection.

## Project structure

```
zerofish/
  main.py                       # full application — all screens and game loop
deploy/
  deploy.sh                     # rsync + service install (run from dev machine)
  rpi_setup.sh                  # first-time RPi setup
  zerofish.service               # systemd unit file
Touch_e-Paper_Code/
  python/lib/TP_lib/
    epd2in13_V4.py              # display driver
    gt1151.py                   # touch controller driver
    epdconfig.py                # GPIO/SPI/I2C wiring
  python/pic/                   # Roboto fonts used by the UI
```

## Known limitations / possible next steps

- Pawn promotion always promotes to queen (no piece selection)
- No move history display
