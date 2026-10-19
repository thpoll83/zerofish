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
     * The red folding board with brown and yellow pieces, mid-game, from a low angle: by luma
     * texture the pieces cannot be told from the empty squares at all (the wood grain of the
     * squares reads as texture), by the colour distance to the empty squares they can, and the
     * chroma offset tells white from black pieces better than brightness. The position was read
     * from the photo square by square; a few squares behind tall pieces are covered by them.
     */
    @Test
    fun redBoardReadsByColourNotTexture() {
        val img = TestImages.load(javaClass.getResourceAsStream("/boards/red_2.jpg")!!)
        // corners a1, h1, h8, a8 of the labelled grid
        val geometry = BoardGeometry(listOf(Pt(227.0, 778.0), Pt(963.0, 397.0), Pt(532.0, 128.0), Pt(3.0, 248.0)))
        val occupancy = IntArray(64)
        for (sq in listOf("a8", "a7", "b8", "b7", "c8", "c7", "e8", "d5", "f7", "g8", "g7", "h8", "h7", "g5", "c1", "d1")) occupancy[square(sq)] = 2
        for (sq in listOf("a2", "c2", "f3", "f1", "h2", "h1", "g3", "g4", "h4")) occupancy[square(sq)] = 1
        val f = BoardLocator.locate(img, geometry.corners, Calibration.default(), occupancy, 0, allowRotation = false).features
        val m = Calibration.Margins.of(f, occupancy)
        println("red_2: $m")
        assertTrue(m.occupancyTexture < 0.0, "texture was expected to fail on this board: $m")
        val byColour = assertNotNull(m.occupancyChroma)
        assertTrue(byColour > m.occupancyTexture + 0.3, "the colour distance should separate pieces far better than texture: $m")
        // most pieces and most empty squares must be on the right side of 0.4 by colour
        val pieces = (0 until 64).filter { occupancy[it] != 0 }.count { f.chromaFraction!![it] >= 0.4 }
        val empties = (0 until 64).filter { occupancy[it] == 0 }.count { f.chromaFraction!![it] < 0.4 }
        println("red_2: by colour, %d of 25 pieces and %d of 39 empty squares read right".format(pieces, empties))
        assertTrue(pieces >= 20 && empties >= 34, "by colour $pieces of 25 pieces and $empties of 39 empties read right")
        assertTrue((m.colourChroma ?: 0.0) > m.colourLuma, "chroma should tell white from black better than brightness: $m")
        // no colour shift of the luma channel is needed once the colour cues are in the features
        println("red_2: shift " + ColorProjection.choose(img, geometry, occupancy))
    }

    /**
     * The plastic roll-up board (club_9): by luma texture the far rank's pieces do not clear the
     * empty squares, by colour distance they do. The tracker learns the starting position, and
     * the calibration reads occupancy from colour on at least one shade.
     */
    @Test
    fun rollUpBoardLearnsByColour() {
        val img = TestImages.load(javaClass.getResourceAsStream("/boards/club_9.jpg")!!)
        val tracker = com.chesscoach.core.vision.LiveTracker(framesToConfirm = 3, framesToLearn = 3)
        val statuses = (1..3).map { tracker.process(img).status }
        assertTrue(statuses.last() == com.chesscoach.core.vision.LiveTracker.Status.LEARNED, "statuses $statuses")
        val cal = assertNotNull(tracker.calibration)
        println("club_9: " + cal.notes.joinToString(" | ") + "; shift ${tracker.projection}")
        assertTrue(cal.occFromChroma.any(), "occupancy was expected to be read from colour on the roll-up board: ${cal.notes}")
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
