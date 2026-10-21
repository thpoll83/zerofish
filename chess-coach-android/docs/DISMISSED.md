# What we tried and dropped, and why

Every entry here was built or measured, then dropped. Each says what it was, what the
measurement showed, and where the details are (section numbers refer to docs/LESSONS.md). The
test set is the same for all: 46 photographs with corner ground truth, two game videos with the
moves known, synthetic scenes, and the owner's debug bundles from a Pixel 8 Pro. "By itself /
taps / wrong" counts moves the tracker followed alone, moves settled by a tap, and moves applied
wrongly; a wrong move is the one result that is never acceptable.

## Finding the board

| Tried | What happened | Instead |
|---|---|---|
| Lines only: Sobel edges, Hough lines, vanishing points, equal spacing | Found most boards, but a square off or turned by a quarter on the rest, and nothing in the line evidence told them apart (2) | Candidate grids ranked by the x-corners they sit on |
| Hessian saddle response for x-corners | Fired on slanted edges and thin lines (2) | A ring test of 16 samples |
| A fresh grid search on every frame | Landed a square off now and then on a board whose frame matches its dark squares; each such frame read a move nobody played (2) | Lock the grid at learning and track it |
| Lock following a new detection by 0.5 | The lock chased misreads (2) | 0.2 |
| Grouping sparse x-corners without a neighbour rule | Stray corners on hands and chairs joined into a window the size of the picture (2) | A point needs three neighbours within two cells |

## Reading a square

| Tried | What happened | Instead |
|---|---|---|
| Switch to a colour channel whenever it reads a little better | Lost a game on a wooden board under changing light (3) | Luma stays unless it fails, or squares behind pieces read like pieces in it |
| Switch only when luma fails outright | On the red board luma passed once glare was handled, and the channel that read the board cleanly was never chosen (3) | The rule above |
| A cue chosen on a small margin at learning | Twice applied a wrong move later in a game (5) | A colour cue takes over per shade only where luma does not separate |
| A per-shade lighting plane through the empty squares | Broke a start-position photo and flipped the cue choice on video 1: near the camera there are no empty squares at the start to fit through (3) | The lit-square rule: bright all over, no edges |
| A uniform brightness shift without the edge and brightness conditions | Missed dark pieces on dark squares that fill their window (3) | The same lit-square rule |
| Learning every quiet square's own empty picture | Absorbed pieces not yet seen, which then read empty for good (3) | Only squares that read below 0.2, plus squares a move just vacated |
| Flat backup cues trusted at a small gap | Flat synthetic pieces at 0.06 fitted an edge threshold inside an empty square's jitter (3) | Gap 0.08 (edges 0.04), 2.5 times the noise, piece edges at least 0.1 |
| Leaving squares behind pieces out of the threshold fit | The threshold dropped until every hidden square read as a piece (5) | They count in the fit and are left out only of the start check |

## Reading a move

| Tried | What happened | Instead |
|---|---|---|
| Discounting hidden squares in both directions | Threw away the bare e2 that proves the pawn left after 1.e4; failed the synthetic test (4) | Only an "occupied" reading behind a piece is discounted |
| One weight (0.5) behind any piece | From a low seat the king's body fills e2 after 1.e4, and "no move" tied with e4 (4) | Weight by height: pawn 0.6, minor or rook 0.5, queen or king 0.35 |
| Discount straight along the files only | From the corner seat the bishop on f1 covered g1 in the picture; 2.f3 was applied for 2.Nf3 (12) | The cover map from the homography, diagonal included |
| A blanket margin of 0.6 between cover twins | Halved the moves followed by themselves (4) | The far twin needs its near square empty, or a lead of 1.5 |
| A twin margin of 0.8 | Blocked b3 and b4 on video 1 (4) | Same rule |
| Counting squares behind pawns as hidden for the hidden-rival rule | Made almost every opening move a question, Nf3 against Ne2 among them (12) | Only squares behind pieces taller than a pawn |
| Ignoring frames with a hand in flight | Video 1 fell from 14 moves by itself to 6, with 22 wrong: a move confirmed a frame late left the tracker a move behind (4) | In-flight frames count; only the confirming frame must be still |
| Applying a lone move that fits worse than the quiet baseline after three agreeing frames, on the strength of a three-move search | Applied d5 on video 1 three frames earlier, while the hand's shadow still lay on the board; the vacated squares' pictures were learned from a disturbed board and the next moves needed taps (luma 14/4 became 11/7) (15) | The same search after six agreeing frames |
| A second move of a pair needs a gain over its first move alone (1.0, then 0.7) | Meant to stop "Re1 Rf8" (gain 0.45) from being applied for a plain Re1. Real pairs on video 1 gain 0.9 to 1.7. At 1.0 luma fell to 9 moves by itself with 9 taps; at 0.7 luma lost two moves (14/4) and the network reading changed squares applied one wrong move (13/5/1) (15) | Not used. The undo of a wrongly applied move is remembered, so it does not come back |
| Stricter quiet baselines: a fallback cost, recent frames only, no pairs without a baseline, five frames for pairs | Each helped one frame and left the tracker a move behind on others, after which a pair read from two moves ahead was applied (4) | Median of the last 8 settled frames; three agreeing frames when there is none |
| Asking after 8 unexplained frames | Buttons came and went before they could be tapped (6) | 14 frames, offers from the 3rd |
| Offers that changed from frame to frame, two-move buttons | Could not be tapped on a flickering board; pairs were misread and mis-tapped (6) | Single moves, kept in the order first seen |

## Depth as the reader

| Tried | What happened | Instead |
|---|---|---|
| A full 3D mesh of the board | Needs many viewpoints or a depth sensor; a phone on a stand gives one view, and ARCore's depth needs the phone to move (10) | Depth from one frame, pieces dropped onto the board |
| Depth blended with luma, or deciding only its confident squares | Needed more taps than depth alone (10) | Not used |
| Depth with the hidden-square discount | Threw the evidence away twice: the footprints already put a body on its own square (10) | Not used |
| Depth threshold from the start position (0.0085) | Below the stray points that piece edges spill onto neighbours (10) | A fixed 0.06, a lead only |
| Calibrating depth on the first tracking frame | On video 2 the hand was on its way to e4: 3 to 8 wrong moves (10) | Calibrate on the learning frame |
| Depth on every frame in the app | Only on every frame did it beat luma (17 against 15 on video 1). The phone takes 1.77 s per frame on the CPU and 2.0 s with XNNPACK, about nine times the budget (10) | Not in the tracker |
| Depth through NNAPI | 12.9 s per frame; with half precision it never finished preparing, and the app died soon after (10) | NNAPI left out of the benchmark |
| Depth as the referee on squares nothing hides | On free squares it read 3.9% of pieces as empty and 6.8% of empties as pieces, against 1.0% and 1.6% for the network; behind a piece it called half the empty squares occupied (14) | Not used |

## The network

| Tried | What happened | Instead |
|---|---|---|
| A whole-board network trained on overhead photos | Reported 73% of squares right, overhead only; useless from a low seat (11) | Chesscog's per-square occupancy network |
| Re-reading a square only when its patch changed | Applied "c3 cxd4" for "c4 dxc4" twice on video 1: a moved piece was still read where it had stood (11) | All 64 on the first still frame after a hand, plus 4 squares in turn |
| Crops turned along the way pieces lean | 10 to 11 misreads per frame instead of 2 to 4: the network was trained on crops aligned with the grid (12) | Grid-aligned crops |
| Shifting the crop to catch an off-centre piece | The knight on c3 never read above 0.43 at shifts up to 20 pixels (13) | Rules for when the network misses a piece |
| Luma as the referee, from 0.5: where the network reads empty and luma occupied, the square is unknown | Luma read d5 as occupied after the knight left, and c3 as occupied before the move (the c2 pawn's head): both squares became unknown, and the "piece seems gone" question never came (14) | Tried from 0.8 |
| Luma as the referee, from 0.8 | On the bundle it put Nc3 first among the offers. On video 1 it applied a wrong move with changed-squares reading (15 by itself, 3 taps, 1 wrong; 11, 7 and 1 when tapping after two seconds) and cost 1 to 2 moves by itself with every square read (14) | Not used: the network decides alone, and the rules of section 13 catch a missed piece |

## Tooling

| Tried | What happened | Instead |
|---|---|---|
| A replay harness that taps the moment an offer shows | Took moves the tracker was about to apply: 11 by itself and 7 taps where a person's reaction gives 15 and 3 (7) | Tap after 2 seconds, and a tap-only-when-asked run |
| A harness parameter after the `log` lambda | Every trailing lambda bound to the new parameter: replays ran, logged nothing, and the suite still passed (12) | New parameters go before `log` |
| A benchmark that waits on every accelerator | Stuck at "NNAPI, half precision: preparing" with nothing shown (10) | Results line by line, 2 minutes per setup, NNAPI dropped |
