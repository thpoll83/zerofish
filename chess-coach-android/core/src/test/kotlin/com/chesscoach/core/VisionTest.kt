package com.chesscoach.core

import com.chesscoach.core.chess.Board
import com.chesscoach.core.chess.Move
import com.chesscoach.core.chess.Square
import com.chesscoach.core.vision.ArrayLumaImage
import com.chesscoach.core.vision.BoardGeometry
import com.chesscoach.core.vision.BoardLocator
import com.chesscoach.core.vision.Calibration
import com.chesscoach.core.vision.ChangeDetector
import com.chesscoach.core.vision.GridDetector
import com.chesscoach.core.vision.Homography
import com.chesscoach.core.vision.LumaImage
import com.chesscoach.core.vision.MoveInference
import com.chesscoach.core.vision.NearSide
import com.chesscoach.core.vision.Pt
import com.chesscoach.core.vision.SquareFeatures
import java.awt.Color
import java.awt.image.BufferedImage
import java.io.File
import javax.imageio.ImageIO
import kotlin.math.abs
import kotlin.math.hypot
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class VisionTest {
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

    // ---- synthetic scene -------------------------------------------------------------------------

    /**
     * Renders a photo-like scene: a table with texture, a board frame, light/dark squares with a
     * gentle illumination gradient, and pieces drawn in image space as a disc plus a body rising
     * towards the top of the image (as a real piece does when seen from an angle). Noise added.
     */
    private fun render(
        corners: List<Pt>, occupancy: IntArray, w: Int, h: Int,
        brightness: Double = 1.0, seed: Int = 1, lightTone: Double = 175.0, darkTone: Double = 85.0,
    ): ArrayLumaImage {
        val hom = Homography.boardToImage(corners)
        val inv = hom.inverse()
        val rnd = java.util.Random(seed.toLong())
        val data = IntArray(w * h)
        for (y in 0 until h) for (x in 0 until w) {
            val b = inv.map(x + 0.5, y + 0.5)
            val grad = 1.0 + 0.12 * (x.toDouble() / w - 0.5) - 0.08 * (y.toDouble() / h - 0.5)
            var v: Double = if (b.x in -0.7..8.7 && b.y in -0.7..8.7) {
                if (b.x in 0.0..8.0 && b.y in 0.0..8.0) {
                    val f = b.x.toInt().coerceIn(0, 7)
                    val r = b.y.toInt().coerceIn(0, 7)
                    if (Square.isLight(Square.of(f, r))) lightTone else darkTone
                } else 120.0 // frame
            } else {
                // table: slow, non-periodic brightness variation like wood under room light
                140.0 + 12 * kotlin.math.sin(x / 41.0 + 2 * kotlin.math.sin(y / 67.0)) + 6 * kotlin.math.cos(y / 29.0)
            }
            data[y * w + x] = (v * grad * brightness).toInt().coerceIn(0, 255)
        }
        // pieces in image space
        for (sq in 0 until 64) {
            val occ = occupancy[sq]
            if (occ == 0) continue
            val f = Square.file(sq)
            val r = Square.rank(sq)
            val c = hom.map(f + 0.5, r + 0.5)
            val e1 = hom.map(f + 1.0, r + 0.5)
            val e2 = hom.map(f + 0.5, r + 1.0)
            // base: a circle on the board, so an ellipse in the image; body: rises towards the top
            val halfW = hypot(e1.x - c.x, e1.y - c.y)
            val halfH = hypot(e2.x - c.x, e2.y - c.y)
            val rx = 0.32 * halfW * 2
            val ry = 0.32 * halfH * 2
            val height = 1.1 * halfW * 2
            val tone = if (occ == 1) 230.0 else 30.0
            val x0 = (c.x - rx - 1).toInt().coerceAtLeast(0)
            val x1 = (c.x + rx + 1).toInt().coerceAtMost(w - 1)
            val y0 = (c.y - height - 1).toInt().coerceAtLeast(0)
            val y1 = (c.y + ry + 1).toInt().coerceAtMost(h - 1)
            for (y in y0..y1) for (x in x0..x1) {
                val dx = x - c.x
                val dy = y - c.y
                val inDisc = (dx * dx) / (rx * rx) + (dy * dy) / (ry * ry) <= 1.0
                val inBody = abs(dx) <= rx * 0.45 && dy < 0 && dy > -height
                if (inDisc || inBody) {
                    val shade = if (inBody && abs(dx) > rx * 0.3) tone * 0.8 + 10 else tone
                    data[y * w + x] = shade.toInt().coerceIn(0, 255)
                }
            }
        }
        for (i in data.indices) data[i] = (data[i] + rnd.nextGaussian() * 3).toInt().coerceIn(0, 255)
        return ArrayLumaImage(w, h, data)
    }

    private fun cornerError(found: List<Pt>, truth: List<Pt>): Double {
        // best cyclic rotation
        var best = Double.MAX_VALUE
        for (rot in 0 until 4) {
            var e = 0.0
            for (i in 0 until 4) {
                val a = found[(i + rot) % 4]
                e = maxOf(e, hypot(a.x - truth[i].x, a.y - truth[i].y))
            }
            best = minOf(best, e)
        }
        return best
    }

    private fun occupancyAfter(moves: List<String>): Pair<Board, IntArray> {
        var b = Board.start()
        for (m in moves) b = b.play(b.parseMove(m)!!)
        return b to b.occupancy()
    }

    private fun writeOverlay(img: LumaImage, corners: List<Pt>?, name: String, lines: List<com.chesscoach.core.vision.ImageLine> = emptyList()) {
        val out = BufferedImage(img.width, img.height, BufferedImage.TYPE_INT_RGB)
        for (y in 0 until img.height) for (x in 0 until img.width) {
            val v = img.luma(x, y)
            out.setRGB(x, y, (v shl 16) or (v shl 8) or v)
        }
        run {
            val g = out.createGraphics()
            for (l in lines) {
                g.color = if (l.family == 0) Color.RED else Color.ORANGE
                g.drawLine(l.x1.toInt(), l.y1.toInt(), l.x2.toInt(), l.y2.toInt())
            }
            g.dispose()
        }
        if (corners != null) {
            val g = out.createGraphics()
            g.color = Color.GREEN
            val geo = BoardGeometry(corners)
            for (i in 0..8) {
                val a = geo.toImage(i.toDouble(), 0.0); val b = geo.toImage(i.toDouble(), 8.0)
                g.drawLine(a.x.toInt(), a.y.toInt(), b.x.toInt(), b.y.toInt())
                val c = geo.toImage(0.0, i.toDouble()); val d = geo.toImage(8.0, i.toDouble())
                g.drawLine(c.x.toInt(), c.y.toInt(), d.x.toInt(), d.y.toInt())
            }
            g.color = Color.RED
            val a1 = geo.toImage(0.5, 0.5)
            g.fillOval(a1.x.toInt() - 5, a1.y.toInt() - 5, 10, 10)
            g.dispose()
        }
        val dir = File("build/test-overlays").apply { mkdirs() }
        ImageIO.write(out, "png", File(dir, "$name.png"))
    }

    @Test
    fun detectsGridOverheadRotated() {
        // slightly rotated and off-centre board
        val corners = listOf(Pt(140.0, 470.0), Pt(560.0, 500.0), Pt(530.0, 80.0), Pt(110.0, 110.0))
        val (_, occ) = occupancyAfter(listOf("e4", "e5", "Nf3", "Nc6", "Bb5", "a6"))
        val img = render(corners, occ, 700, 600)
        val grid = GridDetector.detect(img)
        writeOverlay(img, grid?.corners, "overhead")
        assertNotNull(grid, "grid not found")
        val err = cornerError(grid.corners, corners)
        assertTrue(err < 8.0, "corner error $err px, notes ${grid.notes}")
    }

    @Test
    fun detectsGridSideView() {
        val corners = listOf(Pt(60.0, 560.0), Pt(740.0, 560.0), Pt(600.0, 160.0), Pt(200.0, 160.0))
        val (_, occ) = occupancyAfter(listOf("d4", "Nf6", "c4", "e6", "Nc3", "Bb4"))
        val img = render(corners, occ, 800, 640)
        val grid = GridDetector.detect(img)
        writeOverlay(img, grid?.corners, "side")
        println("SIDE checker at true corners: %.3f".format(GridDetector.checkerScore(img, BoardGeometry(corners))))
        assertNotNull(grid, "grid not found")
        val err = cornerError(grid.corners, corners)
        assertTrue(err < 10.0, "corner error $err px, notes ${grid.notes}")
    }

    @Test
    fun handheldGame() {
        // Scan 1: starting position from one viewpoint, used to learn thresholds and orientation.
        val view1 = listOf(Pt(70.0, 560.0), Pt(730.0, 570.0), Pt(610.0, 150.0), Pt(190.0, 140.0))
        val img1 = render(view1, Board.start().occupancy(), 800, 640, seed = 3)
        val grid1 = assertNotNull(GridDetector.detect(img1), "start grid not found")
        writeOverlay(img1, grid1.corners, "scan1")
        println("scan1 corner error %.1f notes %s".format(cornerError(grid1.corners, view1), grid1.notes))
        val loc1 = BoardLocator.locate(img1, grid1.corners, Calibration.default(), Board.start().occupancy(), null)
        val cal = Calibration.learn(loc1.features)
        assertTrue(cal.isUsable, cal.notes.joinToString("\n"))
        // orientation: a1 corner must be near the true a1 corner
        val a1 = loc1.geometry.corners[0]
        assertTrue(hypot(a1.x - view1[0].x, a1.y - view1[0].y) < 10.0, "a1 at $a1")

        // Scan 2: after e4, from a different viewpoint and exposure.
        val view2 = listOf(Pt(120.0, 600.0), Pt(700.0, 580.0), Pt(640.0, 130.0), Pt(160.0, 170.0))
        val (b1, occ1) = occupancyAfter(listOf("e4"))
        val img2 = render(view2, occ1, 800, 640, brightness = 0.85, seed = 4)
        val grid2 = assertNotNull(GridDetector.detect(img2), "scan 2 grid not found")
        writeOverlay(img2, grid2.corners, "scan2")
        println("scan2 corner error %.1f notes %s".format(cornerError(grid2.corners, view2), grid2.notes))
        val loc2 = BoardLocator.locate(img2, grid2.corners, cal, Board.start().occupancy(), loc1.rotation)
        val change2 = ChangeDetector.scores(loc1.patches, loc2.patches)
        for (name in listOf("e2", "e4", "e3", "d2")) {
            val sq = Square.parse(name)
            val o = loc2.observations[sq]
            println("scan2 $name occ %.2f white %.2f frac %.2f col %.2f change %.2f".format(o.occupied, o.white, o.occFraction, o.colourScore, change2[sq]))
        }
        val r2 = MoveInference.infer(Board.start(), loc2.observations, change2, nearSide = loc2.geometry.nearSide)
        assertEquals("e4", r2.best!!.description, r2.candidates.take(3).joinToString { "${it.description}=%.2f".format(it.cost) })

        // Scan 3: two plies later (e5 Nf3), camera moved to the other side of the board.
        val view3 = listOf(Pt(620.0, 150.0), Pt(180.0, 140.0), Pt(60.0, 570.0), Pt(740.0, 560.0))
        val (_, occ3) = occupancyAfter(listOf("e4", "e5", "Nf3"))
        val img3 = render(view3, occ3, 800, 640, brightness = 1.1, seed = 5)
        val grid3 = assertNotNull(GridDetector.detect(img3), "scan 3 grid not found")
        writeOverlay(img3, grid3.corners, "scan3", grid3.lines)
        println("scan3 checker at true corners %.2f".format(GridDetector.checkerScore(img3, BoardGeometry(view3))))
        println("scan3 corner error %.1f notes %s".format(cornerError(grid3.corners, view3), grid3.notes))
        val loc3 = BoardLocator.locate(img3, grid3.corners, cal, b1.occupancy(), loc2.rotation)
        val change3 = ChangeDetector.scores(loc2.patches, loc3.patches)
        for (name in listOf("e7", "e5", "g1", "f3", "e4", "d7")) {
            val sq = Square.parse(name)
            val o = loc3.observations[sq]
            println("scan3 $name occ %.2f white %.2f frac %.2f col %.2f change %.2f".format(o.occupied, o.white, o.occFraction, o.colourScore, change3[sq]))
        }
        val r3 = MoveInference.infer(b1, loc3.observations, change3, nearSide = loc3.geometry.nearSide)
        assertEquals("e5 Nf3", r3.best!!.description, r3.candidates.take(3).joinToString { "${it.description}=%.2f".format(it.cost) })

        // Castling and a capture from yet another angle, without change evidence.
        val (b4, _) = occupancyAfter(listOf("e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"))
        val castled = b4.play(Move.fromUci("e1g1")!!)
        val view4 = listOf(Pt(100.0, 90.0), Pt(130.0, 560.0), Pt(700.0, 600.0), Pt(680.0, 60.0))
        val img4 = render(view4, castled.occupancy(), 800, 640, seed = 6)
        val grid4 = assertNotNull(GridDetector.detect(img4), "scan 4 grid not found")
        val loc4 = BoardLocator.locate(img4, grid4.corners, cal, b4.occupancy(), null)
        assertEquals("O-O", MoveInference.infer(b4, loc4.observations, nearSide = loc4.geometry.nearSide).best!!.description)
    }

    @Test
    fun featuresSeparateStartPosition() {
        val geometry = BoardGeometry(sideViewCorners)
        val img = render(sideViewCorners, Board.start().occupancy(), 640, 520)
        val patches = com.chesscoach.core.vision.SquareSampler.sample(img, geometry)
        val f = SquareFeatures.extract(patches)
        val cal = Calibration.learn(f)
        assertTrue(cal.isUsable, cal.notes.joinToString("\n"))
        val obs = cal.observe(f)
        val expected = Board.start().occupancy()
        println("FEAT notes " + cal.notes.joinToString(" | "))
        println("FEAT colour thresholds dark %.2f light %.2f".format(cal.colourThreshold[0], cal.colourThreshold[1]))
        for (sq in 0 until 64) if (expected[sq] != obs[sq].label) {
            println("FEAT mismatch ${Square.name(sq)} light=${Square.isLight(sq)} occ %.2f col %.2f".format(f.occFraction[sq], f.colourScore[sq]))
            val side = com.chesscoach.core.vision.SquareSampler.DEFAULT_SIDE
            val tmpl = IntArray(side * side) { p ->
                val vals = (0 until 64).filter { Square.isLight(it) == Square.isLight(sq) }.map { patches[it][p] }.sorted()
                vals[vals.size / 2]
            }
            for (j in 0 until side) println("FEAT row $j patch " + (0 until side).joinToString(" ") { "%3d".format(patches[sq][j * side + it]) } + "   tmpl " + (0 until side).joinToString(" ") { "%3d".format(tmpl[j * side + it]) })
        }
        for (sq in 0 until 64) assertEquals(expected[sq], obs[sq].label, "square ${Square.name(sq)}")
    }

    /** Runs on a real photo when CHESS_PHOTO points at one; writes an overlay for eyeballing. */
    @Test
    fun realPhotoIfAvailable() {
        val path = System.getenv("CHESS_PHOTO") ?: return
        val bi = ImageIO.read(File(path))
        val data = IntArray(bi.width * bi.height)
        for (y in 0 until bi.height) for (x in 0 until bi.width) {
            val rgb = bi.getRGB(x, y)
            data[y * bi.width + x] = (((rgb shr 16) and 255) * 77 + ((rgb shr 8) and 255) * 151 + (rgb and 255) * 28) shr 8
        }
        val img = ArrayLumaImage(bi.width, bi.height, data)
        val grid = GridDetector.detect(img)
        writeOverlay(img, grid?.corners, File(path).nameWithoutExtension)
        println("real photo ${File(path).name}: ${grid?.notes ?: "NOT FOUND"} corners=${grid?.corners}")
        assertNotNull(grid, "grid not found in real photo")
    }
}
