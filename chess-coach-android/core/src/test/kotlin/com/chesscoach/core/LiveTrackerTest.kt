package com.chesscoach.core

import com.chesscoach.core.chess.Board
import com.chesscoach.core.chess.Color
import com.chesscoach.core.vision.LiveTracker
import com.chesscoach.core.vision.Pt
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class LiveTrackerTest {
    private val view = listOf(Pt(70.0, 560.0), Pt(730.0, 570.0), Pt(610.0, 150.0), Pt(190.0, 140.0))

    private fun frame(board: Board, seed: Int, jitter: Double = 0.0, hand: Pt? = null) =
        SyntheticScene.render(
            view.map { Pt(it.x + jitter * (seed % 3 - 1), it.y + jitter * ((seed * 7) % 3 - 1)) },
            board.occupancy(), 800, 640, brightness = 1.0 + 0.03 * (seed % 2), seed = seed, hand = hand, handRadius = 90.0,
        )

    @Test
    fun learnsFromStartThenFollowsMoves() {
        val t = LiveTracker(framesToConfirm = 3, framesToLearn = 3)
        var b = Board.start()
        // a few frames with the board being set up (the far pawns missing) must not count as the start
        val halfSetUp = Board.fromFen("rnbqkbnr/8/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        repeat(2) { assertEquals(LiveTracker.Status.WAITING_FOR_START, t.process(frame(halfSetUp, it)).status) }
        // starting position, handheld jitter: learned after three frames
        var learned = false
        for (i in 0 until 5) {
            val r = t.process(frame(b, 10 + i, jitter = 4.0))
            if (r.status == LiveTracker.Status.LEARNED) { learned = true; break }
            assertEquals(LiveTracker.Status.LEARNING, r.status, r.message)
        }
        assertTrue(learned, "did not learn")
        assertEquals(LiveTracker.Phase.TRACKING, t.phase)
        // hand over the board while moving: ignored
        val handFrame = t.process(frame(b, 20, hand = Pt(400.0, 350.0)))
        assertTrue(handFrame.status == LiveTracker.Status.UNSTABLE || handFrame.applied.isEmpty(), handFrame.message)
        // e4 appears; applied on the third agreeing frame
        b = b.play(b.parseMove("e4")!!)
        var applied: List<String> = emptyList()
        for (i in 0 until 5) {
            val r = t.process(frame(b, 30 + i, jitter = 3.0))
            if (r.applied.isNotEmpty()) { applied = r.applied.map { it.uci() }; break }
        }
        assertEquals(listOf("e2e4"), applied)
        assertEquals(b, t.board)
        // steady frames afterwards do nothing
        repeat(3) { assertTrue(t.process(frame(b, 40 + it, jitter = 3.0)).applied.isEmpty()) }
        // reply e5, then Nf3: each move must be applied within five frames, except that e5
        // and e6 are cover twins (the pawn on e5 fills e6 in the picture): there the move
        // must be offered within five frames and is applied by a tap
        for (san in listOf("e5", "Nf3", "Nc6", "Bb5")) {
            b = b.play(b.parseMove(san)!!)
            val log = ArrayList<String>()
            var done = false
            for (i in 0 until 5) {
                val r = t.process(frame(b, 50 + 10 * log.size + i, jitter = 3.0))
                log += "${r.status}:${r.message}"
                if (t.board == b) { done = true; break }
                if (san == "e5") {
                    val offered = r.suggestions.firstOrNull { it.sans == listOf("e5") }
                    if (offered != null) { t.accept(offered); done = t.board == b; break }
                }
            }
            assertTrue(done, "$san not applied within 5 frames: $log")
        }
    }

    /**
     * The glossy travel set seen from White's far side: its black pieces on dark squares read
     * as empty, so the starting position is not recognised by itself. Once the user confirms
     * that the pieces are set up, the tracker learns from the frames anyway.
     */
    @Test
    fun learnsFromAConfirmedStartWhenThePiecesReadPoorly() {
        val photo = ReplayHarness.load(javaClass.getResourceAsStream("/boards/travel_1.jpg")!!)
        val tracker = LiveTracker(framesToConfirm = 3, framesToLearn = 3)
        // the photo may read well enough to be taken for the start by itself (the squares behind
        // the pieces no longer count against it); if not, the user's word must do
        val first = tracker.process(photo).status
        if (first == LiveTracker.Status.WAITING_FOR_START) {
            repeat(2) { assertEquals(LiveTracker.Status.WAITING_FOR_START, tracker.process(photo).status) }
            tracker.confirmStart()
            val statuses = (1..3).map { tracker.process(photo).status }
            assertEquals(listOf(LiveTracker.Status.LEARNING, LiveTracker.Status.LEARNING, LiveTracker.Status.LEARNED), statuses)
        } else {
            assertEquals(LiveTracker.Status.LEARNING, first)
            val statuses = (1..2).map { tracker.process(photo).status }
            assertEquals(listOf(LiveTracker.Status.LEARNING, LiveTracker.Status.LEARNED), statuses)
        }
        assertEquals(Board.start(), tracker.board)
    }

    @Test
    fun offersSuggestionsWhenItCannotDecideAndAcceptsThePick() {
        val t = LiveTracker(framesToConfirm = 3, framesToLearn = 2)
        val b0 = Board.start()
        repeat(2) { t.process(frame(b0, it)) }
        assertEquals(LiveTracker.Phase.TRACKING, t.phase)
        // Three plies happen before the camera gets a clean look (Nf3 Nf6 Ng5): no two-move
        // explanation fits, so after a couple of seconds suggestions must appear, and after a
        // little longer the three-move search must find the truth and offer its first move.
        // Once that is tapped, the other two are read from the new position.
        // The tracker may apply the first two by itself (they explain most of the board) and
        // read the third from there, or offer them one move at a time; either way the truth
        // must be reached within a few seconds, with every offer a single move, and a tap
        // taken whenever the right move is among the offers.
        var b = b0
        val truth = listOf("Nf3", "Nf6", "Ng5")
        for (san in truth) b = b.play(b.parseMove(san)!!)
        val log = ArrayList<String>()
        var taps = 0
        for (i in 0 until 48) {
            if (t.board == b) break
            val r = t.process(frame(b, 200 + i, jitter = 2.0))
            log += "${r.status}:${r.message} ${r.suggestions.map { it.description }}"
            assertTrue(r.suggestions.all { it.moves.size == 1 }, "offers must be single moves: ${r.suggestions.map { it.description }}")
            val plies = (t.board.fullmoveNumber - 1) * 2 + (if (t.board.sideToMove == Color.BLACK) 1 else 0)
            val expected = truth.getOrNull(plies)
            r.suggestions.firstOrNull { it.description == expected }?.let { t.accept(it); taps++ }
        }
        assertEquals(b, t.board, "the three moves were not read: $log")
        println("three plies at once: reached with $taps taps")
        // after accepting, a quiet board is quiet again
        repeat(3) { assertEquals(LiveTracker.Status.TRACKING, t.process(frame(b, 300 + it, jitter = 2.0)).status) }
    }

    /**
     * After the user takes back a move the tracker applied, the camera still shows the same
     * board: the move must come back as a button, never be applied again by itself. On the
     * owner's board a knight read on the wrong square was applied three times in a row.
     */
    @Test
    fun doesNotApplyAnUndoneMoveAgain() {
        val t = LiveTracker(framesToConfirm = 3, framesToLearn = 2)
        val b0 = Board.start()
        repeat(2) { t.process(frame(b0, it)) }
        assertEquals(LiveTracker.Phase.TRACKING, t.phase)
        val b1 = b0.play(b0.parseMove("e4")!!)
        var applied = false
        for (i in 0 until 5) if (t.process(frame(b1, 10 + i, jitter = 2.0)).applied.isNotEmpty()) { applied = true; break }
        assertTrue(applied, "e4 was not applied")
        // the user undoes it
        t.setBoard(b0)
        var offered: com.chesscoach.core.vision.Candidate? = null
        for (i in 0 until 20) {
            val r = t.process(frame(b1, 30 + i, jitter = 2.0))
            assertTrue(r.applied.isEmpty(), "e4 applied again after the undo: ${r.message}")
            offered = r.suggestions.firstOrNull { it.description == "e4" } ?: offered
        }
        assertTrue(offered != null, "e4 was not offered after the undo")
        // a tap still applies it
        t.accept(offered!!)
        assertEquals(b1, t.board)
    }

    @Test
    fun needsAgreementBeforeApplying() {
        val t = LiveTracker(framesToConfirm = 3, framesToLearn = 2)
        val b0 = Board.start()
        repeat(2) { t.process(frame(b0, it)) }
        assertEquals(LiveTracker.Phase.TRACKING, t.phase)
        val b1 = b0.play(b0.parseMove("d4")!!)
        val b2 = b0.play(b0.parseMove("e4")!!)
        // alternating frames never reach three in a row
        for (i in 0 until 6) t.process(frame(if (i % 2 == 0) b1 else b2, 100 + i))
        assertEquals(b0, t.board)
    }
}
