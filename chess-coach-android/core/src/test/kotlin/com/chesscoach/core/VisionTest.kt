package com.chesscoach.core

import com.chesscoach.core.chess.Board
import com.chesscoach.core.chess.Move
import com.chesscoach.core.chess.Square
import com.chesscoach.core.vision.ArrayLumaImage
import com.chesscoach.core.vision.BoardGeometry
import com.chesscoach.core.vision.Calibration
import com.chesscoach.core.vision.Homography
import com.chesscoach.core.vision.MoveInference
import com.chesscoach.core.vision.NearSide
import com.chesscoach.core.vision.Pt
import com.chesscoach.core.vision.SquareSampler
import kotlin.math.abs
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class VisionTest {
    /** Trapezoid corners as seen from the rank-1 side: the near edge is wider. */
    private val sideViewCorners = listOf(Pt(40.0, 460.0), Pt(600.0, 460.0), Pt(500.0, 120.0), Pt(140.0, 120.0))
    private val overheadCorners = listOf(Pt(50.0, 50.0), Pt(450.0, 50.0), Pt(450.0, 450.0), Pt(50.0, 450.0))

    @Test
    fun homographyMapsCornersExactly() {
        val h = Homography.boardToImage(sideViewCorners)
        val expect = listOf(Pt(0.0, 0.0), Pt(8.0, 0.0), Pt(8.0, 8.0), Pt(0.0, 8.0))
        for (k in 0 until 4) {
            val p = h.map(expect[k])
            assertTrue(abs(p.x - sideViewCorners[k].x) < 1e-6 && abs(p.y - sideViewCorners[k].y) < 1e-6, "corner $k: $p")
        }
        val inv = h.inverse()
        val back = inv.map(h.map(3.5, 2.5))
        assertTrue(abs(back.x - 3.5) < 1e-6 && abs(back.y - 2.5) < 1e-6)
    }

    @Test
    fun nearSideDetection() {
        assertEquals(NearSide.RANK_1, BoardGeometry(sideViewCorners).nearSide)
        assertEquals(NearSide.NONE, BoardGeometry(overheadCorners).nearSide)
        val fromHFile = listOf(Pt(500.0, 120.0), Pt(600.0, 460.0), Pt(40.0, 460.0), Pt(140.0, 120.0))
        assertEquals(NearSide.FILE_H, BoardGeometry(fromHFile).nearSide)
    }

    /**
     * Renders a fake photo: squares in two shades, pieces as discs that also rise one third of a
     * square towards the far side (crude stand-in for a piece seen from an angle).
     */
    private fun render(geometry: BoardGeometry, occupancy: IntArray, brightness: Double, w: Int = 640, h: Int = 520): ArrayLumaImage {
        val inv = geometry.homography.inverse()
        val data = IntArray(w * h)
        for (y in 0 until h) for (x in 0 until w) {
            val b = inv.map(x + 0.5, y + 0.5)
            var v = 60.0
            if (b.x in 0.0..8.0 && b.y in 0.0..8.0) {
                val f = b.x.toInt().coerceIn(0, 7)
                val r = b.y.toInt().coerceIn(0, 7)
                v = if (Square.isLight(Square.of(f, r))) 170.0 else 90.0
                // piece disc centred in the square, plus a stalk reaching into the square beyond (towards rank 8)
                for (dr in 0..1) {
                    val rr = r - dr
                    if (rr !in 0..7) continue
                    val occ = occupancy[Square.of(f, rr)]
                    if (occ == 0) continue
                    val cx = f + 0.5
                    val cy = rr + 0.5
                    val inDisc = (b.x - cx) * (b.x - cx) + (b.y - cy) * (b.y - cy) < 0.3 * 0.3
                    val inStalk = abs(b.x - cx) < 0.12 && b.y > cy && b.y < cy + 0.85
                    if (inDisc || inStalk) v = if (occ == 1) 235.0 else 25.0
                }
            }
            data[y * w + x] = (v * brightness + ((x * 7 + y * 13) % 5)).toInt().coerceIn(0, 255)
        }
        return ArrayLumaImage(w, h, data)
    }

    private fun occupancyAfter(moves: List<String>): Pair<Board, IntArray> {
        var b = Board.start()
        for (m in moves) b = b.play(b.parseMove(m)!!)
        return b to b.occupancy()
    }

    @Test
    fun calibrateAndInferMovesFromSideView() {
        val geometry = BoardGeometry(sideViewCorners)
        val empty = SquareSampler.sample(render(geometry, IntArray(64), 1.0), geometry)
        val start = SquareSampler.sample(render(geometry, Board.start().occupancy(), 1.0), geometry)
        val cal = Calibration.learn(empty, start)
        assertTrue(cal.isUsable, cal.notes.joinToString("\n"))

        // Single pawn move, slightly different exposure.
        val (b1, occ1) = occupancyAfter(listOf("e4"))
        val obs1 = cal.observe(SquareSampler.sample(render(geometry, occ1, 0.85), geometry))
        val r1 = MoveInference.infer(Board.start(), obs1)
        assertEquals("e4", r1.best!!.description, r1.candidates.take(3).joinToString { "${it.description}=${"%.2f".format(it.cost)}" })
        assertTrue(r1.margin > 0.3, "margin ${r1.margin}")

        // Two plies at once (user forgot to scan in between), including a capture.
        val (b3, occ3) = occupancyAfter(listOf("e4", "d5", "exd5"))
        val obs3 = cal.observe(SquareSampler.sample(render(geometry, occ3, 1.1), geometry))
        val r3 = MoveInference.infer(b1, obs3)
        assertEquals("d5 exd5", r3.best!!.description)

        // Castling and en passant are matched as single moves.
        val (b4, _) = occupancyAfter(listOf("e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"))
        val castled = b4.play(Move.fromUci("e1g1")!!)
        val obs4 = cal.observe(SquareSampler.sample(render(geometry, castled.occupancy(), 1.0), geometry))
        assertEquals("O-O", MoveInference.infer(b4, obs4).best!!.description)

        val epBoard = Board.fromFen("rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3")
        val afterEp = epBoard.play(Move.fromUci("e5d6")!!)
        val obs5 = cal.observe(SquareSampler.sample(render(geometry, afterEp.occupancy(), 1.0), geometry))
        assertEquals("exd6", MoveInference.infer(epBoard, obs5).best!!.description)

        // No move: unchanged board should be reported as such.
        val obs6 = cal.observe(SquareSampler.sample(render(geometry, b3.occupancy(), 1.0), geometry))
        assertEquals("no move", MoveInference.infer(b3, obs6).best!!.description)
    }

    @Test
    fun inferWorksOverhead() {
        val geometry = BoardGeometry(overheadCorners)
        val empty = SquareSampler.sample(render(geometry, IntArray(64), 1.0, 500, 500), geometry)
        val start = SquareSampler.sample(render(geometry, Board.start().occupancy(), 1.0, 500, 500), geometry)
        val cal = Calibration.learn(empty, start)
        assertTrue(cal.isUsable, cal.notes.joinToString("\n"))
        val (_, occ) = occupancyAfter(listOf("Nf3"))
        val obs = cal.observe(SquareSampler.sample(render(geometry, occ, 1.0, 500, 500), geometry))
        assertEquals("Nf3", MoveInference.infer(Board.start(), obs).best!!.description)
    }
}
