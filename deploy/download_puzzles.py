#!/usr/bin/env python3
"""Download 1-move chess puzzles from the Lichess database.

Run this script ON the Raspberry Pi (after deploy.sh has synced files):

    python3 ~/zerofish/deploy/download_puzzles.py [count]

Default count: 200.  Puzzles are stored in ~/.zerofish_puzzles/puzzles.json.
Only puzzles where the player must find exactly one move are included.

Source: https://database.lichess.org/#puzzles
CSV columns: PuzzleId, FEN, Moves, Rating, RatingDeviation, Popularity,
             NbPlays, Themes, GameUrl, OpeningTags

FEN is the position BEFORE the opponent's "trigger" move.
Moves: first UCI move = trigger (opponent), remaining = solution path.
A 1-move puzzle has exactly 2 UCI moves: trigger + the one solution move.

Requires: zstandard  (pip3 install zstandard --break-system-packages)
"""

import csv
import io
import json
import os
import random
import sys
import urllib.request

import chess

TARGET     = int(sys.argv[1]) if len(sys.argv) > 1 else 200
PUZZLE_URL = 'https://database.lichess.org/lichess_db_puzzle.csv.zst'
PUZZLE_DIR = os.path.expanduser('~/.zerofish_puzzles')
OUT_FILE   = os.path.join(PUZZLE_DIR, 'puzzles.json')
# Collect up to 5× target then sample, to get variety without full download.
COLLECT    = TARGET * 5


def _load_solved_ids() -> set:
    solved_file = os.path.join(PUZZLE_DIR, 'solved.json')
    try:
        with open(solved_file) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def _existing_ids() -> set:
    """IDs already in puzzles.json (so we don't re-add them)."""
    try:
        with open(OUT_FILE) as f:
            data = json.load(f)
        return {p['id'] for p in data.get('puzzles', [])}
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def main() -> None:
    try:
        import zstandard as zstd
    except ImportError:
        print('Error: zstandard package is required.')
        print('Install with: pip3 install zstandard --break-system-packages')
        sys.exit(1)

    os.makedirs(PUZZLE_DIR, exist_ok=True)

    solved   = _load_solved_ids()
    existing = _existing_ids()
    skip_ids = solved | existing

    print(f'Downloading puzzles from Lichess (target: {TARGET}) …')
    print(f'Skipping {len(skip_ids)} already-known puzzle IDs.')

    candidates: list[dict] = []
    rows_checked = 0

    req = urllib.request.Request(PUZZLE_URL, headers={'User-Agent': 'ZeroFish/1.0'})
    with urllib.request.urlopen(req, timeout=60) as resp:
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(resp) as reader:
            text_stream = io.TextIOWrapper(reader, encoding='utf-8')
            csv_reader  = csv.DictReader(text_stream)

            for row in csv_reader:
                rows_checked += 1
                if rows_checked % 10000 == 0:
                    print(f'  … scanned {rows_checked:,} rows, '
                          f'found {len(candidates)} candidates', flush=True)

                puzzle_id = row.get('PuzzleId', '').strip()
                if puzzle_id in skip_ids:
                    continue

                moves = row.get('Moves', '').strip().split()
                if len(moves) != 2:
                    continue  # not a 1-move puzzle

                trigger_uci, solution_uci = moves

                # Skip promotions — no promotion sub-screen in puzzle mode
                if len(solution_uci) == 5:
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

                if len(candidates) >= COLLECT:
                    break

    if not candidates:
        print('No matching puzzles found.')
        sys.exit(1)

    sample = random.sample(candidates, min(TARGET, len(candidates)))
    print(f'Sampled {len(sample)} puzzles from {len(candidates)} candidates '
          f'(checked {rows_checked:,} rows).')

    # Merge with existing (non-solved) puzzles
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


if __name__ == '__main__':
    main()
