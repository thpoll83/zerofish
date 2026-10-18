package com.chesscoach.core

import com.chesscoach.core.vision.ArrayLumaImage
import com.chesscoach.core.vision.LiveTracker
import java.io.File
import javax.imageio.ImageIO
import kotlin.test.Test

/** Replays a folder of video frames (CHESS_FRAMES_DIR, sorted by name) through the live tracker and prints a log. */
class VideoReplayTest {
    private fun load(file: File): ArrayLumaImage {
        val bi = ImageIO.read(file)
        val data = IntArray(bi.width * bi.height)
        for (y in 0 until bi.height) for (x in 0 until bi.width) {
            val rgb = bi.getRGB(x, y)
            data[y * bi.width + x] = (((rgb shr 16) and 255) * 77 + ((rgb shr 8) and 255) * 151 + (rgb and 255) * 28) shr 8
        }
        return ArrayLumaImage(bi.width, bi.height, data)
    }

    @Test
    fun startCheckDiagnosticsIfAvailable() {
        val dir = System.getenv("CHESS_FRAMES_DIR")?.let { File(it) } ?: return
        val files = dir.listFiles { f -> f.extension.lowercase() == "jpg" }!!.sortedBy { it.name }.take(8)
        for (f in files) {
            val img = load(f)
            val grid = com.chesscoach.core.vision.GridDetector.detect(img) ?: run { println("DIAG ${f.name}: no board"); return@run null } ?: continue
            val located = com.chesscoach.core.vision.BoardLocator.locate(img, grid.corners, com.chesscoach.core.vision.Calibration.default(), com.chesscoach.core.chess.Board.start().occupancy(), null)
            val feat = located.features
            val sq = com.chesscoach.core.chess.Square
            val empties = (0 until 64).filter { sq.rank(it) in 2..5 }.map { feat.occFraction[it] }.sorted()
            val pieces = (0 until 64).filter { sq.rank(it) !in 2..5 }.map { feat.occFraction[it] }.sorted()
            val split = (empties[empties.size / 2] + pieces[pieces.size / 2]) / 2
            val piecesSeen = pieces.count { it > split + 0.03 }
            val emptiesSeen = empties.count { it < split - 0.03 }
            val whites = (0 until 64).filter { sq.rank(it) <= 1 }.map { feat.colourScore[it] }.average()
            val blacks = (0 until 64).filter { sq.rank(it) >= 6 }.map { feat.colourScore[it] }.average()
            println("DIAG ${f.name}: ${grid.notes} a1=(%.0f,%.0f) rot=${located.rotation} split=%.2f piecesSeen=$piecesSeen emptiesSeen=$emptiesSeen whites=%.2f blacks=%.2f".format(located.geometry.corners[0].x, located.geometry.corners[0].y, split, whites, blacks))
            for (r in 7 downTo 0) println("DIAG   rank ${r + 1} occ " + (0..7).joinToString(" ") { "%.2f".format(feat.occFraction[sq.of(it, r)]) } + "  col " + (0..7).joinToString(" ") { "%+.2f".format(feat.colourScore[sq.of(it, r)]) })
            // overlay
            val out = java.awt.image.BufferedImage(img.width, img.height, java.awt.image.BufferedImage.TYPE_INT_RGB)
            for (y in 0 until img.height) for (x in 0 until img.width) { val v = img.luma(x, y); out.setRGB(x, y, (v shl 16) or (v shl 8) or v) }
            val g = out.createGraphics(); g.color = java.awt.Color.GREEN
            val geo = located.geometry
            for (i in 0..8) { val a = geo.toImage(i.toDouble(), 0.0); val b = geo.toImage(i.toDouble(), 8.0); g.drawLine(a.x.toInt(), a.y.toInt(), b.x.toInt(), b.y.toInt()); val c = geo.toImage(0.0, i.toDouble()); val d = geo.toImage(8.0, i.toDouble()); g.drawLine(c.x.toInt(), c.y.toInt(), d.x.toInt(), d.y.toInt()) }
            for (s2 in 0 until 64) { val poly = geo.sampleWindowPolygon(sq.file(s2), sq.rank(s2)); g.color = java.awt.Color.CYAN; for (i in 0 until 4) { val a = poly[i]; val b = poly[(i + 1) % 4]; g.drawLine(a.x.toInt(), a.y.toInt(), b.x.toInt(), b.y.toInt()) } }
            g.color = java.awt.Color.RED; val a1 = geo.toImage(0.5, 0.5); g.fillOval(a1.x.toInt() - 5, a1.y.toInt() - 5, 10, 10)
            g.dispose()
            val od = File("build/test-overlays").apply { mkdirs() }
            ImageIO.write(out, "png", File(od, "video-${f.nameWithoutExtension}.png"))
        }
    }

    @Test
    fun replayIfAvailable() {
        val dir = System.getenv("CHESS_FRAMES_DIR")?.let { File(it) } ?: return
        val fps = System.getenv("CHESS_FRAMES_FPS")?.toDoubleOrNull() ?: 4.0
        val files = dir.listFiles { f -> f.extension.lowercase() == "jpg" }!!.sortedBy { it.name }
        val tracker = LiveTracker(framesToConfirm = 3, framesToLearn = 3)
        var last = ""
        val moves = ArrayList<String>()
        val counts = HashMap<String, Int>()
        for ((i, f) in files.withIndex()) {
            val r = tracker.process(load(f))
            counts[r.status.name] = (counts[r.status.name] ?: 0) + 1
            val line = "${r.status} ${r.message}" + (if (r.suggestions.isNotEmpty()) " -> " + r.suggestions.joinToString(" | ") { "${it.description} (%.1f)".format(it.cost) } else "")
            if (r.applied.isNotEmpty()) moves += r.applied.joinToString(" ") { it.uci() } + "@%.1fs".format(i / fps)
            if (line != last || r.applied.isNotEmpty()) println("REPLAY %6.1fs %s %s".format(i / fps, f.name, line))
            last = line
        }
        println("REPLAY statuses: $counts")
        println("REPLAY moves: $moves")
        println("REPLAY final: ${tracker.board.toFen()}")
    }
}
