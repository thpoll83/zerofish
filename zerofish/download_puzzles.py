#!/usr/bin/env python3
"""Download 1-move chess puzzles from the Lichess database.

Can be imported by the application for background auto-download, or run as a
standalone script on the Raspberry Pi:

    python3 ~/zerofish/download_puzzles.py [count]

Default count: 200.  Puzzles are stored in ~/.zerofish_puzzles/puzzles.json.

Source: https://database.lichess.org/#puzzles
CSV columns: PuzzleId, FEN, Moves, Rating, RatingDeviation, Popularity,
             NbPlays, Themes, GameUrl, OpeningTags

FEN is the position BEFORE the opponent's "trigger" move.
Moves: first UCI move = trigger (opponent), remaining = solution path.
A 1-move puzzle has exactly 2 UCI moves: trigger + the one solution move.
Promotion puzzles (5-char solution UCI such as e7e8q) are included.

Requires: zstandard  (pip3 install zstandard --break-system-packages)
"""

import csv
import io
import json
import os
import random
import socket
import sys
import threading
import urllib.request

import chess

PUZZLE_URL = 'https://database.lichess.org/lichess_db_puzzle.csv.zst'
PUZZLE_DIR = os.path.expanduser('~/.zerofish_puzzles')
OUT_FILE   = os.path.join(PUZZLE_DIR, 'puzzles.json')


def has_internet(host: str = 'database.lichess.org',
                 port: int = 443,
                 timeout: float = 5.0) -> bool:
    """Return True if the puzzle server is reachable."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _load_solved_ids() -> set:
    solved_file = os.path.join(PUZZLE_DIR, 'solved.json')
    try:
        with open(solved_file) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def _existing_ids() -> set:
    try:
        with open(OUT_FILE) as f:
            data = json.load(f)
        return {p['id'] for p in data.get('puzzles', [])}
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def run_download(count: int = 1000,
                 stop_event: threading.Event | None = None,
                 progress_cb=None) -> bool:
    """Download puzzles from Lichess and merge them into the local puzzle file.

    count       — target number of new puzzles to add
    stop_event  — set this Event to abort the download mid-stream
    progress_cb — optional callable(rows_checked, found) for progress updates

    Returns True if puzzles were saved, False on error / abort / no internet.
    """
    try:
        import zstandard as zstd
    except ImportError:
        print('Error: zstandard is required.  '
              'pip3 install zstandard --break-system-packages')
        return False

    if not has_internet():
        print('No internet connection — skipping puzzle download.')
        return False

    collect  = count * 5
    os.makedirs(PUZZLE_DIR, exist_ok=True)
    solved   = _load_solved_ids()
    existing = _existing_ids()
    skip_ids = solved | existing

    print(f'Downloading puzzles from Lichess (target: {count}) …')
    print(f'Skipping {len(skip_ids)} already-known puzzle IDs.')

    candidates: list[dict] = []
    rows_checked = 0

    try:
        req = urllib.request.Request(PUZZLE_URL, headers={'User-Agent': 'ZeroFish/1.0'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            dctx = zstd.ZstdDecompressor()
            with dctx.stream_reader(resp) as reader:
                text_stream = io.TextIOWrapper(reader, encoding='utf-8')
                csv_reader  = csv.DictReader(text_stream)

                for row in csv_reader:
                    if stop_event is not None and stop_event.is_set():
                        print('Puzzle download cancelled.')
                        return False

                    rows_checked += 1
                    if rows_checked % 10000 == 0:
                        print(f'  … scanned {rows_checked:,} rows, '
                              f'found {len(candidates)} candidates', flush=True)
                        if progress_cb is not None:
                            progress_cb(rows_checked, len(candidates))

                    puzzle_id = row.get('PuzzleId', '').strip()
                    if puzzle_id in skip_ids:
                        continue

                    moves = row.get('Moves', '').strip().split()
                    if len(moves) != 2:
                        continue  # not a 1-move puzzle

                    trigger_uci, solution_uci = moves

                    # Accept both normal (4-char) and promotion (5-char) moves.
                    if len(solution_uci) not in (4, 5):
                        continue

                    try:
                        b = chess.Board(row['FEN'])
                        trigger = chess.Move.from_uci(trigger_uci)
                        if trigger not in b.legal_moves:
                            continue
                        b.push(trigger)
                        solution = chess.Move.from_uci(solution_uci)
                        if solution not in b.legal_moves:
                            continue

                        candidates.append({
                            'id':       puzzle_id,
                            'fen':      b.fen(),
                            'solution': solution_uci,
                            'rating':   int(row.get('Rating', 1500)),
                        })
                    except Exception:
                        continue

                    if len(candidates) >= collect:
                        break

    except Exception as exc:
        print(f'Download error: {exc}')
        return False

    if not candidates:
        print('No matching puzzles found.')
        return False

    sample = random.sample(candidates, min(count, len(candidates)))
    print(f'Sampled {len(sample)} puzzles from {len(candidates)} candidates '
          f'(checked {rows_checked:,} rows).')

    # Merge with existing unsolved puzzles
    try:
        with open(OUT_FILE) as f:
            old_data = json.load(f)
        old_puzzles = [p for p in old_data.get('puzzles', [])
                       if p['id'] not in solved]
    except (FileNotFoundError, json.JSONDecodeError):
        old_puzzles = []

    merged = old_puzzles + sample
    with open(OUT_FILE, 'w') as f:
        json.dump({'version': 1, 'puzzles': merged}, f)

    print(f'Saved {len(merged)} puzzles total to {OUT_FILE}')
    print('(Previous unsolved puzzles kept + new batch added.)')
    return True


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    ok = run_download(count)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
