package com.chesscoach.core

import com.chesscoach.core.chess.Board
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
        // a few frames with the board being set up (one rank missing) must not count as the start
        val halfSetUp = Board.fromFen("rnbqkbnr/pppppppp/8/8/8/8/8/RNBQKBNR w KQkq - 0 1")
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
        // reply e5, then Nf3: each move must be applied within five frames
        for (san in listOf("e5", "Nf3", "Nc6", "Bb5")) {
            b = b.play(b.parseMove(san)!!)
            val log = ArrayList<String>()
            var done = false
            for (i in 0 until 5) {
                val r = t.process(frame(b, 50 + 10 * log.size + i, jitter = 3.0))
                log += "${r.status}:${r.message}"
                if (t.board == b) { done = true; break }
            }
            assertTrue(done, "$san not applied within 5 frames: $log")
        }
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
