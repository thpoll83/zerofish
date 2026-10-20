# Test photos

The `board_*.jpg` files are photographs of real chess boards taken from the `test/in` folder of
<https://github.com/maciejczyzewski/neural-chessboard> (GNU GPL v3, copyright 2017-present
Maciej A. Czyzewski and contributors), downscaled to at most 1000 px and renamed
(`board_12.jpg` was `test/in/12.jpg`, `board_cc7.jpg` was `test/in/cc7.jpg`). They are used only
as unit-test inputs.

The `own_*.jpg` files were photographed by the repository owner on the board the app is meant
for (wooden board with a frame about one square wide, wooden pieces, room light): overhead with
White on the far side (own_1), from a corner (own_2), from the side with White on the right
(own_3), and from White's seat (own_4, own_5). All five show the starting position.

`ground_truth.txt` holds, per photo, the pixel positions of the board's four outer corners in
cyclic order (any rotation). The values were produced by the detector and checked by eye against
overlays; they are regression anchors with a tolerance, not survey-grade measurements.

The `club_*.jpg` files are crops of photographs the repository owner took at a chess club and at
a public tournament, cut down to the board and the table around it so that no person is
recognisable. They show vinyl tournament boards with plastic pieces (club_1, club_2) and a wooden
tournament board with a dark printed frame (club_3 to club_5), all in the middle of a game, from
across the table at a low angle.

`club_6` to `club_8` are crops of photographs taken at a public event in a shopping centre: a
wooden tournament board with wooden pieces on a dark table, seen from the side at a low angle,
with the board small in the original frame. `club_9` is a plastic roll-up board with the starting
position, seen flat across a table in a tournament hall. `club_10` is a wooden board on the floor
seen from above. All are cut down to the board and the table around it so that no person is
recognisable.

The `travel_*.jpg` files were photographed by the repository owner: a small magnetic travel set
with a glossy black plastic frame that is as dark as its dark squares, with the starting position,
from four viewpoints (White far and near, from above and from a low angle), on a desk next to a
laptop. Downscaled to 1000 px.

The `red_*.jpg` files are photographs the repository owner took of a folding board with red and
cream squares, a red frame, and brown and yellow plastic pieces, on a dinner table: red_1 and
red_2 in the middle of a game from a low angle across the table, cropped so that no person is in
them; red_3 after 1.e4 d6 2.d3 e5 3.Nc3 from White's seat (position known from the moves).
In grayscale the brown pieces are as dark as the red squares and the yellow pieces as light as
the cream ones, which makes it the hardest board of the set to read.
