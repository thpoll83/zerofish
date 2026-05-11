#!/usr/bin/env python3
"""ZeroFish debug viewer — remote screen + touch injection.

Run on the dev machine while `main.py --debug-remote` runs on the RPi.

Usage:
    python3 debug_viewer.py [host]          # default host: zerofish.local

Left-click on the window to send a touch event to the RPi.
The image is shown at 3× scale (750×366 px).
"""

import io
import socket
import struct
import sys
import threading
import tkinter as tk

try:
    from PIL import Image, ImageTk
except ImportError:
    sys.exit('Pillow is required: pip install pillow')

HOST  = sys.argv[1] if len(sys.argv) > 1 else 'zerofish.local'
PORT  = 7373
SCALE = 3   # display magnification
# Canvas starts at landscape size; resized automatically when portrait arrives.
_LAND_W = 250 * SCALE   # 750
_LAND_H = 122 * SCALE   # 366


class Viewer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f'ZeroFish — {HOST}  (left-click = touch)')
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(self.root, width=_LAND_W, height=_LAND_H,
                                bg='white', highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind('<Button-1>', self._on_click)
        self._img_w = _LAND_W   # actual canvas pixel width (updated per frame)
        self._img_h = _LAND_H

        self._status = tk.StringVar(value='Connecting…')
        tk.Label(self.root, textvariable=self._status,
                 font=('monospace', 9), anchor='w').pack(fill='x', padx=4)

        self._photo = None  # keep ImageTk reference alive
        self._sock  = None
        self._reconnect()

    # ── Networking ─────────────────────────────────────────────────────────────

    def _reconnect(self):
        self._status.set(f'Connecting to {HOST}:{PORT}…')
        threading.Thread(target=self._connect_thread, daemon=True).start()

    def _connect_thread(self):
        try:
            sock = socket.create_connection((HOST, PORT), timeout=10)
            sock.settimeout(None)  # timeout was for connect only; reads block indefinitely
        except OSError as e:
            self.root.after(0, self._status.set, f'Connect failed: {e}  (retry in 3 s)')
            self.root.after(3000, self._reconnect)
            return
        self._sock = sock
        self.root.after(0, self._status.set, f'Connected to {HOST}:{PORT}')
        threading.Thread(target=self._reader, args=(sock,), daemon=True).start()

    def _reader(self, sock: socket.socket):
        buf = b''
        try:
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    raise ConnectionError('server closed connection')
                buf += chunk
                while len(buf) >= 4:
                    (length,) = struct.unpack_from('>I', buf)
                    if len(buf) < 4 + length:
                        break
                    png_data = buf[4:4 + length]
                    buf = buf[4 + length:]
                    self._schedule_frame(png_data)
        except (OSError, ConnectionError) as e:
            self.root.after(0, self._status.set, f'Disconnected: {e}  (retry in 3 s)')
            self.root.after(3000, self._reconnect)

    # ── Display ────────────────────────────────────────────────────────────────

    def _schedule_frame(self, png_data: bytes):
        self.root.after(0, self._show_frame, png_data)

    def _show_frame(self, png_data: bytes):
        img  = Image.open(io.BytesIO(png_data))
        pw, ph = img.size[0] * SCALE, img.size[1] * SCALE
        img  = img.resize((pw, ph), Image.NEAREST)
        if pw != self._img_w or ph != self._img_h:
            self._img_w, self._img_h = pw, ph
            self.canvas.config(width=pw, height=ph)
            self.root.geometry('')  # let the window shrink/grow
        photo = ImageTk.PhotoImage(img)
        self._photo = photo  # prevent GC
        self.canvas.create_image(0, 0, anchor='nw', image=photo)
        self._status.set(f'Connected to {HOST}:{PORT}')

    # ── Input ──────────────────────────────────────────────────────────────────

    def _on_click(self, event):
        sock = self._sock
        if sock is None:
            return
        raw_x = int(event.x / SCALE)
        raw_y = int(event.y / SCALE)
        # Clamp to whatever image was last shown (landscape or portrait).
        lx = max(0, min(self._img_w // SCALE - 1, raw_x))
        ly = max(0, min(self._img_h // SCALE - 1, raw_y))
        try:
            sock.sendall(struct.pack('>I', 8) + struct.pack('>ii', lx, ly))
            self._status.set(f'Touch sent ({lx}, {ly}) — waiting for response…')
        except OSError:
            pass

    # ── Run ────────────────────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    Viewer().run()
