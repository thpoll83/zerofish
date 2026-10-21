# How one frame is decided

The tracker (`core/.../vision/LiveTracker.kt`) handles one camera frame at a time, about 4 per
second. Each frame ends in exactly one status: NO_BOARD, WAITING_FOR_START, LEARNING, LEARNED,
UNSTABLE, TRACKING, MOVE_PLAYED or AMBIGUOUS. This page follows a frame from the camera to that
status, with every threshold the code uses. docs/LESSONS.md says why each value is what it is;
docs/DISMISSED.md lists what was tried instead and dropped.

## 1. Before the game: finding the board and learning the pieces

```mermaid
flowchart TD
    F["Camera frame (YUV)"] --> P{"Phase?"}
    P -- "LEARNING" --> G["Full grid search:<br/>lines, x-corners, look again from above"]
    G -- "no grid" --> NB1["NO_BOARD<br/>'Looking for the board'"]
    G -- "grid" --> CH["On colour frames: choose the reading channel<br/>(luma or one of 12 colour channels)"]
    CH --> SC{"Looks like the start position?<br/>4th-weakest piece above 3rd-strongest empty by 0.08,<br/>white differs from black by 0.2<br/>(or the user pressed 'Pieces are set up')"}
    SC -- "no" --> WS["WAITING_FOR_START<br/>streak reset to 0"]
    SC -- "yes" --> ST{"3 such frames in a row?"}
    ST -- "not yet" --> LR["LEARNING (n/3)"]
    ST -- "yes" --> LD["Fit thresholds per shade, lock the grid,<br/>board = start position,<br/>remember usual unsure count and usual cost"]
    LD --> LE["LEARNED<br/>'Ready. Play on the board.'"]
    P -- "TRACKING" --> T["Section 2"]
```

## 2. During the game: from the frame to the square readings

```mermaid
flowchart TD
    F["Camera frame"] --> L{"Grid lock exists?"}
    L -- "yes" --> TR["Pull the lock onto the x-corners near it<br/>(snap radii 0.3 / 0.2 / 0.15 squares)"]
    TR -- "verified" --> FO["Lock follows the board by 0.2 of the way"]
    TR -- "lost" --> FS["Full grid search"]
    FS -- "no grid for more than 8 frames" --> NB["NO_BOARD, lock dropped"]
    FS -- "grid at the lock" --> FO
    FS -- "grid elsewhere" --> AW{"Same grid elsewhere<br/>3 frames in a row?"}
    AW -- "no" --> UN1["UNSTABLE<br/>'Hold still, the board moved'"]
    AW -- "yes" --> RL["Lock moves there, square pictures forgotten"]
    FO --> LOC["Read every square in its far half<br/>(depth 0.42 to 0.92, lateral 0.22 to 0.78):<br/>tone, edges, colour against the empty pictures,<br/>lit-square rule, backup cues"]
    RL --> LOC
    LOC --> HU{"Unsure squares above<br/>max(14, usual + 10)?"}
    HU -- "yes: a hand or shadow" --> UN2["UNSTABLE<br/>'Hold still, hand or shadow over the board'"]
    HU -- "no" --> NN{"Network switched on?"}
    NN -- "no" --> SM
    NN -- "yes" --> WH{"Which squares to read again"}
    WH -- "every square on, board moved,<br/>first still frame after a hand,<br/>or no reading yet" --> A64["All 64"]
    WH -- "otherwise" --> CHG["Squares whose patch changed by more than 0.2,<br/>their neighbours, and 4 more in turn"]
    A64 --> RUN["Chesscog network (XNNPACK, 4 threads):<br/>probability of a piece per square"]
    CHG --> RUN
    RUN --> NV["Network value replaces luma's occupancy<br/>(luma still says white or black)"]
    NV --> SM["Blend with the last frames:<br/>0.6 this frame, 0.4 the blend so far"]
    SM --> MO["Moving: more than 5 squares changed by 0.5<br/>since the frame before (a hand in flight)"]
    MO --> D["Section 3"]
```

## 3. From the readings to a decision

Every legal move, and every pair of moves, is scored against the readings (section 4 of
LESSONS.md). Per square: expected empty pays `weight x occupied`; expected to hold a piece pays
`(1 - occupied)` in full plus `weight x occupied x wrong colour`. The weight is 1 for a square
nothing hides, and lower behind a piece in the picture (the cover map, from the homography): 0.6
behind a pawn, 0.5 behind a knight, bishop or rook, 0.35 behind a queen or king, and 1.0, 0.8 or
0.65 two squares on. Each ply adds 0.3. A square the change detector saw change, on which the
candidate changes nothing, adds 0.35 x its change score.

```mermaid
flowchart TD
    S["Score 'no move', every legal move, every pair"] --> BAD{"Best cost above<br/>max(20, baseline + 10)?"}
    BAD -- "yes: grid misread or a body over the board" --> UN["UNSTABLE<br/>'Hold still, cannot read the board'"]
    BAD -- "no" --> EV{"Best is a move and beats<br/>'no move' by 0.6 or more?"}

    EV -- "no: the board looks as tracked" --> Q["quiet + 1<br/>if settled: baseline and empty-square pictures update"]
    Q --> QS{"6 quiet frames in a row?"}
    QS -- "yes" --> QR["Forget the pending evidence<br/>(offers stay)"]
    QS -- "no" --> GO
    QR --> GO{"Network on and a square of the tracked position<br/>reads below 0.1 for 14 frames in a row?"}
    GO -- "yes" --> GA["Offer every legal move of that piece<br/>AMBIGUOUS 'A piece seems gone from d5'"]
    GO -- "no" --> AQ{"14 unexplained frames so far<br/>and offers on screen?"}
    AQ -- "yes" --> AM1["AMBIGUOUS<br/>'Not sure what was played'"]
    AQ -- "no" --> TQ["TRACKING<br/>'Tracking' or 'Reading the move...'"]

    EV -- "yes: something changed" --> U["unsettled + 1, quiet = 0<br/>from the 3rd such frame: offer the best 3<br/>within 1.5 of the best"]
    U --> BL{"Any block?"}
    BL --> B1["Cover twin: a rival within 1.5 differs by one destination<br/>one cover step away, the best is the far one,<br/>and the near square reads occupied"]
    BL --> B2["Hidden: a rival within 1.5 differs only on squares<br/>with weight 0.5 or less"]
    BL --> B3["Unseen arrival: a square the move fills reads below 0.5<br/>(also offers every move of the piece that left)"]
    BL --> B4["Refused: the user undid this move from this position"]
    B1 -- "blocks applying" --> M
    B2 -- "blocks applying" --> M
    B3 -- "blocks applying" --> M
    B4 -- "blocks applying" --> M
    BL -- "none" --> M{"Leads the first real rival by 0.3?<br/>(a rival that only appends a move does not count)"}
    M -- "yes and not blocked" --> PC["Same as last frame's leader? count + 1, else count = 1"]
    PC --> C3{"Count 3, and the board after the move fits<br/>within 1.2 of the quiet baseline,<br/>and this frame is still?"}
    C3 -- "yes" --> MP["MOVE_PLAYED: board updated,<br/>vacated squares re-learned for 6 frames"]
    C3 -- "count 3 but does not fit" --> MC["Offer it: 'Seeing X, but more changed'<br/>(keep looking for the fuller explanation)"]
    C3 -- "not yet" --> WT
    M -- "no, or blocked" --> WT{"14 unexplained frames?"}
    MC --> WT
    WT -- "yes" --> AM2["Offer the best 4; from frame 22 every 4th frame<br/>also search three-move sequences<br/>AMBIGUOUS 'Not sure what was played'"]
    WT -- "no" --> TR2["TRACKING<br/>'Seeing X (n/3)' or 'Maybe X or Y'"]
```

## 4. What the user does, and what it changes

```mermaid
flowchart LR
    TAP["Taps an offer, or the destination square"] --> ACC["The move is played; pending evidence,<br/>offers and quiet costs cleared"]
    TYPE["Types a move"] --> SET["setBoard: tracked position replaced,<br/>change reference dropped"]
    UNDO["Undo"] --> REF["setBoard to the position before;<br/>if the tracker had applied that move, it is refused<br/>from that position (offered, never applied by itself)"]
    CONF["'Pieces are set up'"] --> LRN["Learn from the next 3 frames<br/>even if the start check fails"]
```

## 5. Every number in one place

| Step | Value | Where |
|---|---|---|
| Start check | 4th-weakest piece above 3rd-strongest empty by 0.08; colour gap 0.2; 3 frames | `learn` |
| Grid tracking | snap radii 0.3 / 0.2 / 0.15 squares, follow 0.2, relock after 3 frames, drop after 8 without a grid | `cornersForFrame` |
| Hand or shadow | unsure squares above max(14, usual + 10) | `track` |
| Network refresh | change score 0.2, neighbours, 4 squares in turn; all 64 after a hand | `classify` |
| Smoothing | 0.6 this frame | `smooth` |
| Moving | more than 5 squares changed by 0.5 | `track` |
| Square weight behind a piece | pawn 0.6 / 1.0, minor or rook 0.5 / 0.8, queen or king 0.35 / 0.65 | `CoverMap` |
| Ply penalty | 0.3 | `MoveInference` |
| Change evidence | 0.35 x change score on untouched squares | `MoveInference` |
| Misread frame | best cost above max(20, baseline + 10) | `track` |
| A change at all | best beats "no move" by 0.6 | `minEvidence` |
| Apply margin | 0.3 over the first real rival, 3 frames, still frame | `applyMargin`, `framesToConfirm` |
| Fits the baseline | within 1.2 of the median "no move" cost of the last 8 settled frames | `applySlack` |
| Cover twins, hidden rivals | within 1.5 | `twinMargin` |
| Unseen arrival | filled square below 0.5 | `arrivalMin` |
| Piece gone | below 0.1 for 14 frames (network only) | `vanishedMax` |
| Offers | from the 3rd unexplained frame, best 3 within 1.5; at most 10 | `offer` |
| Ask | after 14 unexplained frames; three-move search from 22, every 4th frame | `framesBeforeAsking` |
| Settled | 6 quiet frames in a row | `quietFramesToSettle` |
| Empty-square pictures | learned below 0.2, three tenths per quiet frame; vacated squares 6 frames regardless | `templates` |
