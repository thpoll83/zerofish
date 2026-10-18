package com.chesscoach.core

import com.chesscoach.core.chess.Board
import com.chesscoach.core.chess.Square
import com.chesscoach.core.vision.ArrayLumaImage
import com.chesscoach.core.vision.BoardLocator
import com.chesscoach.core.vision.Calibration
import com.chesscoach.core.vision.GridDetector
import com.chesscoach.core.vision.Pt
import javax.imageio.ImageIO
import kotlin.math.hypot
import kotlin.test.Test
import kotlin.test.assertNotNull
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * Tests on photographs of real boards (see src/test/resources/boards/NOTICE.md).
 * Ground truth corners come from ground_truth.txt; a detection passes when every corner is within
 * 2.5% of the image's longer side of the labelled corner, for some cyclic rotation.
 */
class RealBoardTest {
    private data class Labelled(val name: String, val corners: List<Pt>)

    private fun groundTruth(): Pair<List<Labelled>, List<String>> {
        val text = javaClass.getResourceAsStream("/boards/ground_truth.txt")!!.bufferedReader().readText()
        val labelled = ArrayList<Labelled>()
        val failures = ArrayList<String>()
        for (raw in text.lines()) {
            val line = raw.trim()
            if (line.isEmpty()) continue
            if (line.startsWith("# known failures")) {
                failures += line.substringAfter(":").trim().split(Regex("\\s+")).filter { it.isNotEmpty() }
                continue
            }
            if (line.startsWith("#")) continue
            val t = line.split(Regex("\\s+"))
            val c = (0 until 4).map { Pt(t[1 + 2 * it].toDouble(), t[2 + 2 * it].toDouble()) }
            labelled += Labelled(t[0], c)
        }
        return labelled to failures
    }

    private fun load(name: String): ArrayLumaImage {
        val stream = javaClass.getResourceAsStream("/boards/$name.jpg") ?: error("missing resource $name")
        val bi = ImageIO.read(stream)
        val data = IntArray(bi.width * bi.height)
        for (y in 0 until bi.height) for (x in 0 until bi.width) {
            val rgb = bi.getRGB(x, y)
            data[y * bi.width + x] = (((rgb shr 16) and 255) * 77 + ((rgb shr 8) and 255) * 151 + (rgb and 255) * 28) shr 8
        }
        return ArrayLumaImage(bi.width, bi.height, data)
    }

    private fun cornerError(found: List<Pt>, truth: List<Pt>): Double {
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

    @Test
    fun findsTheBoardInRealPhotos() {
        val (labelled, _) = groundTruth()
        assertTrue(labelled.size >= 15, "expected at least 15 labelled photos, got ${labelled.size}")
        val problems = ArrayList<String>()
        for (l in labelled) {
            val img = load(l.name)
            val grid = GridDetector.detect(img)
            if (grid == null) {
                problems += "${l.name}: not found"
                continue
            }
            val err = cornerError(grid.corners, l.corners)
            val tol = 0.025 * maxOf(img.width, img.height)
            if (err > tol) problems += "${l.name}: corner error %.0f px (tolerance %.0f), ${grid.notes}".format(err, tol)
        }
        if (problems.isNotEmpty()) fail("Detection regressions:\n" + problems.joinToString("\n"))
    }

    /** Diagnostic dump, enabled with CHESS_DEBUG=1: feature grids and line overlays. */
    @Test
    fun debugDumpIfRequested() {
        if (System.getenv("CHESS_DEBUG") == null) return
        for (name in listOf("board_6", "board_12")) {
            val img = load(name)
            val grid = GridDetector.detect(img) ?: continue
            val exp = if (name == "board_6") Board.fromFen("rnbqkbnr/pppp2pp/5p2/4p3/4P3/5P2/PPPP2PP/RNBQKBNR w KQkq - 0 3").occupancy() else Board.start().occupancy()
            val located = BoardLocator.locate(img, grid.corners, Calibration.default(), exp, null)
            println("DBG $name rotation ${located.rotation} a1 at ${located.geometry.corners[0]} nearSide ${located.geometry.nearSide}")
            run {
                val out = java.awt.image.BufferedImage(img.width, img.height, java.awt.image.BufferedImage.TYPE_INT_RGB)
                for (y in 0 until img.height) for (x in 0 until img.width) { val v = img.luma(x, y); out.setRGB(x, y, (v shl 16) or (v shl 8) or v) }
                val g = out.createGraphics()
                val geo = located.geometry
                for (sq in 0 until 64) {
                    val poly = geo.sampleWindowPolygon(Square.file(sq), Square.rank(sq))
                    g.color = if (located.observations[sq].label == 0) java.awt.Color.GREEN else if (located.observations[sq].label == 1) java.awt.Color.WHITE else java.awt.Color.RED
                    for (i in 0 until 4) { val a = poly[i]; val b = poly[(i + 1) % 4]; g.drawLine(a.x.toInt(), a.y.toInt(), b.x.toInt(), b.y.toInt()) }
                    val c = geo.toImage(Square.file(sq) + 0.5, Square.rank(sq) + 0.5)
                    g.color = java.awt.Color.YELLOW
                    g.drawString(Square.name(sq), c.x.toInt() - 6, c.y.toInt() + 4)
                }
                g.dispose()
                val dir = java.io.File("build/test-overlays").apply { mkdirs() }
                ImageIO.write(out, "png", java.io.File(dir, "$name-windows.png"))
            }
            for (r in 7 downTo 0) {
                println("DBG $name rank ${r + 1} occ  " + (0..7).joinToString(" ") { f -> "%.2f".format(located.features.occFraction[Square.of(f, r)]) } +
                    "   col " + (0..7).joinToString(" ") { f -> "%+.2f".format(located.features.colourScore[Square.of(f, r)]) })
            }
        }
        for (name in listOf("board_5", "board_17", "board_cc6")) {
            val img = load(name)
            val lines = ArrayList<com.chesscoach.core.vision.ImageLine>()
            val grid = GridDetector.detect(img, log = { println("DBG $name $it") }, debugOut = lines)
            val out = java.awt.image.BufferedImage(img.width, img.height, java.awt.image.BufferedImage.TYPE_INT_RGB)
            for (y in 0 until img.height) for (x in 0 until img.width) { val v = img.luma(x, y); out.setRGB(x, y, (v shl 16) or (v shl 8) or v) }
            val g = out.createGraphics()
            for (l in lines) { g.color = when (l.family) { 0 -> java.awt.Color.RED; 1 -> java.awt.Color.ORANGE; else -> java.awt.Color.MAGENTA }; g.drawLine(l.x1.toInt(), l.y1.toInt(), l.x2.toInt(), l.y2.toInt()) }
            grid?.let { gr -> g.color = java.awt.Color.GREEN; val geo = com.chesscoach.core.vision.BoardGeometry(gr.corners); for (i in 0..8) { val a = geo.toImage(i.toDouble(), 0.0); val b = geo.toImage(i.toDouble(), 8.0); g.drawLine(a.x.toInt(), a.y.toInt(), b.x.toInt(), b.y.toInt()); val c = geo.toImage(0.0, i.toDouble()); val d = geo.toImage(8.0, i.toDouble()); g.drawLine(c.x.toInt(), c.y.toInt(), d.x.toInt(), d.y.toInt()) } }
            g.dispose()
            val dir = java.io.File("build/test-overlays").apply { mkdirs() }
            ImageIO.write(out, "png", java.io.File(dir, "$name.png"))
        }
    }

    @Test
    fun knownHardPhotosAreReported() {
        // Documents the current state: these side views are not solved yet. No assertion on the
        // outcome, but they must not crash and must finish quickly.
        val (_, failures) = groundTruth()
        for (name in failures) {
            val img = load(name)
            val t0 = System.currentTimeMillis()
            val grid = GridDetector.detect(img)
            val ms = System.currentTimeMillis() - t0
            println("hard photo $name: ${grid?.notes ?: "not found"} in $ms ms")
            assertTrue(ms < 5000, "$name took $ms ms")
        }
    }

    @Test
    fun detectionIsFastEnoughForAPhone() {
        val img = load("board_2")
        GridDetector.detect(img) // warm-up
        val t0 = System.nanoTime()
        repeat(3) { GridDetector.detect(img) }
        val msPerPhoto = (System.nanoTime() - t0) / 3 / 1_000_000
        println("detection: $msPerPhoto ms per 1000 px photo on the JVM")
        assertTrue(msPerPhoto < 2000, "too slow: $msPerPhoto ms")
    }

    /**
     * board_12 shows the starting position: orientation, learned thresholds and every square's
     * reading must match it. A few squares hidden behind tall pieces may read wrong.
     */
    @Test
    fun readsTheStartingPositionFromARealPhoto() {
        val img = load("board_12")
        val grid = assertNotNull(GridDetector.detect(img), "board_12: board not found")
        val located = BoardLocator.locate(img, grid.corners, Calibration.default(), Board.start().occupancy(), null)
        val cal = Calibration.learn(located.features)
        val obs = cal.observe(located.features)
        val expected = Board.start().occupancy()
        val wrong = (0 until 64).filter { obs[it].label != expected[it] }
        println("board_12: ${cal.notes.joinToString(" | ")}; wrong squares: " + wrong.joinToString { Square.name(it) + "=" + obs[it].label })
        assertTrue(wrong.size <= 4, "board_12: ${wrong.size} squares misread: " + wrong.joinToString { Square.name(it) })
    }

    /**
     * board_6 (wooden set, overhead) shows 1.e4 e5 2.f3 f6 with the bishop c1 unclear. Labelled by
     * eye; the light wooden pieces are only a little brighter than the dark squares, which is the
     * hard case for the colour cue. Uses default thresholds, as no starting-position photo exists
     * for this set.
     */
    @Test
    fun readsAWoodenMiddlegameFromARealPhoto() {
        val img = load("board_6")
        val grid = assertNotNull(GridDetector.detect(img), "board_6: board not found")
        val fen = "rnbqkbnr/pppp2pp/5p2/4p3/4P3/5P2/PPPP2PP/RNBQKBNR w KQkq - 0 3"
        val expectedBoard = Board.fromFen(fen)
        val expected = expectedBoard.occupancy()
        val located = BoardLocator.locate(img, grid.corners, Calibration.default(), expected, null)
        val obs = located.observations
        val uncertain = setOf(Square.parse("c1"))
        val wrongOcc = (0 until 64).filter { it !in uncertain && (obs[it].label == 0) != (expected[it] == 0) }
        val wrongColour = (0 until 64).filter { it !in uncertain && expected[it] != 0 && obs[it].label != 0 && obs[it].label != expected[it] }
        println("board_6 occupancy errors: " + wrongOcc.joinToString { Square.name(it) } + "; colour errors: " + wrongColour.joinToString { Square.name(it) })
        assertTrue(wrongOcc.size <= 4, "board_6: occupancy wrong on ${wrongOcc.size} squares: " + wrongOcc.joinToString { Square.name(it) })
        assertTrue(wrongColour.size <= 4, "board_6: colour wrong on ${wrongColour.size} squares: " + wrongColour.joinToString { Square.name(it) })
    }
}
