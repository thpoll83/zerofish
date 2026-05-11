"""Debug remote mode — TCP server for remote display and touch injection.

Activated via `main.py --debug-remote`.  Runs a background TCP server on
PORT that:
  • sends every rendered PIL frame as a length-prefixed PNG to all viewers
  • receives logical (lx, ly) touch coordinates from viewers and injects them
    into the touch event queue that DebugGT1151.GT_Scan drains

Wire protocol (both directions use the same framing):
  [4 bytes big-endian: payload length] [N bytes payload]
  Server → client payload : raw PNG image bytes
  Client → server payload : 8 bytes — two int32 big-endian (lx, ly)
"""

import io
import logging
import queue
import socket
import struct
import threading
import time

log = logging.getLogger(__name__)

PORT = 7373

# Shared state — populated by start(), read by stubs
_touch_q: queue.Queue   = queue.Queue()
_clients: list          = []
_clients_lock           = threading.Lock()
_last_frame: bytes|None = None  # most-recent PNG; sent to newly connected viewers


# ── Server ────────────────────────────────────────────────────────────────────

def _send_frame(png_bytes: bytes) -> None:
    global _last_frame
    _last_frame = png_bytes
    header = struct.pack('>I', len(png_bytes))
    with _clients_lock:
        dead = []
        for conn in list(_clients):
            try:
                conn.sendall(header + png_bytes)
            except OSError:
                dead.append(conn)
        for conn in dead:
            _clients.remove(conn)
            try:
                conn.close()
            except OSError:
                pass


def _client_reader(conn: socket.socket, addr) -> None:
    log.info('Debug viewer connected from %s', addr)
    buf = b''
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
            while len(buf) >= 4:
                (length,) = struct.unpack_from('>I', buf)
                if len(buf) < 4 + length:
                    break
                payload = buf[4:4 + length]
                buf = buf[4 + length:]
                if length == 8:
                    lx, ly = struct.unpack('>ii', payload)
                    _touch_q.put((lx, ly))
    except OSError:
        pass
    finally:
        log.info('Debug viewer %s disconnected', addr)
        with _clients_lock:
            if conn in _clients:
                _clients.remove(conn)
        try:
            conn.close()
        except OSError:
            pass


def _server_thread() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        for attempt in range(1, 16):
            try:
                srv.bind(('', PORT))
                break
            except OSError:
                log.warning('Debug server: port %d busy (attempt %d/15), retrying in 2 s…',
                            PORT, attempt)
                time.sleep(2)
        else:
            log.error('Debug server: port %d still busy after 30 s — giving up', PORT)
            return
        srv.listen(4)
        log.info('Debug remote server listening on port %d', PORT)
        while True:
            try:
                conn, addr = srv.accept()
            except OSError:
                break
            with _clients_lock:
                _clients.append(conn)
                # Immediately send the last known frame so the viewer isn't blank.
                if _last_frame is not None:
                    try:
                        conn.sendall(struct.pack('>I', len(_last_frame)) + _last_frame)
                    except OSError:
                        pass
            threading.Thread(target=_client_reader, args=(conn, addr),
                             daemon=True).start()


def start() -> None:
    """Start the background TCP server.  Call once before the main loop."""
    threading.Thread(target=_server_thread, daemon=True).start()


# ── Stub hardware objects ──────────────────────────────────────────────────────

class DebugEPD:
    """Drop-in replacement for epd2in13_V4.EPD that streams frames over TCP."""

    FULL_UPDATE = 0
    PART_UPDATE = 1

    def init(self, mode):        pass
    def Clear(self, color):      pass
    def sleep(self):             pass
    def Dev_exit(self):          pass

    def getbuffer(self, img):
        # Return the PIL image unchanged; display methods receive it directly.
        return img

    def _send(self, img) -> None:
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        _send_frame(buf.getvalue())

    def displayPartBaseImage(self, img):
        self._send(img)

    def displayPartial_Wait(self, img):
        self._send(img)


class GTDevelopment:
    """Mirror of gt1151.GT_Development — used in debug mode to avoid importing epdconfig."""
    def __init__(self):
        self.Touch            = 0
        self.TouchpointFlag   = 0
        self.TouchCount       = 0
        self.Touchkeytrackid  = [0, 1, 2, 3, 4]
        self.X                = [0, 1, 2, 3, 4]
        self.Y                = [0, 1, 2, 3, 4]
        self.S                = [0, 1, 2, 3, 4]


class DebugGT1151:
    """Drop-in replacement for gt1151.GT1151 that drains the remote touch queue."""

    INT = 0  # pin constant (value unused in debug mode)

    def GT_Init(self):        pass
    def GT_DumpConfig(self):  pass
    def GT_Reset(self):       pass

    def digital_read(self, pin) -> int:
        # Return 0 (active-low INT asserted) when a touch is waiting so that
        # the irq_poll thread in main.py sets dev.Touch = 1.
        return 0 if not _touch_q.empty() else 1

    def GT_Scan(self, dev, old) -> None:
        if dev.Touch != 1:
            return
        dev.Touch = 0
        try:
            lx, ly = _touch_q.get_nowait()
        except queue.Empty:
            dev.TouchpointFlag = 0
            return
        # to_landscape(tx, ty) = (249 - ty, tx)  →  inverse: tx = ly, ty = 249 - lx
        old.X[0] = dev.X[0]
        old.Y[0] = dev.Y[0]
        old.S[0] = dev.S[0]
        dev.X[0] = ly
        dev.Y[0] = 249 - lx
        dev.S[0] = 50
        dev.TouchpointFlag = 0x80
        dev.TouchCount = 1
