# Test photos

The `board_*.jpg` files are photographs of real chess boards taken from the `test/in` folder of
the MIT-licensed project <https://github.com/maciejczyzewski/neural-chessboard> (copyright
2017-present Maciej A. Czyzewski and contributors), downscaled to at most 1000 px and renamed
(`board_12.jpg` was `test/in/12.jpg`, `board_cc7.jpg` was `test/in/cc7.jpg`). They are used only
as unit-test inputs.

The `own_*.jpg` files were photographed by the repository owner on the board the app is meant
for (wooden board with a frame about one square wide, wooden pieces, room light): overhead with
White on the far side (own_1), from a corner (own_2), from the side with White on the right
(own_3), and from White's seat (own_4, own_5). All five show the starting position.

`ground_truth.txt` holds, per photo, the pixel positions of the board's four outer corners in
cyclic order (any rotation). The values were produced by the detector and checked by eye against
overlays; they are regression anchors with a tolerance, not survey-grade measurements.
Photos listed under `# known failures` are side views where the detector currently fails.
