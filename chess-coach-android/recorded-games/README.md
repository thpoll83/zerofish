# Recorded games

Debug bundles from the owner's phone (Pixel 8 Pro, Android 17, red folding board, yellow and
brown pieces), kept as reference. Each folder holds the whole `log.txt`, the frames something
was decided on, a `README.md` saying what the game shows, and where a game was played, its
moves as `game.pgn`.

| Folder | When | What it shows | Moves by itself / taps / undos |
|---|---|---|---|
| [01-first-move-red-board](01-first-move-red-board) | 20 Oct, 18:25 | The first bundle. The starting position scored 0.28 for view quality and the first move was missed (LESSONS sections 3, 4, 5) | no move read |
| [02-nf3-read-as-f3](02-nf3-read-as-f3) | 21 Oct, 17:43 | 2.Nf3 applied as 2.f3 from White's right-hand corner (LESSONS section 12) | 10 / 0 / 0 |
| [03-knight-back-to-c3](03-knight-back-to-c3) | 21 Oct, 18:25 | 16.Nc3 read as Nf6+ three times, undone twice (LESSONS section 13). Its log starts with all of 02 | 27 / 5 / 4 (second run) |
| [04-self-game-with-questions](04-self-game-with-questions) | 21 Oct, 20:15 | A 25-move game: 15 questions, mostly one candidate, and a false "Re1 Rf8" (LESSONS section 15) | 33 / 15 / 1 |
| [05-benchmark-crash](05-benchmark-crash) | 21 Oct, 19:20 | The depth benchmark that hung on NNAPI half precision (LESSONS section 10). Log only | none |
| [06-self-game-clean](06-self-game-clean) | 21 Oct, 21:56 | 7 moves, none asked, none undone, with the rules of sections 13 and 15 in | 12 / 0 / 0 |

The counts are `MOVE_PLAYED`, `TAP` and `UNDO` lines of the log. A `MOVE_PLAYED` line can hold
two moves.

## How to read a log

One line per frame: the time since the app started, the frame number, the status, the message,
the best explanations with their costs (`top:`), the offers, the number of unsure squares, the
milliseconds the network took, and the four corners of the grid. Lines for decisions have no
frame number: `TAP`, `UNDO`, `TYPED`, `NEW GAME`, `BUNDLE` (the game so far, as the app has
it, wrong moves included). The log of a run is appended to the one before it, so a later folder
can start with the whole of an earlier one: lines 1 to 323 of 03 are 02.

`docs/DECISION_FLOW.md` says what each status and message means.

## What is kept, and what is not

The frames are cropped to the board with a margin of 2% at the sides and below and 10% above
(the far pieces stand there), scaled to at most 640 pixels and saved as JPEG. Only the frames
of these kinds are kept: learned, confirm (the user said the start is set up), played, tap,
asked and undo. Offer frames are left out because they are taken while the hand is still over
the board, and frames that show a hand or an arm at the edge of the crop are dropped (seven in
game 03).

## The full recordings

The original zips, the two game videos and the photos shared while the reader was built are in
the private repo [thpoll83/zerofish-recordings](https://github.com/thpoll83/zerofish-recordings)
(Git LFS, 153 MB in 21 files, each with its size and SHA-256 in its `MANIFEST.md`). They show
the owner's home and hands, so that repo stays private. `tools/fetch_recordings.sh` clones it
next to this repo, downloads all files or the ones named (`tools/fetch_recordings.sh
../zerofish-recordings "videos/*"`) and checks them against the manifest. A new game goes into
both places: the zip into the private repo's `bundles/`, the archived folder here.

The cropped frames are for looking at, not for replaying: the replay harness needs whole
frames, which the full recordings below have. To add a game, share the debug bundle from the app and run

    python3 tools/archive_bundle.py BUNDLE.zip recorded-games/07-name --skip <frames with a hand>

then look at the frames before committing them.
