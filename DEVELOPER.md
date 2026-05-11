# ZeroFish — Developer Documentation

**Player guide (with screenshots and translations): [README.md](README.md)**

## Hardware

| Part | Detail | Where to buy |
|------|--------|--------------|
| Raspberry Pi Zero 2 W | Host board | [Amazon](https://amzn.eu/d/0armY7FJ) |
| WaveShare 2.13" Touch e-Paper HAT V4 | 122 × 250 px B/W, SPI display + GT1151 I2C touch | [Amazon](https://amzn.eu/d/086WPCji) |
| Micro USB cable + USB power supply or power bank | Powers the Pi Zero via its micro USB port | — |
| Standard chess board | Any physical board | — |

The display attaches to the GPIO header. No additional wiring is needed beyond the HAT.

## Dev machine setup

One-time setup on the development machine (Linux / macOS):

```bash
# 1. Create and populate the Python venv
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. (Linux only) Install the system package that provides tkinter
#    Required for debug_viewer.py — the rest of the venv works without it
sudo apt install python3-tk   # Debian / Ubuntu / Raspberry Pi OS
```

`tkinter` is Python stdlib; its C extension (`_tkinter.so`) lives in Python's
`lib-dynload` directory, so it is visible inside the venv once `python3-tk` is
installed — no venv recreation needed.

macOS ships `tkinter` out of the box with its system Python 3 / Homebrew Python.

## First-time setup

1. Flash a 64-bit Raspberry Pi OS (Trixie / Debian 13) image.
2. Enable SSH and set **username to `zero`** via RPi Imager advanced options (the hostname set here doesn't matter — `rpi_setup.sh` will override it).
3. Find the Pi's IP address from your router, copy your SSH key, then clone this repo:

```bash
ssh-copy-id zero@<rpi-ip>
git clone <this-repo>
```

4. Deploy files and run the setup script **once** (password prompt requires an interactive terminal):

```bash
bash deploy/deploy.sh <rpi-ip>
ssh -t zero@<rpi-ip> bash deploy/rpi_setup.sh            # mDNS name: zerofish.local (default)
ssh -t zero@<rpi-ip> bash deploy/rpi_setup.sh mydevice   # custom: mydevice.local
```

`rpi_setup.sh` handles:
- Enabling SPI and I2C via `raspi-config`
- Installing all Python dependencies (`gpiozero`, `spidev`, `smbus`, `pillow`, `numpy`, `chess`, fonts, `stockfish`)
- Writing a sudoers entry so that future deploys can restart the service non-interactively
- Power tuning: Bluetooth off, GPU memory at 16 MB, CPU powersave governor on boot, CPU governor helper script
- Installing `avahi-daemon` and pinning the mDNS hostname in `/etc/avahi/avahi-daemon.conf` so the Pi is reachable as `<hostname>.local` regardless of the system hostname. Re-running with a different name updates the existing config safely. Default is `zerofish.local`.

5. Reboot the RPi. ZeroFish starts automatically on every boot via systemd, and the Pi is reachable as `zerofish.local` — no more hunting for IP addresses.

```bash
ssh zero@zerofish.local
bash deploy/deploy.sh   # all future deploys use zerofish.local automatically
```

## Deploying changes

From your development machine:

```bash
bash deploy/deploy.sh
```

This syncs all code, installs/updates the systemd service, and restarts it. The new code is live immediately.

```bash
ssh zero@zerofish.local systemctl status zerofish
ssh zero@zerofish.local journalctl -fu zerofish   # live log
```

## Resolving zerofish.local

The Pi advertises itself over mDNS (Bonjour/Avahi) so `zerofish.local` works without a fixed IP or DNS entry. What you need on the **dev machine** depends on the OS:

### macOS
Nothing to do — Bonjour is built in. `zerofish.local` resolves immediately.

### Linux
Most desktop distros already have the required packages. Check and fix in two steps:

**1. Install the packages (if missing):**
```bash
sudo apt install avahi-daemon libnss-mdns   # Debian/Ubuntu
```

**2. Allow non-link-local resolution:**

Open `/etc/nsswitch.conf` and find the `hosts:` line. Change `mdns4_minimal` to `mdns4`:

```
# before
hosts: files mdns4_minimal [NOTFOUND=return] dns

# after
hosts: files mdns4 [NOTFOUND=return] dns
```

`mdns4_minimal` only resolves link-local addresses (169.254.x.x). `mdns4` resolves any IPv4 address advertised via mDNS, which is what the Pi uses (192.168.x.x).

No restart needed — the change takes effect immediately.

### Windows
Windows 10 (build 1703+) and Windows 11 include a built-in mDNS client. `zerofish.local` should resolve in a PowerShell or Command Prompt without any extra software. If it doesn't, install [Apple Bonjour for Windows](https://support.apple.com/kb/DL999) (also bundled with iTunes and iCloud).

### Verify
```bash
ssh zero@zerofish.local 'hostname -I'
```

If that times out, fall back to the IP address — check your router's DHCP table or run:
```bash
# Linux/macOS
avahi-resolve-host-name zerofish.local   # requires avahi-utils on Linux

# Any OS
ping zerofish.local
```

## Testing

### Unit tests (dev machine, no hardware)

Run the full unit suite locally. The `conftest.py` in `tests/` stubs out all RPi hardware, so no Pi is needed.

```bash
.venv/bin/python3 -m pytest tests/ --ignore=tests/rpi -v
```

The RPi integration tests auto-skip on a non-Pi machine — running without `--ignore` is safe but produces skips rather than runs.

### RPi integration tests (real hardware required)

The tests in `tests/rpi/` exercise the complete game loop on real e-ink hardware with a mock Stockfish engine (instant, deterministic first-legal-move replies) and injected touch events. They skip automatically on any machine that isn't a Raspberry Pi.

**Deploy the code first**, then SSH into the Pi and run pytest:

```bash
bash deploy/deploy.sh                                         # sync latest code to the Pi
ssh zero@zerofish.local 'cd ~/zerofish && pytest tests/rpi/ -v'
```

The two tests covered:

| Test | What it exercises |
|------|-------------------|
| `test_new_game_white_resign` | New game as White → play 1.e4 → acknowledge Stockfish reply → open menu → resign → game over → splash |
| `test_resume_unfinished_game` | Pre-existing save file detected on startup → resume screen → select game → resign → game over → splash |

Each test starts `main.main()` in a background thread, injects touch events via a semaphore-synchronised queue, and blocks until the real e-ink display finishes each full refresh. pytest must be installed on the Pi:

```bash
pip3 install pytest --break-system-packages
```

## Debug remote viewer

`debug_viewer.py` lets you run the full application on the RPi and control it
from your dev machine — no physical touch required. Every rendered frame is
streamed over TCP and displayed in a scaled window; left-clicks are forwarded
as touch events.

### Start

```bash
# 1. Deploy the latest code
bash deploy/deploy.sh

# 2. On the RPi — stop the normal service and start in debug mode
ssh zero@zerofish.local 'sudo systemctl stop zerofish && cd ~/zerofish && python3 main.py --debug-remote'

# 3. On the dev machine — open the viewer (in a separate terminal)
.venv/bin/python3 debug_viewer.py            # connects to zerofish.local:7373
.venv/bin/python3 debug_viewer.py <host>     # custom host / IP
```

The viewer connects automatically and shows the current screen immediately
(the server replays the last frame to any new connection). Left-click anywhere
in the window to inject a touch event at that position.

When finished, `Ctrl-C` the SSH session to stop the app; the normal service
can be restarted with:

```bash
bash deploy/deploy.sh   # also restarts the service
```

### How it works

`--debug-remote` swaps the real e-paper and touch hardware for in-process stubs
(`DebugEPD`, `DebugGT1151` in `zerofish/debug_remote.py`):

- **Display:** `DebugEPD.getbuffer()` returns the PIL image unchanged.
  `displayPartBaseImage` / `displayPartial_Wait` encode it as PNG and broadcast
  to all connected viewers over a length-prefixed TCP stream (port 7373).
- **Touch:** viewer clicks are sent as `[4-byte length][8 bytes: lx, ly int32]`.
  `DebugGT1151.digital_read()` signals the IRQ when the queue is non-empty;
  `GT_Scan()` dequeues the event and back-transforms logical `(lx, ly)` to raw
  device coordinates so the existing `to_landscape()` call in `main.py`
  reconstructs the original values correctly.

The rest of `main.py` — game logic, Stockfish, WiFi, all screen modules — runs
unchanged. Multiple viewers can connect simultaneously (all receive the same
frames; any viewer can inject touches).

## Project structure

```
zerofish/
  main.py                     # full application — all screens and game loop
  screen_machine.py           # state machine: (screen_id, action) → next screen_id
  game_state.py               # save/load/clear game state (Resume after power loss)
  puzzle_state.py             # load/filter/mark-solved Lichess puzzles
  puzzle_session.py           # in-memory state for an active puzzle session
  download_puzzles.py         # background downloader (Lichess puzzle CSV)
  boot_splash.py              # early-boot script: shows "Booting…" before main service starts
  ui.py                       # shared layout, font cache, drawing helpers, screen base class
  config.py                   # all tunable constants: sizes, fonts, paths, idle timeout
  board_widget.py             # shared board-drawing widget (used by game + puzzle screens)
  game_utils.py               # move validation, SAN conversion helpers

  # ── Screen modules (one per screen) ────────────────────────────────────────
  screen_splash.py            # splash / loading
  screen_main_menu.py         # 3×2 main menu (New Game, Cont, Puzzle, Stats, Settings, Back)
  screen_difficulty.py        # engine-strength selection (15 levels)
  screen_color.py             # side selection (White / Black / Random)
  screen_thinking.py          # "Stockfish is thinking" indicator
  screen_sf_move.py           # engine move display
  screen_player_move.py       # player move input (piece / file / rank grid)
  screen_promotion.py         # pawn promotion piece selector
  screen_disambig.py          # source-square disambiguation
  screen_ingame_menu.py       # in-game menu (Resign, Board, Score Sheet, Time)
  screen_resign_confirm.py    # resign confirmation dialog
  screen_time.py              # elapsed-time display
  screen_board.py             # position viewer
  screen_scoresheet.py        # move-list viewer (portrait orientation)
  screen_game_over.py         # game result screen
  screen_resume.py            # saved-game browser
  screen_puzzle.py            # puzzle board + move-counter header + rank labels
  screen_puzzle_difficulty.py # 8-band Lichess-rating selector
  screen_puzzle_loading.py    # puzzle download progress
  screen_puzzle_end_confirm.py # "end puzzle session?" confirmation
  screen_puzzle_hint.py       # hint board after a wrong move
  screen_stats.py             # solved-puzzle totals per difficulty band
  screen_settings.py          # settings hub (currently: Wifi button)
  screen_wifi.py              # WiFi setup: network list + keyboard + result screen

  TP_lib/                     # WaveShare drivers (epd2in13_V4, gt1151, epdconfig)

deploy/
  deploy.sh            # rsync + service install/restart (run from dev machine)
  rpi_setup.sh         # first-time RPi setup: interfaces, packages, power tuning
  zerofish.service     # systemd unit — autorun on boot, restarts on failure
  zerofish-boot.service # early-boot splash service (runs before zerofish.service)

tests/
  conftest.py               # hardware stubs shared across all unit tests
  test_screen_render.py     # renders every screen without hardware
  test_hit_detection.py     # hit-zone geometry for all screens
  test_wifi_screen.py       # comprehensive WiFi screen tests (138 cases)
  test_game_state.py        # save/load round-trips
  test_logic.py             # move generation and SAN helpers
  test_find_candidates.py   # disambiguation logic
  test_coordinates.py       # touch → landscape coordinate mapping

generate_screenshots.py     # render all screens to docs/screenshots/ (3× scaled PNGs)
```

## Puzzle system

### Screen flow

```
Main menu → Puzzle difficulty → Puzzle (or Puzzle loading if download running)
              ↑ Back                ↓ Solve / Skip / End
                              Player move input
                                  ↓ OK (move validated)
                              Puzzle (updated board + move counter)
```

### Puzzle difficulty

`screen_puzzle_difficulty.py` mirrors `screen_difficulty.py` but offers 8 Lichess-rating bands instead of 15 engine-strength levels. The selected band is stored in `pz['diff_sel']` and used by `puzzle_state.load_unsolved_by_rating()` to filter the puzzle list. The ranges are defined in `config.PUZZLE_DIFF_MIN` / `config.PUZZLE_DIFF_MAX`.

### Multi-move puzzles

The downloader (`download_puzzles.py`) now accepts puzzles with any even number of total UCI moves (trigger + player/engine alternating). The stored format is:

```json
{
  "id": "abcde",
  "fen": "<FEN after trigger>",
  "moves": ["<player1>", "<engine1>", "<player2>", "…"],
  "rating": 1500
}
```

`moves[0]`, `moves[2]`, `moves[4]` … are the player's moves. `moves[1]`, `moves[3]` … are the engine's automatic responses. `puzzle_state.get_moves()` provides backward compatibility with the old single-`solution` format.

The `pz` dict in `main.py` tracks:

| Key | Meaning |
|-----|---------|
| `moves` | Full solution sequence from puzzle data |
| `move_idx` | Current position in `moves` (next expected player move index) |
| `move_num` | Player-move counter displayed as the numerator in "1/3" |
| `move_total` | Total player moves = `ceil(len(moves)/2)` |
| `sol` | UCI of the currently expected player move |
| `fen` | FEN at puzzle start — used to reset the board on a wrong answer |

`_pz_check_move(move_uci)` handles all three puzzle answer paths (normal, promotion, disambiguation). On a correct move it applies the engine response and advances the counter. On a wrong move it resets the board to `pz['fen']` for retry.

### Rank labels on the board

`screen_puzzle.py` draws rank numbers 1–8 in the 18 px gap between the board's right edge and the vertical separator line. The label for visual row `vrank` is `vrank+1` when white is at the bottom, or `8-vrank` when black is at the bottom. This makes the board orientation immediately clear without requiring the header to say "White" or "Black".

## WiFi system

### Screen layout

`screen_wifi.py` uses a non-standard left/right split at x = 100 px (vs. the standard `VSEP_X = 192`) to give the right panel 148 px for the 5 × 4 on-screen keyboard. The left panel title bar covers only x = 0..99; the right panel has no header and uses the full 122 px height.

```
x=0         x=100 x=102                  x=249
┌────────────┬─┬────────────────────────────┐
│ Wifi       │ │  (right panel — no header) │  y=0
├────────────│ │                            │  y=21
│ list rows  │ │  status / keyboard         │
│ (6 max)    │ │                            │
├────────────│ │                            │
│  Rescan    │ │           Back             │  y=100..120
└────────────┴─┴────────────────────────────┘
```

### Right panel modes

| Selected network | Mode |
|---|---|
| None / deselected | Back only |
| Open (no password) | "Open" label + Connect + Back |
| WPA (has password) | Password field + 5×4 keyboard + Back |
| Connected | "Connected" + IP address + Forget + Back |
| Post-forget disconnected | "Disconnected" label + Back |

### OS integration

All network operations use `nmcli` via the private `_run()` helper, which catches `subprocess.SubprocessError` and `OSError` and returns `(-1, '', '<type>: <msg>')` instead of raising. The public functions return `(success: bool, message: str)` for connect operations and are silent on error for `forget_network`.

`scan_networks()` parses nmcli tabular output with `line.split(':', 3)` (max 3 splits) so security strings that contain colons (e.g. `WPA1 WPA2:WPA1 WPA2`) are handled correctly. The scan blocks for up to 20 s; `main.py` renders an empty list screen first so the display is immediately responsive.

### `wifi_status` state variable

`main.py` tracks a `wifi_status: str` alongside the other WiFi state. It is set to `'disconnected'` after a successful Forget + rescan confirms no active connection, and reset to `''` on any Select or Rescan action. The flag is passed through to `build_wifi_screen()` / `hit_wifi()` and suppresses keyboard mode for WPA networks (showing "Disconnected" in the right panel instead).

## Dev Notes

### GT1151 touch controller — don't write the config

`Screen_Touch_Level` at register `0x8053` reads `0xFA` (250) from the factory — already at the hardware maximum. Writing any value via the config block write corrupts the chip and makes it unresponsive until the next reset. Leave it alone.

Missed taps are a software race condition, not a hardware sensitivity issue. `irq_poll()` must be **set-only**: it raises `dev.Touch = 1` when INT is low but never clears it. `GT_Scan()` clears it after reading. If `irq_poll` clears `dev.Touch` back to 0 between the `had_irq` snapshot and the `GT_Scan` call, the event is silently dropped. The thread also needs a small sleep (5 ms) — without it, it runs as a busy loop pinning one CPU core at 100%.

### E-paper refresh strategy

Two refresh paths exist and must be used correctly:

- `displayPartBaseImage` — writes to **both** frame buffers simultaneously. Use this on every screen transition so the previous screen doesn't ghost through on the next partial update.
- `displayPartial_Wait` — fast in-screen update. Use for button tap feedback.
- Force a full `FULL_UPDATE` cycle every 5 partial updates to prevent ghost accumulation.

On every screen transition: `epd.init(FULL_UPDATE)` → `displayPartBaseImage` → `epd.init(PART_UPDATE)`.

### Coordinate systems

The PIL canvas is always 250 × 122 (landscape). `epd.getbuffer()` applies a 270° rotation internally before sending to the display. Hold the device with the USB port on the left.

Touch coordinates from the GT1151 arrive in portrait space and must be swapped:
```python
lx = 249 - ty   # landscape X
ly = tx          # landscape Y
```

The score sheet is an exception — it renders a 122 × 250 portrait image. `getbuffer()` rotates it 180° for display. Hold the device upright (USB at the bottom). No touch transform is needed in portrait mode; raw `(tx, ty)` map directly to PIL coordinates.

### CPU governor

`powersave` is active at all times except during Stockfish's think:
```python
_set_cpu_governor('performance')
result = engine.play(board, think_limit)
_set_cpu_governor('powersave')
```

This is done at both call sites. The helper script (`/usr/local/bin/zerofish-set-governor`) is whitelisted in sudoers so no password prompt is needed.

### Chess glyph font

Unicode chess symbols (♟♞♝♜♛♚) require a font with coverage at U+2654–U+265F. The code tries **Chess Merida Unicode** first (traditional figurines, manual install) then falls back to **DejaVu Sans** (confirmed working). The piece font path list (`config.FONT_PIECE_PATHS`) is separate from the regular font family system because glyph coverage matters more than style here.

## Possible next steps

- Bluetooth board integration (auto-detect moves)
