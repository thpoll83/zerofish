# Chess Coach (Android)

Point your phone at a real chess board. The app works out which move was just played, asks
Stockfish what to answer, and shows the move on a digital board.

Standalone project. It shares no code with ZeroFish and can be moved to its own repository as is.

## What it does

1. Setup: choose your colour and how long Stockfish may think per move.
2. Calibration (once per session, phone fixed on a stand):
   - photograph the empty board and tap its four corners (a1, h1, h8, a8),
   - photograph the starting position with all 32 pieces.
   The app learns, per square shade, how an empty square, a white piece and a black piece look.
3. Game: after your opponent moves, tap "Scan board". The app classifies every square as empty,
   white or black, then finds the legal move (or two-move sequence, in case you forgot to scan
   once) whose result matches best. You confirm with one tap, Stockfish analyses, and the
   digital board shows the suggested move with an arrow. Tap "I played Nf3" once you have moved
   it on the real board, or scan again.

No piece classifier is needed because the game always starts from the known position and only
occupancy and piece colour change. Castling, en passant, captures and promotions are matched
through the move generator. Any scan can be corrected by typing the move (SAN or UCI).

## Side angles

The four tapped corners define a full perspective transform, so the board may be photographed
from above or from the side. The app detects which board edge is nearest the camera (the one
that appears longest) and reads each square on the half facing away from the camera, where the
piece in front hides the least. The scan screen draws the warped grid, the patch read per square
and a marker per square (white, black, green dot for empty, yellow ring for unsure) over the photo
so you can see what was recognised, and the digital board shows the inferred position.

Tips: even light without hard shadows, a matte board, and an angle of 45 degrees or steeper.
Low angles make tall pieces hide the squares behind them.

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
core/   pure Kotlin: chess rules (move generation, SAN, FEN), homography, square sampling,
        calibration, move inference, UCI parsing. Unit-tested with perft and a synthetic
        side-view board renderer.
app/    Android: CameraX capture, Compose UI (photo overlay, digital board, screens),
        view model, Stockfish JNI bridge and CMake build.
```

## Limits

- The phone must not move between calibration and scans. If it does, use "Re-calibrate camera".
- Hands, shadows or strong lighting changes during a scan lower confidence. The confirm screen
  lists alternatives, and any move can be typed.
- Promotions are assumed to be to a queen; type the move for an underpromotion.
- Threefold repetition is not detected.
- A fatal engine error (for example a missing network file) terminates the process, as Stockfish
  calls `exit()` in that case.
