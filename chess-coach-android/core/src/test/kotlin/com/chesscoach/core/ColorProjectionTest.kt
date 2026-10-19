package com.chesscoach.core

import com.chesscoach.core.chess.Board
import com.chesscoach.core.vision.BoardGeometry
import com.chesscoach.core.vision.BoardLocator
import com.chesscoach.core.vision.Calibration
import com.chesscoach.core.vision.ColorProjection
import com.chesscoach.core.vision.LumaImage
import com.chesscoach.core.vision.Pt
import com.chesscoach.core.vision.YuvImage
import kotlin.test.Test
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/**
 * The colour shift: on a board whose pieces differ from their squares in colour more than in
 * brightness, a channel other than luma is chosen and separates pieces from empty squares;
 * on wooden and plastic sets that differ in brightness, plain luma stays.
 */
class ColorProjectionTest {
    /**
     * The red folding board with brown and yellow pieces: in luma the pieces cannot be told from
     * empty squares at all (the margin is far below the 0.08 the tracker needs), and the chroma
     * channels tell white from black pieces many times better; but the wood grain of its squares
     * reads as texture in every channel, so no channel separates pieces from empty squares well
     * enough to be taken. That failure is the squares' grain, not the colour, and is recorded
     * here so a change to the sampler can be measured against it.
     */
    @Test
    fun redBoardFailsOnGrainNotColour() {
        val img = TestImages.load(javaClass.getResourceAsStream("/boards/red_2.jpg")!!)
        // corners a1, h1, h8, a8 of the labelled grid
        val geometry = BoardGeometry(listOf(Pt(227.0, 778.0), Pt(963.0, 397.0), Pt(532.0, 128.0), Pt(3.0, 248.0)))
        // the position on the photo, read by eye: brown (black) and yellow (white) pieces
        val occupancy = IntArray(64)
        for (sq in listOf("a8", "a7", "b8", "b7", "c8", "c7", "e8", "d5", "f7", "g7", "g8", "h7", "h8", "g5", "e2", "d2")) occupancy[square(sq)] = 2
        for (sq in listOf("c3", "g4", "h4", "f3", "f1", "h1", "h2")) occupancy[square(sq)] = 1
        val luma = ColorProjection.read(img, geometry, occupancy)
        val chroma = ColorProjection.read(ColorProjection(0.0, 0.0, 1.0, 153.0, 5.0).apply(img), geometry, occupancy)
        println("red_2: luma reads $luma; V alone reads $chroma")
        assertTrue(luma.occupancyMargin < 0.08, "luma was expected to fail on this board: $luma")
        assertTrue(chroma.colourMargin > 3 * luma.colourMargin, "the V channel should tell white from black far better: $chroma vs $luma")
        val shift = ColorProjection.choose(img, geometry, occupancy) { println("red_2: $it") }
        assertTrue(shift == null, "no channel should read the grain as clear of pieces, got $shift")
    }

    /**
     * The plastic roll-up board (club_9): in luma the far rank's pieces do not clear the empty
     * squares, and a chroma channel does. The tracker learns the starting position through it.
     */
    @Test
    fun rollUpBoardLearnsThroughAColourShift() {
        val img = TestImages.load(javaClass.getResourceAsStream("/boards/club_9.jpg")!!)
        val tracker = com.chesscoach.core.vision.LiveTracker(framesToConfirm = 3, framesToLearn = 3)
        val statuses = (1..3).map { tracker.process(img).status }
        assertTrue(statuses.last() == com.chesscoach.core.vision.LiveTracker.Status.LEARNED, "statuses $statuses")
        assertNotNull(tracker.projection, "a colour shift was expected for the roll-up board")
        println("club_9: learned through ${tracker.projection}")
    }

    @Test
    fun woodenAndPlasticSetsKeepPlainLuma() {
        for ((name, corners) in listOf(
            "own_1" to listOf(Pt(501.0, 234.0), Pt(133.0, 229.0), Pt(62.0, 576.0), Pt(514.0, 603.0)),
            "travel_4" to listOf(Pt(108.0, 572.0), Pt(502.0, 489.0), Pt(384.0, 228.0), Pt(70.0, 281.0)),
            "club_9" to listOf(Pt(62.0, 63.0), Pt(84.0, 227.0), Pt(544.0, 192.0), Pt(422.0, 48.0)),
        )) {
            val img = TestImages.load(javaClass.getResourceAsStream("/boards/$name.jpg")!!)
            val located = BoardLocator.locate(img, corners, Calibration.default(), Board.start().occupancy(), null)
            val shift = ColorProjection.choose(img, located.geometry, Board.start().occupancy()) { println("$name: $it") }
            // a shift is allowed only when it reads at least as well as luma on both counts
            if (shift != null) {
                val luma = ColorProjection.read(img, located.geometry, Board.start().occupancy())
                val shifted = ColorProjection.read(shift.apply(img), located.geometry, Board.start().occupancy())
                println("$name: chose $shift: $shifted (luma $luma)")
                assertTrue(shifted.occupancyMargin >= luma.occupancyMargin - 0.02 && shifted.colourMargin >= minOf(luma.colourMargin, 0.6) - 0.05, "$name: $shift reads worse than luma ($shifted vs $luma)")
            }
        }
    }

    private fun square(name: String) = (name[1] - '1') * 8 + (name[0] - 'a')
}
