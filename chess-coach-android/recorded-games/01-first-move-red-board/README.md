# 01. The first bundle, the first move missed

**Played:** 20 October, 18:25, from White's side. No move was read.

**What it shows.** The log of the first run with the debug log on. From 3187 s to 3219 s and
beyond the app stays on "Board found. Set up the starting position" with a view quality of
0.26 to 0.39 ("Pieces hard to tell from empty squares: more light from above"). The red board's
squares behind the pawns read 0.94 to 0.99 in luma, almost as strongly as the pieces, so the
start check failed. The same frames now score 0.63.

**What came of it.** The hidden-square weights by piece height, the check that leaves out
squares behind the pieces, and the colour channel choice for the red board (LESSONS sections 3
to 5). Three frames are kept: the start position (confirm and learned).
