# Chess Coach (Android)

Point your phone at a real chess board. The app works out which move was just played, asks
Stockfish what to answer, and shows the move on a digital board.

Standalone project. It shares no code with ZeroFish and can be moved to its own repository as is.

## What it does

1. Setup: choose your colour, how long Stockfish may think per move, and the strength of the
   advice: full strength, or a rating between 1320 and 3190 Elo (Stockfish's `UCI_LimitStrength`
   and `UCI_Elo` options), so the suggestions can be pitched at your son's level.
2. Photograph the board with all 32 pieces on their starting squares, from above or from your
   seat. The app finds the board by itself and learns, per square shade, how an empty square, a
   white piece and a black piece look in your light. A check screen shows the grid it found and a
   marker per square so you can see that everything was recognised.
3. Game: after your opponent moves, tap "Scan board" and take a photo. The phone does not need to
   stay in place. The app finds the board again, classifies every square as empty, white or black,
   and picks the legal move (or two-move sequence, in case you forgot to scan once) whose result
   matches best. You confirm with one tap, Stockfish analyses, and the digital board shows the
   suggested move with an arrow. Tap "I played Nf3" once you have moved it on the real board.

No piece classifier is needed because the game always starts from the known position and only
occupancy and piece colour change. Castling, en passant, captures and promotions are matched
through the move generator. Any scan can be corrected by choosing an alternative or typing the
move (SAN or UCI). If the board is not found in a photo, you can tap its four corners instead.

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
        22 photographs of real boards (core/src/test/resources/boards, see NOTICE.md there):
        the grid must be found within 2.5% of the labelled corners on 20 of them, the
        starting position must be read from one, a wooden middlegame from another, and
        detection must stay under 2 s per photo.
app/    Android: CameraX capture, Compose UI (photo overlay, digital board, screens),
        view model, Stockfish JNI bridge and CMake build.
```

## Limits

- All four board edges must be in the photo. Hands, shadows or strong lighting changes lower
  confidence. The confirm screen lists alternatives, and any move can be typed.
- The scanner was tuned on synthetic scenes and 22 real photos from one public set; other
  boards may need threshold adjustments in `core/.../vision/Calibration.kt` or `GridDetector.kt`.
  Black pieces on dark squares seen from a low angle give the weakest readings.
- Promotions are assumed to be to a queen; type the move for an underpromotion.
- Threefold repetition is not detected.
- A fatal engine error (for example a missing network file) terminates the process, as Stockfish
  calls `exit()` in that case.
