# 03. The knight that went back to c3

**Played:** 21 October, 18:25, from White's right-hand corner, every square read on every frame.
Lines 1 to 323 of the log are the whole of game 02; this game is the second run, from line 361
(27 moves applied, 5 taps, 4 undos).

1.e4 g6 2.d4 Bg7 3.Nc3 Nf6 4.e5 Ng4 5.Qxg4 d6 6.Qh4 dxe5 7.dxe5 Bxe5 8.Be3 a6 9.Rd1 a5
10.Rxd8+ Kxd8 11.Nf3 Bd6 12.Ng5 a4 13.Nxf7+ Ke8 14.Nxh8 a3 15.Nd5 axb2 16.Nc3.

**What the app recorded:** 16.Nf6+, applied three times (frames 494, 511 and 523). The owner undid
it twice, at 2086.9 s and 2102.3 s.

**Why.** The network read d5 as empty and c3 as empty too (0.04 to 0.19 over 30 frames): the c2
pawn's head fills the bottom of c3's crop and the knight stands in its top-left corner. Every
knight move from d5 then cost about the same as "no move", and Nf6+ won on flicker.

**What came of it.** Three rules (LESSONS section 13): a move that fills a square reading
empty is asked about, an undone move is never applied again by itself, and a piece whose
square reads plainly empty for 14 frames is asked about. A luma referee for the network was
tried and dropped (section 14).

Seven frames that show a hand or an arm at the edge are not kept (118, 124, 131, 457, 463, 467
and 494). `game.pgn` has the game with the move the owner played.
