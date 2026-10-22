# 06. A game with no question

**Played:** 21 October, 21:56, from White's right-hand corner, network on, changed squares only,
with the rules of LESSONS sections 13 and 15.

1.e4 e5 2.Nf3 f6 3.Nxe5 fxe5 4.Qh5+ g6 5.Qxe5+ Be7 6.Qxh8 Bf6 7.Qxg8+.

**Counts:** 12 `MOVE_PLAYED` lines for 13 moves (Qxh8 Bf6 came as a pair), no tap, no undo,
nothing typed, nothing wrong.

**What it shows.**
- Nf3, Qh5+ and g6 each had one candidate that cost more than the quiet position before it.
  They were applied after about six frames instead of being asked about.
- Qxe5+ was held back as "arrival unseen" and "hidden", and resolved by itself within 3 s.
- Qxh8 Bf6 took 11.5 s, with the question shown for 15 frames: two moves in flight, a lead
  between 0.17 and 0.26 against the 0.3 needed.
- fxe5 took 7.7 s with no held-back reason: probably a hand lingering over the board.
