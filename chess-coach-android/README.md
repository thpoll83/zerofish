# Chess Coach (Android)

Point your phone at a real chess board. The app works out which move was just played, asks
Stockfish what to answer, and shows the move on a digital board.

Standalone project. It shares no code with ZeroFish and can be moved to its own repository as is.

What the camera work taught us, rule by rule with the numbers and the attempts that failed,
is in [docs/LESSONS.md](docs/LESSONS.md).

## What it does

Live mode (default): set up the starting position, point the camera at the board (handheld or on
a stand) and tap Start. The app finds the board in every frame, learns what your pieces look like
from the first three frames that show the starting position, and from then on applies a move as
soon as the same move explains three consecutive frames. Frames with a hand or a shadow over the
board are ignored. When the board has not matched the tracked position for two seconds and no
single explanation wins, the most likely explanations are shown as buttons, after four seconds
including three-move sequences. The buttons keep the best-scoring explanations of the last three
seconds, so they do not change from frame to frame; tapping one applies it and resynchronises the
tracker. A move is only applied on its own when the board afterwards fits about as well as a quiet
board did before it; if it fits clearly worse, another change went unnoticed and the move is offered
as a button instead. "Type move" accepts several moves separated by spaces, such as `Nc6 Qf3 Bb4+`. The screen shows the annotated camera frame, the digital board and Stockfish's
suggestion for your side. Undo, typing a move and pausing the camera are there for corrections.

When the board is small in the picture (a tournament photo from across the table), the detector
first looks for places where many x-corners sit close together, which is what the corners between
four squares look like, and runs again on each such region at full resolution. A board small in
the frame and seen flat across a table has rows of squares only a few pixels tall at the usual
working size of 640 px, so when nothing is found the search is repeated at 1280 px, and corners
too sparse to fill cells are grouped by distance instead (a point must have three neighbours
within two cells to pass the grouping on, so stray corners on hands and chairs cannot bridge
groups). If several boards are found, the one nearest the centre of the picture is used. A weak reading, or the best rejected
candidate when there is none, is then warped to a square picture with the board seen from above
(the far ranks of a board seen flat across the table become as large as the near ones), where a
grid of nine equally spaced lines per axis is fitted to the gradient profiles and the x-corners,
snapped to the picture's lines and corners, and judged by alternation and corner support; this
repeats until the reading stops moving, and a round that reads worse than the one before (the
grid has walked a square sideways) is dropped. That is how the near edge-on tournament photos are read.

Camera controls sit on the live screen itself: a zoom slider under the viewport (from the phone's
minimum; below 1x selects the wide-angle lens on phones that expose it through zoom), a torch chip
in the row above it, and, before the pieces are learned, a lens picker when the phone lists several
back cameras. Zoom and lens are remembered. Until the game starts, a frame around the viewport
shows how well this view will work, red to green with the score as a percentage, and the status
line names the weakest point: how clearly the grid was found, how large the board is in the
picture (distance and zoom), and how clearly pieces differ from empty squares and white from
black (light, torch). Each part is a ramp between a failing and a comfortable value of what the
tracker measures anyway; the score is half the weakest part, half the average.

The playing screen is built around one square viewport, so nothing needs scrolling: it shows
the camera picture with the board's grid, or, by a toggle, the digital board. On both, the move
just played stays drawn as a green arrow until the next one, and the engine's suggestion as a
blue one; the headline says whose move it is, "Your move: White" or "Opponent's move: Black".
The per-square markers (a dot for what the camera read, a yellow ring where it is unsure) are
shown while the pieces are learned and hidden during the game, unless the switch "Show
recognition markers" in the settings is on. The camera keeps running behind the digital board. While a move is
being read (from the first second the board no longer matches the tracked position), the likeliest
explanations are drawn on the viewport as numbered arrows in distinct colours (on the camera
picture they follow the board as found) and listed right under the viewport, before any text
that could push them about, as compact rectangles framed in the colour of their arrow, with
piece symbols, in as many rows as needed, with "Other" for typing a move (SAN or UCI, several at
once). The moves of the game run in one row that scrolls sideways, the latest highlighted. The list only
grows until the move is settled, so a button keeps its place and colour; after about 3.5 s of
reading the tracker gives up on its own and asks for a tap. Tapping the square the piece went to
picks that move; when two offered sequences start with the same move, the tap narrows them down
and the next tap picks between their second moves.

The app recognises the starting position by itself when the
pieces read clearly. When they do not (black pieces on the dark squares of a glossy board), the
button "Pieces are set up" tells it that every piece stands on its starting square, and it learns
how the pieces look from the next frames regardless; "New game" starts over.

The app opens straight on the camera. One dark look on every phone: a black headline with the
logo, the app name and the state of the game ("Your move", "Learning your pieces"), drawn by the
screen rather than by the system title bar, which some phones colour as they like; the app draws
edge to edge and the header pads itself by the status-bar inset. The launcher icon, the themed
(monochrome) icon and the header logo are vector drawables written by
`app/tools/gen_launcher_icon.py` (a 4x4 board with a camera lens over it); `--sheet` renders a
preview of the mark under the circle, squircle and square launcher masks.

Settings: choose your colour, how long Stockfish may think per move, and the strength of the advice:
full strength, or a rating between 1320 and 3190 Elo (Stockfish's `UCI_LimitStrength` and
`UCI_Elo` options), so the suggestions can be pitched at the player's level.

The camera's colour reaches the tracker (luma at full size, chroma at half, as the camera delivers
it) and the grid is always found on luma, which works on every board. The pieces, though, may
stand out from their squares in colour rather than in brightness: a plastic roll-up board's far
rank, say, or a red board with brown and yellow pieces, where in luma the brown pieces are as
dark as the red squares and the yellow ones as light as the cream squares. While learning, the
tracker therefore tries twelve channels made from luma and chroma (each chroma plane alone and
their sums and differences with luma), reads the starting position through each with the square
sampler, and keeps luma unless luma fails outright (pieces do not clear the empty squares) and a
channel reads them clearly; a channel that merely read a little better on the learning frame
lost a game on a wooden board under changing light. Luma that reads the position but leaves a
square hidden behind a piece reading as clearly as a piece (by 0.05 or more) would fit soft
thresholds, so it gives way to a channel in which every piece beats every hidden square, when
one reads clearly; a near tie in luma is left alone, as on the second game video. On the red
board from a low seat the squares behind the pawns read 0.94 to 0.99 in luma against pieces
from 0.90, and 0.64 against 0.94 through the chosen channel. The chosen channel, normalised so
that white pieces read brighter than black ones, is then what the pieces are read through for
the whole game.

Colour also enters the square features themselves. Besides the luma cues (texture and brightness
of the pixels that differ from the empty-square template), every square gets a colour distance:
an empty-square chroma template per shade (per-pixel median of U and V over the 32 squares of
that shade), the light's tint fitted per shade as a plane over file and rank through the squares
believed empty (pieces stand in rows, which a fit over every square would take for a gradient),
and the fraction of the square's pixels further from the tinted template than twice the board's
own median chroma distance. Wood grain is a brightness pattern of one hue, so it stays near the
template in chroma while a piece of another hue does not. The mean chroma offset of the differing
pixels, projected on the direction from the black set to the white set, tells white from black.
The calibration learned from the starting position reads occupancy from luma texture and piece
colour from brightness, the cues proven over whole games on wooden and plastic sets, and lets the
colour cues take over per shade only where the proven cue fails to separate the two groups on the
learning frame; a cue that merely looked a little better there applied a wrong move later in a
game. On the red folding board from a low angle mid-game, by texture no cut
separates pieces from empty squares, by colour 23 of 25 pieces and 36 of 39 empty squares read
right; from White's seat after three moves, every yellow piece reads by colour and every brown
piece by texture, while the far brown pieces are too small in the chroma planes and ten empty
squares next to tall pieces read as pieces by texture, so neither cue alone separates there (an
occlusion-aware sampling window is the next step for that angle). The plastic roll-up board
reads its light squares by colour. The replay log names the cues chosen.

The grid is locked once the starting position has verified it. The grid finder, working
afresh, lands a square off or turned by a quarter now and then on a board whose frame matches
its dark squares; such a grid reads a move that was not played and misses the one that was.
Once locked, each frame first looks for the board where it was: the lock is pulled onto the
x-corners found around it (the same refinement a found grid gets, with matching radii of 0.3
square and less), and the result must still alternate and have at least 30 percent of its inner
corners on x-corners. That follows the few pixels a touch moves the phone by, cannot land a
square off or turned, and costs about an eighth of a full search (29 ms against 237 ms per
1280 px frame on a desktop JVM), which is what makes the frame rate. The full search runs only
when tracking fails (the camera moved further, a hand covers the corners). A found grid within
0.35 squares of the lock nudges it by a fifth of the difference; one further away disputes it:
the frame is read through the lock but settles nothing ("Hold still, the board moved"), and
the same new grid seen three frames in a row while the board is not seen at the lock becomes
the lock. The orientation is never chosen again, as a board does not turn by a quarter between
two frames; a frame without any grid is read through the lock for up to eight frames.

Empty squares with nothing standing in front of them get their own empty picture: on quiet
frames the square's luma, gradient and chroma patches are blended (three tenths new) into a
per-square template, and the square is then read against its own picture instead of the
shade's median, so grain, a glare spot or a printed coordinate on that square no longer reads
as a piece and the square cannot flip between piece and empty without a hand. A square is
remembered only while it reads empty (below 0.2) and only when no piece stands in front of it
towards the camera: a piece's body would go into the picture, and the square would read as
occupied just when that piece moved away. The templates are dropped when the lock moves.
The one exception is a square a move has just left: it is known empty whatever it reads, so
its picture is taken on the next six settled frames regardless. That is the only chance to
learn a square that misreads when empty, such as the square nearest the camera, lit brighter
than the shade's typical square and read as a white piece by tone: once the queen's move is
applied, by the camera or by a tap, d1 reads empty from the next frame on.

Two explanations that differ only in one destination square and the square behind it in the
picture are cover twins: a queen on f3 seen from a low angle fills g4 as well, and occupancy
alone cannot tell Qf3 from Qg4. The step a piece's body covers is read from the board's
homography (straight up in the picture, mapped to the board; from a seat off to the side it
is a diagonal). A body fills the far square, never the other way round, so the far twin (Qg4
against Qf3, e4 against e3) is applied by itself only when the near square reads empty (a pawn
on e4 leaves e3 bare) or when it leads by 1.5; while the near square reads occupied the piece
may well stand there, and both are offered for the user to settle. On the game video that
turns a wrongly applied Qg4 into a question and leaves every pawn's double step automatic.

A move is confirmed by three frames in a row that read it best, each leading the first real
alternative by 0.3; an explanation that is the best one with a further move appended ("b3
Ng8" against "b3", the second ply a ghost from a flickering square) is no alternative, as it
agrees about b3. A move is applied only on a still frame: one with at most five squares
changed since the frame before (a hand carrying a piece moves six to ten, a settled board
none to two). Frames in flight still count towards the three, since in a fast game the move
is confirmed on the first still frame after the hand and a frame lost there leaves the
tracker a move behind; a queen on its way to d4 read as "e5 d5" for three frames in a row
before that. Measured both ways, with taps only when asked and with taps six frames after an
offer shows: video 1 follows 14 moves by itself and 4 by a tap, or 15 and 3, with none wrong.

The offers are single moves, the first move of each explanation, since the user confirms one
move at a time and the next is read from the new position; and they stay until a move is
applied, by the camera or by the user. On a still board that flickers, buttons that came and
went could not be tapped. The replay harness taps the right offer eight frames (two seconds)
after it shows, as a player who confirms every unsure move does, rather than only when the
tracker gives up and asks; in this fast game every delay compounds, and that is the behaviour
measured. Six frames took moves the tracker was about to apply by itself (11 by itself and 7
taps on video 1); at eight it follows 15 by itself with 3 taps, and the same at ten or twelve.

A frame counts as a hand or a shadow over the board, or a misread grid ("Hold still"), when it
reads much worse than the board usually does: more unsure squares than usual by ten, or a best
explanation costlier than the usual quiet reading by ten, where "usual" is measured on the learning
frame and follows quiet frames slowly. A board whose pieces are hard to tell from its squares
therefore reads unsure on every frame without being blocked.

The square readings of each frame are blended with the readings so far (60% the new frame, 40%
the blend), since a piece cannot change between two frames unless a hand came in between; a
square that reads as a piece in one frame and empty in the next is noise, not a move. A hand
over the board resets the blend.

No piece classifier is needed because the game always starts from the known position and only
occupancy and piece colour change. Castling, en passant, captures and promotions are matched
through the move generator.

## How the board is found

Pure Kotlin, no OpenCV:

1. Downscale to 640 px, Sobel edges, weighted Hough transform, peak lines.
2. Each line is walked in the image; lines are weighted by how long they are supported by edges
   and by how often the edge polarity flips along them. A grid line flips light/dark every
   square, a piece silhouette or a table edge does not, so piece edges count for little.
3. Lines split into two families by direction. Each family proposes vanishing points by pairwise
   voting. A projective transform sends the vanishing line to infinity, after which the grid lines
   of a family are parallel and equally spaced again, and nine equally spaced lines are fitted.
4. Candidate grids are scored by how many detected lines they coincide with, penalised for a
   strong line one square outside the board (a shifted grid), and verified by the light/dark
   alternation of the squares measured on each square's border ring (where piece bases rarely
   reach) including the ring of squares outside the board, which must not alternate.
5. The best grid is refined by snapping its 18 lines to detected lines and refitting the
   homography by least squares.

Orientation comes from the dark a1 rule plus the known position (and the rotation used last time).

The starting position is judged with the squares hidden behind the pieces counted as empties,
and, where that fails, without them: from a low seat behind White the third rank lies in the
pawns' bodies and reads as occupied whatever stands there (e3, f3, g3 at 0.94 to 1.00 on the
red board), which made every cue look as if it failed and the view quality read 0.28. Those
squares still count when the thresholds are set, so that they read below them as far as the
pieces allow; left out, the thresholds fell until every hidden square read as a piece. The
learned frame from the owner's first debug bundle is in the test set as `red_4`: it now reads
0.63, learns by itself, and every square reads right.

## Debug log

The app keeps a log of what the tracker saw and decided (on by default; Settings > Debug log)
in its own files, no permission needed: one line per frame in the replay harness's format
(status, message, the best explanations with their costs, the offers, the unsure count, the
grid corners), and the camera frame itself, as the tracker saw it, whenever something was
decided: the pieces learned, a move applied, a question asked, an offer added, the grid moved,
a tap, a typed move or an undo; plus every twentieth frame as a sample. At most 400 frames are
kept. "Share debug bundle" zips the lot for sending; the frames show the board and whatever is
around it, so look before sharing. The bundle replays through the harness like a video. When
the app starts it logs Android's reason for its previous exit (`LAST EXIT`: a crash, a crash in
native code, the system freeing memory, or the user), as the log of a run that crashed ends
without a word.

## Depth benchmark

An experiment (Settings > Depth benchmark): it times a monocular depth model, Depth Anything V2
Small (Apache-2.0), and Chesscog's network on all 64 squares, on the last camera frame through
ONNX Runtime, on the CPU and with XNNPACK. It shows the median time per frame, the time to set
each one up, how closely the outputs agree and the depth map itself, each line as soon as it is
known. The depth model, 99 MB, is downloaded once from the converter's GitHub release and
checked against its SHA-256; that download is the only use of the internet permission. The
results, the frame and the depth map go into the debug log. Depth replaced the luma occupancy
reading in an offline test on the game videos (see docs/LESSONS.md, section 10) and helped only
when it ran on every frame. On the owner's Pixel 8 Pro it takes 1.77 s per frame on the CPU and
2.0 s with XNNPACK, so it stays out of the tracker. NNAPI was timed too and is left out now: 12.9
s per frame, and with half precision it never finished preparing and the app died soon after.

## Square classifier (Chesscog)

An experiment, on by default in this build (Settings > Square reader): Chesscog's occupancy
network (Georg Wölflein, [github.com/georg-wolflein/chesscog](https://github.com/georg-wolflein/chesscog),
MIT licence, from the paper "Determining Chess Game State from an Image", Journal of Imaging
2021) decides which squares hold a piece while the game is tracked. It is a ResNet-18 trained on
about 5,000 rendered boards from many angles and lights; it reads a 100 by 100 crop of each
square plus half a square around it, from the board warped to a top-down view with the camera's
side at the bottom (`ChesscogCrops`, sampled straight from the frame through the homography).
Brightness and colour still tell white from black, and the pieces are still learned from luma.
The model is converted to ONNX at build time (`tools/chesscog_to_onnx.py`, which checks the
download's SHA-256 and the export against PyTorch) and run through ONNX Runtime; a build without
Python and PyTorch leaves it out and reads the squares as before, while CI refuses to.

Only squares whose patch changed since their last reading are read again, with their
neighbours (the crop takes in half of each), plus four more in turn every frame, and the whole
board on the first still frame after a hand has been over it: comparing patches with the ones
at the last reading alone missed pieces that had moved, and applied "c3 cxd4" for "c4 dxc4".
"Read every square on every frame" reads all 64 each time, about four times the work. The debug
log records per frame how many squares were read and how long it took.

On the game videos, with the replay harness (moves by itself / taps / wrong):

| Reader | Video 1, tap when asked | Video 1, tap after 2 s | Video 2 |
|---|---|---|---|
| luma (without the network) | 16 / 2 / 0 | 14 / 4 / 0 | 4 / 1 / 0 |
| network, changed squares | 16 / 2 / 0 | 15 / 3 / 0 | 4 / 1 / 0 |
| network, every square | 17 / 1 / 0 | 17 / 1 / 0 | 5 / 0 / 0 |

These include the rule below on hidden squares, which costs the network one move by itself on
video 1 and keeps it from applying 2.f3 for 2.Nf3 from a corner seat (red_6 to red_8).

On the desktop JVM the 64 crops take about 130 ms to make and the network about 300 ms on four
cores; with changed squares only, about 16 squares are read per frame on average. The depth
benchmark times the network on all 64 squares on the phone too.

## Hidden squares and the cover map

Which squares a piece's body falls onto in the picture comes from the board's homography
(`CoverMap`): along each of its cover steps, straight along the dominant axis and, from a seat
off to the side, the diagonal as well. An occupied reading on such a square counts less (behind
a pawn 0.6, behind a knight, bishop or rook 0.5, behind a queen or king 0.35; 1.0, 0.8 and 0.65
two squares on). Until now only the square straight behind a piece along the files counted.
From White's right-hand corner the owner's pieces lean towards the h-file: after 1.e4 e5 2.Nf3
the bishop on f1 covers the empty g1 and the king e1 the occupied f2, so g1 read 1.00 occupied,
f2 0.75, and 2.f3 was applied by a lead of 0.5. Two explanations whose positions differ only on
squares right behind a piece taller than a pawn cannot be told apart by occupancy, whatever the
lead says; the tracker now offers both instead of applying one. Turning each crop for the
network along the lean was tried and dropped: the network was trained on crops aligned with
the board's grid and misread 10 to 11 squares per frame instead of 2 to 4.

## When a move is only offered

Three cases end in a question rather than an applied move. A move whose destination reads
empty (below 0.5) is offered with every other legal move of the piece that left. A move the
user took back after the tracker applied it is only offered from that position again. With
the network on, a piece whose square reads below 0.1 for 14 frames in a row counts as gone,
and the tracker asks where it went. On the owner's board the network read a knight back on
c3 as empty, and before these rules Nf6+ was applied three times, twice right after an undo.

## Reading the squares

Each square is sampled through the homography on the half facing away from the camera, where
the piece in front hides least. An "empty square" template per shade is built from the photo
itself as the per-pixel median over the 32 squares of that shade (pieces never cover more than
half of them at any pixel). The fraction of pixels that differ from the template gives occupancy;
whether they are brighter or darker gives the piece colour. A square brighter than its shade's
template all over, by more than a piece is allowed to shift it, and without a single edge in it,
is a square catching the light, not a piece (a piece brings edges, and a dark piece cannot
brighten a square): the whole shift is taken as lighting and the square reads empty. That is
the square nearest the camera on the game video (d1, 0.89 by tone and no edges once the queen
had left) and two squares of the third rank on the red board, which had made luma fail there.
Squares with a piece standing between them and the camera are weighted down, and squares that
changed since the last scan support the candidate move that touches them.

How much a hidden square's reading counts depends on what hides it: behind a pawn it keeps
0.6 of its weight (and all of it two squares on), behind a knight, bishop or rook 0.5 (0.8),
behind a queen or king 0.35 (0.65); the weight is the lower of the two positions a candidate
compares, so a candidate cannot buy credibility with its own pieces. Only an "occupied" reading
is discounted that way: a body in front can make a square read as occupied, never as empty, so
a square expected to hold a piece and reading bare counts in full. From a low seat behind White
the king's body fills e2 after 1.e4, and the move is read from the pawn on e4 and the bare
e3; with e2 trusted the first move of the red-board game was never seen.

One cue reads first (luma: pixels of another tone, or edges, whichever says more), and where
that fails on a shade, the larger of the luma and the colour reading per square is tried
before colour alone: on the red folding board yellow pieces on cream squares are invisible to
the luma cues (a2 reads 0.20) and plain to the colour cue (0.97), brown pieces on the same
squares the reverse, so neither cue alone separates and the larger of the two does. The other
cues stand by as backups: the tone fraction, the edge fraction and
the colour distance each get their own threshold per shade on the learning frame, and a backup
is trusted only where it splits the starting position's pieces from its empty squares cleanly,
by a gap of at least 0.08 (0.04 for edges) and 2.5 times the noise, and edges only when the
pieces' edges reach 0.1 (flat test pieces at 0.06 fitted a threshold so low that an empty
square's jitter passed for a piece). When the first reading is
unsure (between 0.3 and 0.7), the confident backups decide if they agree; when it is confident
and a trusted backup contradicts it, the square keeps its side but weakly (0.4 or 0.6), so the
move search leans on the other squares. A black piece on a dark square is empty by tone and a
piece by edges.

Tips: even light without hard shadows, a matte board, and an angle of 40 degrees or steeper.
At low angles tall pieces hide the squares behind them; the confirm screen then lists alternatives.

## Stockfish

The engine is the official Stockfish 17.1 source, fetched by CMake at build time and compiled
with the NDK for arm64. A small JNI bridge runs the UCI loop on a thread and talks to it over
pipes. The two NNUE network files (about 80 MB) are downloaded by Gradle into the app assets and
loaded through the `EvalFile` / `EvalFileSmall` options. The engine uses up to 4 threads and
64 MB hash and reports 3 lines (MultiPV).

## Build

Requirements: Android Studio Ladybug or newer with SDK 36, NDK and CMake 3.22 installed through
the SDK Manager, internet access during the first build (Stockfish sources and networks).

```
cd chess-coach-android
./gradlew :core:test          # pure-Kotlin rules, vision and UCI tests, no SDK needed
./gradlew :app:assembleDebug  # needs the Android SDK + NDK
```

Install `app/build/outputs/apk/debug/app-debug.apk` on a 64-bit phone (Android 8.0+).

The square classifier needs Python 3 with `torch`, `torchvision`, `onnx` and `onnxruntime`
during the build (the CPU build of torch is enough:
`pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu` and
`pip install onnx onnxruntime`); without them the app is built without it. Set `PYTHON` to
choose the interpreter.

To build with ARMv8.2 dot-product instructions (about 30% faster search on 2018+ phones), add
`-DSTOCKFISH_DOTPROD=ON` to `externalNativeBuild.cmake.arguments` in `app/build.gradle.kts`.

## Layout

```
core/   pure Kotlin: chess rules (move generation, SAN, FEN), grid detector, homography,
        square sampling and classification, move inference, UCI parsing. Unit-tested with
        perft, a synthetic renderer of boards with pieces seen from changing viewpoints, and
        44 photographs of real boards (core/src/test/resources/boards, see NOTICE.md there),
        five of them of the owner's own board from every side, four of a glossy travel set whose
        black frame is as dark as its squares, three of a red folding board whose pieces are as
        dark and as light as its squares, and ten crops of club, tournament
        and event boards, most mid-game and seen across the table: the grid must be found within 2.5% of the
        labelled corners on every one of them, the starting position must be read with the right orientation from eight, a wooden
        middlegame from one more, and detection must stay under 2 s per photo. A 33 s passage of a real game video (136 frames at 360x640,
        core/src/test/resources/video) is replayed through the live tracker with a simulated
        user: no move may be applied that was not played, and every move played must be followed
        or offered as a button. Set CHESS_FRAMES_DIR to a folder of frames (ffmpeg -vf fps=4) to
        replay a whole video; CHESS_REPLAY_TRUTH="e4 c5 ..." adds the simulated user and prints
        how many moves were followed by the tracker itself, how many needed a tap, and how many
        were wrong.
app/    Android: CameraX live view with overlay, Compose UI (digital board, screens, arrows,
        theme and header), view model, Stockfish JNI bridge and CMake build; tools/ writes the
        icons.
```

## Limits

- All four board edges must be in the picture. Hands, shadows or strong lighting changes lower
  confidence. Unclear moves are offered for a tap, and any move can be typed.
- The scanner was tuned on synthetic scenes and 22 real photos from one public set; other
  boards may need threshold adjustments in `core/.../vision/Calibration.kt` or `GridDetector.kt`.
  Black pieces on dark squares seen from a low angle give the weakest readings; a board whose
  squares carry a strong wood-grain print is read by colour instead of texture, which needs
  pieces of a different hue than the squares.
- Promotions are assumed to be to a queen; type the move for an underpromotion.
- Threefold repetition is not detected.
- A fatal engine error (for example a missing network file) terminates the process, as Stockfish
  calls `exit()` in that case.
