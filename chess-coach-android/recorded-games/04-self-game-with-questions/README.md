# 04. A game against oneself: fifteen questions

**Played:** 21 October, 20:15, from White's right-hand corner, network on, changed squares only.

1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 d6 5.O-O Nf6 6.c3 Be7 7.Re1 O-O 8.d4 d5 9.exd5 Nxd5
10.Bxc6 bxc6 11.c4 Nb4 12.a3 Nc2 13.Qxc2 exd4 14.Nxd4 Qxd4 15.Rxe7 Bh3 16.gxh3 Qh4 17.Qe4 Qxh3
18.Nc3 g6 19.Qg2 Qxg2+ 20.Kxg2 Rae8 21.Rxc7 f5 22.Bh6 Rf7 23.Rxc6 Rd7 24.Nd5 a5 25.Nf6+.

**Counts:** 33 moves applied by the app, 15 taps, 1 undo, nothing wrong at the end.

**What it shows.**
- Eight of the fifteen questions had one candidate, read the same on every frame, that cost 1.2 to
  2.4 more than the quiet position before it (Bb5, Bxc6, exd4, Nxd4, Qe4, Rxc7 and others). The
  old rule applied a move only within 1.2 of that baseline. Fixed in LESSONS section 15.
- The others were real ties (a6 against a5, Nc2 against Nd3, both cover twins) and squares the
  network did not see (Bh3, Nd5): the rules of section 13 asking on purpose.
- 7.Re1 was applied as "Re1 Rf8" (frame 209) and the owner undid the rook move at 1517 s: f8,
  just left by the bishop, read occupied, and the rook on h8 half empty. Stays open (section 15).

`game.pgn` has the game as played.
