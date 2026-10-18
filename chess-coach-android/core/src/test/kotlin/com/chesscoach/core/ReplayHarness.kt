package com.chesscoach.core

import com.chesscoach.core.chess.Board
import com.chesscoach.core.vision.ArrayLumaImage
import com.chesscoach.core.vision.LiveTracker
import java.io.InputStream
import javax.imageio.ImageIO

/**
 * Replays video frames through [LiveTracker] and, when the game's moves are known, plays the
 * user: taps the offered button that matches the next moves, and corrects a wrongly applied move
 * the way a user would (undo and type). Used by the on-demand video replay and by the committed
 * passage test.
 */
object ReplayHarness {
    class Stats {
        /** Plies the tracker applied by itself, correctly. */
        var autoFollowed = 0
        /** Buttons the simulated user tapped. */
        var taps = 0
        /** Moves the tracker applied that were not the game's moves. */
        var wrong = 0
        /** Plies of the known moves reached (by tracking or tapping). */
        var reached = 0
        val counts = HashMap<String, Int>()
        val applied = ArrayList<String>()
        var finalBoard: Board = Board.start()
    }

    fun load(stream: InputStream): ArrayLumaImage {
        val bi = ImageIO.read(stream)
        val data = IntArray(bi.width * bi.height)
        for (y in 0 until bi.height) for (x in 0 until bi.width) {
            val rgb = bi.getRGB(x, y)
            data[y * bi.width + x] = (((rgb shr 16) and 255) * 77 + ((rgb shr 8) and 255) * 151 + (rgb and 255) * 28) shr 8
        }
        return ArrayLumaImage(bi.width, bi.height, data)
    }

    private fun bare(san: String) = san.trimEnd('+', '#')

    /**
     * @param frames name and loader per frame, in order; the index gives the time at [fps].
     * @param jump moves to put on the tracker once it has learned (the passage starts mid-game).
     * @param truth the game's moves from the starting position (beginning with [jump] if given).
     * @param detail time window in seconds in which every scored candidate is logged.
     */
    fun run(
        frames: List<Pair<String, () -> ArrayLumaImage>>,
        fps: Double,
        jump: List<String>? = null,
        truth: List<String>? = null,
        detail: ClosedRange<Double>? = null,
        log: (String) -> Unit = {},
    ): Stats {
        val tracker = LiveTracker(framesToConfirm = 3, framesToLearn = 3)
        val stats = Stats()
        val bareTruth = truth?.map { bare(it) }
        var truthIdx = 0
        var checking = truth != null
        fun truthBoard(): Board {
            var b = Board.start()
            for (san in truth!!.take(truthIdx)) b = b.play(b.parseMove(san) ?: error("bad truth move $san"))
            return b
        }
        var last = ""
        for ((i, frame) in frames.withIndex()) {
            val (name, loader) = frame
            val t = i / fps
            val r = tracker.process(loader())
            if (r.status == LiveTracker.Status.LEARNED && jump != null) {
                var b = tracker.board
                for (san in jump) b = b.play(b.parseMove(san) ?: error("bad move $san"))
                tracker.setBoard(b)
                truthIdx = jump.size
            }
            if (detail != null && t in detail) {
                log("DETAIL %6.1fs %s %s agree=%d: %s".format(t, name, r.status, r.agreement,
                    r.candidates.take(6).joinToString(" | ") { "${it.description} (%.2f)".format(it.cost) }))
            }
            if (checking && tracker.phase == LiveTracker.Phase.TRACKING) {
                if (truthIdx >= bareTruth!!.size) {
                    if (r.applied.isNotEmpty() || r.status == LiveTracker.Status.AMBIGUOUS) {
                        log("REPLAY %6.1fs %s known moves exhausted; no longer checking".format(t, name))
                        checking = false
                    }
                } else {
                    if (r.applied.isNotEmpty()) {
                        val sans = r.candidate!!.sans.map { bare(it) }
                        if (sans == bareTruth.drop(truthIdx).take(sans.size)) {
                            truthIdx += sans.size; stats.autoFollowed += sans.size
                        } else {
                            stats.wrong++
                            log("REPLAY %6.1fs %s WRONG applied %s, expected %s".format(t, name, sans, bareTruth.drop(truthIdx).take(2)))
                            tracker.setBoard(truthBoard())
                        }
                    }
                    if (r.status == LiveTracker.Status.AMBIGUOUS) {
                        val pick = r.suggestions
                            .filter { c -> c.sans.map { bare(it) } == bareTruth.drop(truthIdx).take(c.sans.size) }
                            .maxByOrNull { it.moves.size }
                        if (pick != null) {
                            tracker.accept(pick)
                            truthIdx += pick.moves.size
                            stats.taps++
                            log("REPLAY %6.1fs %s TAP %s".format(t, name, pick.description))
                        }
                    }
                }
            }
            stats.counts[r.status.name] = (stats.counts[r.status.name] ?: 0) + 1
            val line = "${r.status} ${r.message}" +
                (if (r.suggestions.isNotEmpty()) " -> " + r.suggestions.joinToString(" | ") { "${it.description} (%.1f)".format(it.cost) } else "")
            if (r.applied.isNotEmpty()) stats.applied += r.applied.joinToString(" ") { it.uci() } + "@%.1fs".format(t)
            if (line != last || r.applied.isNotEmpty()) log("REPLAY %6.1fs %s %s".format(t, name, line))
            last = line
        }
        stats.reached = if (truth == null) 0 else minOf(truthIdx, truth.size)
        stats.finalBoard = tracker.board
        log("REPLAY statuses: ${stats.counts}")
        log("REPLAY moves: ${stats.applied}")
        log("REPLAY final: ${tracker.board.toFen()}")
        if (truth != null) log("REPLAY truth: ${truth.size} plies, followed by itself ${stats.autoFollowed}, by tap ${stats.taps} taps, wrong ${stats.wrong}, reached ply ${stats.reached}")
        return stats
    }
}
