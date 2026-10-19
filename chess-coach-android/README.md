# Chess Coach (Android)

Point your phone at a real chess board. The app works out which move was just played, asks
Stockfish what to answer, and shows the move on a digital board.

Standalone project. It shares no code with ZeroFish and can be moved to its own repository as is.

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
as a button instead. "Type move" accepts several moves separated by spaces, such as `Nc6 Qg4 Bb4+`. The screen shows the annotated camera frame, the digital board and Stockfish's
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
recognition markers" in the settings is on. The camera keeps running behind the digital board. When the tracker
cannot tell which move was played, the possible moves are drawn on the viewport as numbered
arrows in distinct colours (on the camera picture they follow the board as found), and tapping the
square the piece went to picks that move; when two offered sequences start with the same move,
the tap narrows them down and the next tap picks between their second moves. The same moves are
listed as buttons under the viewport, with "Other" for typing a move (SAN or UCI, several at
once).

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

## Reading the squares

Each square is sampled through the homography on the half facing away from the camera, where
the piece in front hides least. An "empty square" template per shade is built from the photo
itself as the per-pixel median over the 32 squares of that shade (pieces never cover more than
half of them at any pixel). The fraction of pixels that differ from the template gives occupancy;
whether they are brighter or darker gives the piece colour. Squares with a piece standing between
them and the camera are weighted down, and squares that changed since the last scan support the
candidate move that touches them.

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

To build with ARMv8.2 dot-product instructions (about 30% faster search on 2018+ phones), add
`-DSTOCKFISH_DOTPROD=ON` to `externalNativeBuild.cmake.arguments` in `app/build.gradle.kts`.

## Layout

```
core/   pure Kotlin: chess rules (move generation, SAN, FEN), grid detector, homography,
        square sampling and classification, move inference, UCI parsing. Unit-tested with
        perft, a synthetic renderer of boards with pieces seen from changing viewpoints, and
        41 photographs of real boards (core/src/test/resources/boards, see NOTICE.md there),
        five of them of the owner's own board from every side, four of a glossy travel set whose
        black frame is as dark as its squares, and ten crops of club, tournament
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
  Black pieces on dark squares seen from a low angle give the weakest readings.
- Promotions are assumed to be to a queen; type the move for an underpromotion.
- Threefold repetition is not detected.
- A fatal engine error (for example a missing network file) terminates the process, as Stockfish
  calls `exit()` in that case.
