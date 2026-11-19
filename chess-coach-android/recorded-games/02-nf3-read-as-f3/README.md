# 02. Nf3 read as f3

**Played:** 21 October, 17:43, from White's right-hand corner. 1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.d3
Nf6 5.Nc3 O-O.

**What the app recorded:** 2.f3. The log's `BUNDLE` line shows it: `1. e4 e5 2. f3 Nc6 ...`.
The moves after it were recorded from that wrong position.

**Why.** From that corner every body leans towards the h-file in the picture. The bishop on f1
covered the empty g1 (read 1.00) and the king on e1 covered f2, where the pawn still stood
(0.75). g1 counted in full, so f3 beat Nf3 by 0.5, over the margin of 0.3.

**What came of it.** The cover map and the rule that asks when only squares behind a piece taller
than a pawn decide (LESSONS section 12). `game.pgn` has the game as played.
