# What we learned building the board reader

This file records what the camera work taught us, in the order the problems came up, with
the numbers that decided each rule and the attempts that failed. The README says what the
app does now; this says why it does it that way, so that nobody has to rediscover a dead
end. Every claim below was measured on the test set: 46 photographs of real boards with
corner ground truth, two game videos with the moves known, a committed 124-frame passage of
one of them, synthetic scenes, and the owner's debug bundles from the phone.

## 1. What the app must get right

The user plays on a real board with the phone on a stand. The app follows the moves and
shows Stockfish's advice. The user confirms or corrects every move the app is unsure about,
so a question costs a tap and nothing else. A move applied wrongly costs the whole game:
the tracker then explains every later frame from a wrong position, and the user has to
notice, undo and retype. Every rule below is tuned to that asymmetry. Fewer taps is nice;
zero wrong moves is the requirement.

The replay harness measures both. It replays a video through the tracker and plays the
user: when the tracker asks, it taps the offer that matches the true next move; it counts
moves followed by the tracker alone, moves settled by a tap, and moves applied wrongly.
Every change is judged on the same four runs:

| Run | What it tests |
|---|---|
| Video 1 (18 plies, wooden board, low seat off to the side) | tap only when asked, and tap two seconds after an offer shows |
| Video 2 (5 plies, wooden board, Black's side) | tap two seconds after an offer shows |
| Passage test (124 frames of video 1, committed) | regression in the normal suite |
| Owner's bundle (red folding board, Pixel 8 Pro) | the first move of a real game on the hardest board |

The last pushed state: video 1 follows 15 moves by itself with 3 taps (14 and 4 when the
user taps after two seconds), video 2 follows 4 with 1 tap, nothing wrong anywhere, and the
bundle's first move reads by itself.

## 2. Finding the board

**Lines alone are not enough.** The first detector took Sobel edges, Hough lines, two line
families, vanishing points and an equal-spacing fit. It found most boards and was a square
off or turned by a quarter on the rest, and nothing in the line evidence told the two apart.
What told them apart was x-corners: the points where four squares meet. A ring test (16
samples around a pixel; a strong second harmonic, weak first and fourth harmonics, centre
near the ring's mean) fires there and not on slanted edges or thin lines, which the Hessian
saddle response did. Candidate grids within 3 points of the best on lines and alternation
are refined and the one whose inner corners sit on the most x-corners wins. T junctions,
where the frame meets two squares, are not x-corners: the ring response subtracts the
difference between opposite samples to exclude them.

**Look again from above.** A board seen flat across a table has far ranks a few pixels
tall. Warping the first reading to an 800 px square with two squares of margin and running
the detector on that picture makes every square the same size. The new reading is kept only
when it beats the seed's own board on the same picture, and a round that reads worse than
the one before is dropped (on one photo the second round walked a square sideways). In the
rectified view the grid is nearly axis-aligned, so a dedicated fit searches nine equally
spaced lines per axis over offset and spacing, tries every placement inside the picture,
snaps to the x-corners by iterated least squares, and counts x-corners on a lattice's
boundary against it: the real board meets its frame in T junctions, while a grid one square
off has a row of real inner corners along one edge.

**Small boards in crowded frames.** The region finder clusters x-corners in 16 px cells at
640 px. A small, foreshortened board puts nothing in those cells. When the usual pass
proposes no region, the search runs again at 1280 px with 32 px cells, and when corners are
too sparse to fill cells they are grouped by distance, with the rule that a point needs three
neighbours within two cells. Without that rule stray corners on hands and chairs bridged
groups into a window the size of the picture.

**Lock the grid, then track it.** Detecting afresh on every frame landed a square off now
and then on a board whose frame matches its dark squares, and each such frame read a move
that was not played. Once the starting position has verified a grid, the tracker locks it.
Each later frame first pulls the lock onto the x-corners around it (matching radii of 0.3,
0.2 and 0.15 squares) and verifies by alternation and corner support (both at least 0.3).
That follows the few pixels a touch moves the phone, cannot land a square off, and costs an
eighth of a full search (29 ms against 237 ms per frame on the desktop JVM). The full search
runs only when tracking fails. A grid found elsewhere becomes the lock only after three
frames in a row with the board not seen at the lock. A follow factor of 0.5 toward a new
detection was catastrophic (the lock chased misreads); 0.2 is right. The orientation is
never chosen again after learning.

**Open problem.** Before the pieces are learned, the red board's grid sometimes lands with
corners outside the picture. Learning fixes it because the start position verifies the
grid, but the frames before that are chaos. Not yet addressed.

## 3. Reading one square

**Empty-square templates from the photo itself.** The per-pixel median over the 32 squares
of a shade is that shade's empty picture: pieces never cover more than half of them at any
pixel. The fraction of a square's pixels that differ from the template by more than a
quarter of the dark-to-light tone difference is the tone cue; the fraction with strong
gradients is the edge cue; the occupancy reading is the larger of tone and 2.5 times edges.
A black piece on a dark square has no tone difference and plenty of edges; a white piece on
a light square the reverse. Brightness of the differing pixels at the 70th percentile (so
shadows do not drag a light piece down) tells white from black.

**Colour.** Every square also carries a chroma distance from a per-shade chroma template,
with the light's tint fitted per shade as a plane over file and rank through the squares
believed empty. Wood grain is a brightness pattern of one hue and stays near the template; a
piece of another hue does not. On the red folding board yellow pieces on cream squares read
0.20 by tone and 0.97 by colour, brown pieces on the same squares the reverse, so neither
cue alone separates and the larger of the two per square does. The chroma offset of the
differing pixels, along the direction from the black set to the white set, tells the sets
apart seven times better than brightness on that board.

**Reading the pieces through a colour channel.** The grid is always found on luma. The
pieces may be read through one of twelve channels (each chroma plane alone, and sums and
differences with luma), chosen on the learning frames and kept for the whole game. The
plastic roll-up board learns only through such a channel. The rule for switching went
through three versions:

1. Switch whenever a channel reads a little better. Lost a game on a wooden board under
   changing light.
2. Keep luma unless it fails outright (pieces do not clear the empty squares by 0.08) and a
   channel reads clearly (0.15). Safe, but on the red board luma failed only because of
   glare (section 3, lit squares), and once that was fixed luma passed and the channel that
   read the board cleanly was no longer chosen.
3. Current: luma also gives way when a square hidden behind a piece reads as clearly as a
   piece by 0.05 or more (its thresholds would be soft, section 5) and a channel exists in
   which every piece beats every hidden square. A near tie is left alone, which keeps luma
   on video 2, where a channel with a clean fit on the learning frame applied "d3 e5" three
   times for a plain d3. On the red board the squares behind the pawns read 0.94 to 0.99 in
   luma against pieces from 0.90, and 0.64 against 0.94 through the chosen channel.

**Backup cues.** The tone fraction, the edge fraction and the colour distance each get
their own threshold per shade on the learning frame, and a backup is trusted only where it
splits the start position cleanly: a gap of 0.08 (0.04 for edges) and 2.5 times the noise,
and for edges the pieces' edges must reach 0.1. Flat synthetic pieces at 0.06 fitted an edge
threshold so low that an empty square's jitter passed for a piece. An unsure first reading
(0.3 to 0.7) takes the side the confident backups agree on; a confident one that a trusted
backup contradicts keeps its side but weakly (0.4 or 0.6), so the move search leans on the
other squares.

**A square's own empty picture.** Squares that read empty with nothing in front of them get
a per-square template (luma, gradient, chroma) blended three tenths per quiet frame, and are
read against it instead of the shade's median. Only squares that read empty (below 0.2) are
remembered: an early version blended every quiet square and absorbed pieces that had not
been seen yet, which then read as empty for good. The one exception is a square a move has
just vacated: it is known empty whatever it reads, so its picture is taken on the next six
settled frames regardless. That was the only way to learn d1 on video 1 (next paragraph)
once the queen's move had been applied; d1 then read 0.14 instead of 0.60.

**Lit squares.** The square nearest the camera catches the light. On video 1, d1 after the
queen had left read 0.89 by tone with no edge at all and a brightness 0.32 above the light
template; with the queen on it, it had read 0.60 by tone with 0.18 edges. On the red board
two empty squares of the third rank read 1.00 by tone the same way, and that glare is what
made luma fail the start check there. The rule: a square brighter than its template by more
than the tolerance, all over (more than half its pixels changed, at most a fifth still
changed once the whole shift is removed), with edges below 0.02, is lighting, and the whole
shift is taken as the illumination offset. A piece brings edges, and a dark piece cannot
brighten a square. Two earlier attempts at the same problem failed: a per-shade lighting
plane fitted through the empty squares broke a start-position photo and flipped the cue
choice on video 1 (near the camera there are no empty squares at the start to fit through),
and a uniform-shift rule without the edge and brightness conditions missed dark pieces on
dark squares that fill their window.

**The sampling window.** Each square is sampled on the half facing away from the camera
(depth 0.42 to 0.92 of the square, lateral 0.22 to 0.78), where the piece in front hides
least. That is why a pawn on e4 fills e4's window while a pawn on e3 whose body reaches into
e4 covers mostly the near part that is not sampled.

## 4. Reading a move

**Cost.** Every legal move (and two-ply and, after a wait, three-ply sequences) is scored
against the readings: a square expected empty pays its occupied reading; a square expected
to hold a white piece pays its empty reading plus its "black" reading; a ply costs a fixed
penalty; squares that changed since the last scan support the moves that touch them, as
one-sided evidence. The lowest cost is the best explanation. The frame result exposes every
scored candidate, which is what the diagnostics print.

**Hidden squares.** A piece between a square and the camera hides part of it. The weight of
a hidden square's reading started at 0.5 behind any piece and 0.8 two squares on. The
owner's first move showed that is not enough: from a low seat behind White the king's body
fills e2 after 1.e4, and e2 reading occupied put "no move" level with e4. The weight now
depends on what hides the square: a pawn leaves 0.6 (and all of it two squares on), a knight,
bishop or rook 0.5 (0.8), a queen or king 0.35 (0.65). The weight is the lower of the two
positions a candidate compares, so a candidate cannot buy credibility with its own pieces.
And only an "occupied" reading is discounted: a body in front can make a square read as
occupied, never as empty, so a square expected to hold a piece and reading bare counts in
full. The first version discounted both directions and failed the synthetic e4 test, since
it threw away the bare e2 that proves the pawn left.

**Cover twins.** Two explanations that differ only in one destination square and the square
behind it in the picture are twins: a queen on f3 seen from a low angle fills g4, and the
camera read Qg4 for the owner's Qf3 so convincingly that the game record used for the
harness had the wrong move in it until the frames were drawn with the grid on them. The step
a body covers is read from the homography (image-up mapped to the board at that square;
straight along the files from White's seat, a diagonal from a seat off to the side, with
the straight step first and the diagonal second when the other component is at least four
tenths of it). A body fills the far square, never the other way round, so the far twin is
applied by itself only when the near square reads empty or when it leads by 1.5; the near
twin at the usual margin. A blanket margin of 0.6 between twins halved the moves followed by
themselves; a twin margin of 0.8 blocked b3 and b4 on video 1; the near-square rule keeps
every pawn double step automatic and turns Qg4 for Qf3 into a question.

**Three agreeing frames, and a still one to apply.** A move is applied when it is the best
explanation on three frames in a row, each leading the first real alternative by 0.3. An
explanation that is the best one with a further move appended ("b3 Ng8" against "b3", the
second ply a ghost from a flickering square) is no alternative, as it agrees about b3.
Frames with a hand in flight (more than five squares changed since the frame before; a hand
carrying a piece changes six to ten, a settled board none to two) count toward the three,
but the frame that applies the move must be still. Ignoring in-flight frames altogether
lost the one frame a fast game cannot spare: video 1 fell from 14 moves by itself to 6, with
22 wrong, because a move confirmed a frame late left the tracker a move behind and a pair
read from a board two moves ahead was applied. With the gate only on the confirming frame,
"e5 d5" is still not applied off a queen on its way to d4.

**The quiet baseline, and the fallbacks that cascaded.** The tracker keeps the median
"no move" cost of the last eight settled frames as the quiet baseline, and applies a move
only when the board after it fits within 1.2 of that baseline; otherwise another change went
unnoticed, the move is offered, and the three-move search looks for the fuller explanation.
That held back a lone Bb4+ on video 1 when Nc6 and Qf3 had read weakly. Only settled frames
feed it: a weakly seen move would otherwise raise it. Every attempt to make it stricter
failed in fast play: a fallback to the typical cost when no baseline exists yet, a baseline
from only the most recent frames, "no two-ply explanations without a baseline", and five
agreeing frames for pairs each helped one frame and left the tracker a move behind on
several others, after which a pair read from a board two moves ahead was applied. When
there is no baseline, the move is applied on the three agreeing frames alone.

**Grid misreads count for nothing.** A frame whose best explanation still costs more than 20
(a third of the board wrong) is a misread grid or a body over the board. It is reported as
"hold still" and does not count as an unexplained frame, so the quiet frames between such
misreads feed the baseline.

## 5. Learning the pieces from the starting position

**The start check.** The tracker learns thresholds when three frames in a row look like the
starting position: the fourth-weakest piece must read above the third-strongest empty
square by 0.08 (three weak far-rank pieces and two phantom pieces are allowed), and white
must differ from black. The user can also press "Pieces are set up", and the tracker learns
from the next frames regardless; that is how the glossy travel set from White's far side
gets going.

**Hidden squares spoil the check, not the fit.** From a low seat behind White the third rank
lies in the pawns' bodies (e3, f3, g3 at 0.94 to 1.00) and counted as empties they made
every cue look as if it failed. The check now leaves out the squares hidden behind the
pieces (straight and diagonal cover steps, two squares deep) when counting them spoils it.
The thresholds themselves still fit with every middle-rank empty included: leaving the
hidden squares out lowered the threshold until every hidden square read as a piece during
the game. When the fit overlaps, the threshold sits between the two means with a scale of a
quarter of their gap, which is soft; a soft fit on the red board turned e4's lead over e3
from 0.88 into 0.47 and the move was never confirmed. That is why the channel choice in
section 3 looks at the fit's cleanliness.

**A cue that looks a little better on the learning frame is not better.** Twice a cue chosen
on a small margin applied a wrong move later in a game (a colour channel on a wooden board
under changing light, and the "texture or colour" cue when merely better rather than needed).
The colour cues take over per shade only where the luma cue fails to separate the two groups
on the learning frame.

**View quality.** Before learning, the tracker scores how clearly the grid was found, how
large the board is, and, from the learning frames, how clearly pieces differ from empty
squares and white from black, as ramps between a failing and a comfortable value; the score
is half the weakest part and half the average, and the weakest part gives the hint shown
on screen. The owner's first bundle read 0.28 (now 0.63 on the same frame).

## 6. What the user sees

**Offers must stand still.** Buttons that came and went on a flickering static board could
not be tapped. Offers are single moves (the first move of each explanation), kept in the
order first seen, and stay until a move is applied by the camera or the user. Since the
user confirms or corrects every unsure move, there is no reason to show two-move sequences
or to withdraw an offer. The move list sits in one row directly under the picture, outside
the scrolling part, so the offers cannot push it off the screen. The offered moves are
also drawn as numbered arrows on the camera picture and the digital board; a tap on the
destination square picks the move.

**Asking takes a few seconds.** The tracker asks after 14 unexplained frames (3.5 s at 4
frames per second) rather than 8; most moves resolve by themselves in that time, and the
earlier buttons vanished before they could be tapped. Offers show from the third
unexplained frame on, so a user who knows the move need not wait for the question.

**The debug bundle.** With the "Debug log" switch (on by default) the app writes one line
per frame in the replay harness's format and saves the camera frame whenever something was
decided (learned, applied, asked, offered, grid moved, tap, typed, undo) plus every
twentieth frame, at most 400 frames. "Share debug bundle" zips them. The first bundle found
both causes of the missed first move within an hour, which no amount of guessing from the
videos had.

## 7. How we diagnose a misread

The same steps found every bug above:

1. Replay the video with the harness and find the frame where the wrong move was applied or
   the right one first fell behind. The log names the candidates and their costs per frame.
2. Dump the per-square readings on that frame and a few before it, with the raw cue values
   (tone, edge, chroma, brightness), the threshold and scale, and the backups' opinions.
   The diagnostic test in the scratch harness prints exactly this.
3. Draw the detected grid on the frame with the square names, and zoom in on the squares
   whose readings contradict the truth. Twice the "truth" was wrong (Qg4 for Qf3) and the
   picture settled it.
4. Compare the same dump with and without the change. A rule that fixes the frame in
   question and changes 120 other squares' readings has changed the calibration, not the
   square; look at the calibration notes and the channel chosen.
5. Rerun all four runs of section 1 before pushing. Every rule in this file was kept only
   when none of them got worse.

Two tools make this cheap: the harness copies under the scratch directory (one Gradle
project per variant, so four replays run at once), and the replay harness's reaction time.
A harness that tapped the true move the moment it was offered took moves the tracker was
about to apply by itself and made the tracker look worse than it was (11 by itself and 7
taps at six frames, 15 and 3 at eight). Two seconds matches a person; the harness reports
both the tap-when-asked and the tap-after-two-seconds runs.

## 8. The numbers

| Rule | Value | Why that value |
|---|---|---|
| Start check margin | 0.08 | fourth-weakest piece above third-strongest empty |
| Luma gives way to a colour channel | luma fails below 0.08, or hidden squares beat pieces by 0.05; channel must read 0.15 and fit clean | video 2 kept on luma at a tie of 0.003 |
| Backup cue trust | gap 0.08 (edges 0.04), separation 2.5, piece edges at least 0.1 | flat pieces at 0.06 fitted a threshold inside the noise |
| Lit square | more than half changed, at most a fifth after the full shift, edges below 0.02, brighter only | d1: 0.89 tone, 0.000 edges |
| Own empty template | learned below 0.2, three tenths per quiet frame; vacated squares six frames regardless | unseen pieces were absorbed at higher levels |
| Hidden square weight | pawn 0.6 / 1.0, minor or rook 0.5 / 0.8, queen or king 0.35 / 0.65; occupied readings only | king's body on e2 after 1.e4 |
| Apply margin | 0.3 over the first real alternative, three frames in a row | |
| Cover twins | far twin needs the near square empty or a lead of 1.5 | 0.8 blocked b3 and b4 |
| Motion | more than 5 changed squares is a hand; confirming frame must be still | hand carrying a piece changes 6 to 10 |
| Misread frame | best explanation above 20 | a third of the board wrong |
| Grid tracking | snap radii 0.3 / 0.2 / 0.15, support 0.3, follow 0.2, relock after 3 frames | follow 0.5 chased misreads |
| Ask after | 14 unexplained frames; offers from the third | buttons vanished at 8 |
| Harness reaction | 8 frames (2 s) | 6 took moves the tracker was about to apply |

## 9. Open problems

- Grid instability before learning on the red board (corners outside the picture).
- A pawn on e3 whose body fills e4, against a pawn on e4 with the king's body on e3, from a
  low seat behind White: the readings are nearly the same, and the tracker rightly asks.
  The sampling window being on the far half of each square is the only thing that
  separates them.
- Far brown pieces on the red board are too small in the chroma planes to read by colour
  from across the table; ten empty squares next to tall pieces read as pieces by texture
  there. An occlusion-aware sampling window is the next step for that angle.
- The whole-game check still rests on two videos and one bundle. More bundles from real
  games are worth more than any further rule.

## 10. Depth as a second reader (an experiment, not in the tracker)

**The idea.** A monocular depth network turns one frame into a depth map. With the camera
pose from the board's four corners (focal length from the homography, the board plane known),
every pixel becomes a 3D point; every point standing above the board is dropped onto the board
along its normal, and the square it lands on gets the credit. That is "build a 3D model, then
see what happened" without a mesh, and it sees neither glare nor colour: d1 under the lamp reads
empty, yellow on cream reads like any piece, and the queen's body over g4 lands on f3. Full
meshes need many viewpoints or a depth sensor; a phone on a stand gives one view, and ARCore's
depth needs the phone to move.

**The model.** Depth Anything V2 Small (25 M parameters, Apache-2.0; the larger ones are
non-commercial) as ONNX, 518 by 518 input. On the desktop JVM through ONNX Runtime it takes
about 350 ms per frame on four cores, and its depth map agrees with the Python pipeline's to a
correlation of 0.999.

**Measured on the videos.** The scores were computed offline for every frame of video 1 and the
first 110 frames of video 2, then fed to the tracker in place of luma's occupancy (luma still
says white or black), through the replay harness:

| Run | Video 1 by itself / taps / wrong | Video 2 |
|---|---|---|
| luma (the tracker as it is), tap when asked | 15 / 3 / 0 | 4 / 1 / 0 |
| depth every frame, threshold 0.06, no hidden-square discount | 17 / 1 / 0 | 5 / 0 / 0 |
| the same, depth once a second | 15 / 3 / 0 | 4 / 1 / 0 |
| luma, tap after two seconds | 14 / 4 / 0 | 4 / 1 / 0 |
| depth every frame, tap after two seconds | 14 / 4 / 0 | 5 / 0 / 0 |

What decided the setting:

- **Replace, do not blend.** Averaging depth with luma, or letting depth decide only its
  confident squares, needed more taps than depth alone.
- **No hidden-square discount.** The footprints already put a body on its own square;
  discounting the squares behind it as well threw the evidence away twice.
- **A fixed threshold, not one from the start position.** Calibrated on the learning frame
  the threshold came out at 0.0085, below the stray points that edges of pieces spill onto
  neighbouring squares (0.05 to 0.2). Fixed thresholds from 0.045 to 0.15 gave the same video 1
  result; 0.1 applied one wrong move on video 2, and 0.03 never confirmed 1.e4 on the owner's
  red board, which 0.06 reads by itself. The value was chosen after seeing these runs, on two
  videos and one bundle frame: a lead, not a proven setting.
- **Calibrate on a still frame.** Calibrating on the first tracking frame of video 2, with the
  hand already on its way to e4, applied 3 to 8 wrong moves.
- **Per square, depth is no better than luma.** On settled frames of video 1 it misread 13.5%
  of squares with the start-position threshold (3.7% with thresholds chosen per rank from the
  answers), luma 11.4%, often on different squares. The move search, which compares whole
  positions, is what makes either work.

**Why it is not in the tracker.** The gain needs depth on every frame, under 200 ms on the
phone. The settings screen has a benchmark for exactly that question (see the README); until it
says yes on the owner's phone, depth stays an experiment.

## 11. A learned square reader: Chesscog's occupancy network

**Where it came from.** Wölflein and Arandjelović's Chesscog (MIT licence) reads a photo of a
board in three steps: find the board, decide per square whether it holds a piece, then name the
piece. Its occupancy network is a ResNet-18 trained on about 5,000 rendered boards at many
camera angles and lights; the crop is the square plus half a square on each side, 100 by 100
pixels, from the board warped to a top-down view with the camera's side at the bottom. Its
piece crops reach one to three squares above the square, more for squares further from the
camera, wider towards the board's edges, and mirrored on the left half so every piece leans
the same way: the same "a body falls onto the square behind" problem as the cover steps of
section 4, handled by the crop. Another suggested project, a whole-board network trained on
overhead photos only, reported 73% of squares right and was of no use from a low seat.

**Per square, unchanged, on boards it never saw.** On the 164 settled frames of video 1 it
misread 3.5% of squares, against 11.4% for the luma reading and 13.5% for the depth footprints
of section 10; most of its errors were on two squares, g8 and c7, next to pieces leaning into
them. On the owner's red board after 1.e4 it read e2 0.00, e3 0.00 and e4 1.00; its only miss
was the pawn on f2 (0.17).

**In the tracker.** Its probabilities replace luma's occupancy reading, before the smoothing;
everything else stays, the hidden-square discount included (unlike depth's footprints, the
crops do not put a body on its own square, and the discount helped). It needs no threshold:
it outputs a probability. Results are in the README; in short, reading every square on every
frame followed every move of both videos with one tap at most and nothing wrong, and reading
only changed squares came close.

**The cache that went wrong first.** Reading a square again only when its patch had changed
since its last reading (the change detector's score above 0.2, with its neighbours) applied
"c3 cxd4" for "c4 dxc4" twice on video 1: a piece that had moved was still read where it had
stood. Reading the whole board on the first still frame after a hand, and four squares in turn
on every frame, fixed it at about 16 squares per frame.

**What to watch on the phone.** The network costs about 23 billion operations for all 64
squares. The debug log records, per frame, the squares read and the milliseconds; the depth
benchmark times all 64 on each accelerator.

