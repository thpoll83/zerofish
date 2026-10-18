package com.chesscoach.core.vision

import com.chesscoach.core.chess.Square
import kotlin.math.exp

/** What the scanner believes about one square. Probabilities are in 0..1. */
data class SquareObservation(val occupied: Double, val white: Double, val occFraction: Double, val colourScore: Double) {
    /** 0 = empty, 1 = white, 2 = black, by the most likely reading. */
    val label: Int get() = if (occupied < 0.5) 0 else if (white >= 0.5) 1 else 2

    /** True when the reading is close to a decision boundary. */
    val unsure: Boolean get() = occupied in 0.3..0.7 || (occupied >= 0.5 && white in 0.3..0.7)
}

/** Per-square features that do not depend on a fixed camera: see [SquareFeatures.extract]. */
class SquareFeatures(val occFraction: DoubleArray, val colourScore: DoubleArray) {
    companion object {
        /**
         * Builds, for each square shade, an "empty square" template as the per-pixel median over
         * the 32 squares of that shade in this very photo (pieces never cover more than half of
         * them at any pixel), then measures how much of each square differs from its template and
         * whether the differing pixels are brighter or darker than the board.
         */
        fun extract(patches: Array<IntArray>, gradients: Array<IntArray>? = null): SquareFeatures {
            val n = patches[0].size
            val templates = Array(2) { shade ->
                val squares = (0 until 64).filter { (if (Square.isLight(it)) 1 else 0) == shade }
                val tmp = IntArray(squares.size)
                IntArray(n) { p ->
                    for ((k, sq) in squares.withIndex()) tmp[k] = patches[sq][p]
                    tmp.sort()
                    (tmp[tmp.size / 2 - 1] + tmp[tmp.size / 2]) / 2
                }
            }
            val toneDark = median(templates[0])
            val toneLight = median(templates[1])
            val toneDiff = maxOf(toneLight - toneDark, 10.0)
            val tau = 0.25 * toneDiff
            val occ = DoubleArray(64)
            val col = DoubleArray(64)
            val d = DoubleArray(n)
            val pieceLum = ArrayList<Int>(n)
            for (sq in 0 until 64) {
                val t = templates[if (Square.isLight(sq)) 1 else 0]
                val patch = patches[sq]
                for (p in 0 until n) d[p] = (patch[p] - t[p]).toDouble()
                // Illumination offset from the pixels that still look like board (|d| small), so a
                // piece covering most of the window cannot pull the reference towards itself.
                val boardLike = d.filter { kotlin.math.abs(it) < tau }
                val offset = if (boardLike.size >= n / 5) median(boardLike.toDoubleArray()).coerceIn(-0.1 * toneDiff, 0.1 * toneDiff) else 0.0
                var changed = 0
                pieceLum.clear()
                for (p in 0 until n) {
                    val v = d[p] - offset
                    if (kotlin.math.abs(v) > tau) changed++
                    if (kotlin.math.abs(v) > 0.5 * tau) pieceLum.add(patch[p])
                }
                // Texture: a piece brings edges (outline, highlights) even when its tone matches the
                // square, as a black piece on a dark square does. Empty squares are smooth. The
                // gradient is measured in the image, which still works for squares a few pixels tall.
                var edgeFraction = 0.0
                if (gradients != null) {
                    val g = gradients[sq]
                    val edgeTau = 0.2 * toneDiff
                    var edges = 0
                    for (p in 0 until n) if (g[p] > edgeTau) edges++
                    edgeFraction = edges.toDouble() / n
                }
                occ[sq] = maxOf(changed.toDouble() / n, minOf(1.0, 2.5 * edgeFraction))
                // Colour: brightness of the piece pixels between the dark (-0.5) and light (+0.5)
                // square tones, taken at the 70th percentile so shadows do not drag a light piece down.
                val lum = if (pieceLum.size >= n / 20) {
                    val sorted = pieceLum.toIntArray().sortedArray()
                    sorted[(sorted.size * 7) / 10].toDouble()
                } else {
                    median(patch).toDouble()
                }
                col[sq] = (lum - toneDark) / toneDiff - 0.5
            }
            return SquareFeatures(occ, col)
        }

        private fun median(a: IntArray): Double {
            val s = a.sortedArray()
            return s[s.size / 2].toDouble()
        }

        private fun median(a: DoubleArray): Double {
            val s = a.sortedArray()
            return s[s.size / 2]
        }
    }
}

/**
 * Decision thresholds on [SquareFeatures], per square shade (index 0 = dark, 1 = light).
 * [default] works for typical boards; [learn] tunes them from a photo of the starting position.
 */
class Calibration(
    val occThreshold: DoubleArray,
    val occScale: DoubleArray,
    val colourThreshold: DoubleArray,
    val colourScale: DoubleArray,
    val notes: List<String>,
) {
    val isUsable: Boolean get() = notes.none { it.startsWith("FAIL") }

    fun observe(f: SquareFeatures): Array<SquareObservation> = Array(64) { sq ->
        val shade = if (Square.isLight(sq)) 1 else 0
        val occ = sigmoid((f.occFraction[sq] - occThreshold[shade]) / occScale[shade])
        val white = sigmoid((f.colourScore[sq] - colourThreshold[shade]) / colourScale[shade])
        SquareObservation(occ, white, f.occFraction[sq], f.colourScore[sq])
    }

    private fun sigmoid(z: Double) = 1.0 / (1.0 + exp(-z))

    companion object {
        fun default(): Calibration = Calibration(
            doubleArrayOf(0.22, 0.22), doubleArrayOf(0.07, 0.07),
            doubleArrayOf(-0.5, -0.5), doubleArrayOf(0.25, 0.25),
            listOf("default thresholds"),
        )

        /** Learns thresholds from the features of a photo showing all 32 pieces on their starting squares. */
        fun learn(f: SquareFeatures): Calibration {
            val notes = ArrayList<String>()
            val occThreshold = DoubleArray(2)
            val occScale = DoubleArray(2)
            val colourThreshold = DoubleArray(2)
            val colourScale = DoubleArray(2)
            for (shade in 0..1) {
                val shadeName = if (shade == 0) "dark" else "light"
                val squares = (0 until 64).filter { (if (Square.isLight(it)) 1 else 0) == shade }
                val empty = squares.filter { Square.rank(it) in 2..5 }.map { f.occFraction[it] }
                val occupied = squares.filter { Square.rank(it) !in 2..5 }.map { f.occFraction[it] }
                val maxEmpty = empty.max()
                val minOcc = occupied.min()
                if (minOcc > maxEmpty) {
                    occThreshold[shade] = (maxEmpty + minOcc) / 2
                    occScale[shade] = maxOf((minOcc - maxEmpty) / 4, 0.02)
                    notes.add("OK occupancy on $shadeName squares: empty <= %.2f, pieces >= %.2f".format(maxEmpty, minOcc))
                } else {
                    val meanEmpty = empty.average()
                    val meanOcc = occupied.average()
                    occThreshold[shade] = (meanEmpty + meanOcc) / 2
                    occScale[shade] = maxOf((meanOcc - meanEmpty) / 4, 0.02)
                    val tag = if (meanOcc > meanEmpty + 0.15) "WARN" else "FAIL"
                    notes.add("$tag occupancy on $shadeName squares overlaps: empty up to %.2f, pieces from %.2f".format(maxEmpty, minOcc))
                }
                val whites = squares.filter { Square.rank(it) <= 1 }.map { f.colourScore[it] }
                val blacks = squares.filter { Square.rank(it) >= 6 }.map { f.colourScore[it] }
                val meanWhite = whites.average()
                val meanBlack = blacks.average()
                colourThreshold[shade] = (meanWhite + meanBlack) / 2
                colourScale[shade] = maxOf((meanWhite - meanBlack) / 4, 0.08)
                when {
                    whites.min() > blacks.max() -> notes.add("OK piece colour on $shadeName squares: white >= %.2f, black <= %.2f".format(whites.min(), blacks.max()))
                    meanWhite > meanBlack + 0.2 -> notes.add("WARN piece colour on $shadeName squares overlaps slightly")
                    else -> notes.add("FAIL cannot tell white from black pieces on $shadeName squares (white %.2f vs black %.2f)".format(meanWhite, meanBlack))
                }
            }
            return Calibration(occThreshold, occScale, colourThreshold, colourScale, notes)
        }
    }
}

/** Compares the square patches of two scans; squares a move touched should stand out. */
object ChangeDetector {
    /** Returns a 0..1 score per square; 0 means "looks like last time". */
    fun scores(previous: Array<IntArray>, current: Array<IntArray>): DoubleArray {
        val gain = Features.gain(previous, current)
        val diff = DoubleArray(64) { sq -> Features.compare(previous[sq], current[sq], gain).absDiff }
        val sorted = diff.sortedArray()
        val med = sorted[32]
        // A move touches 2 to 4 squares; anything within the typical spread of the other
        // squares (viewpoint and exposure changes affect them all) does not count.
        val spread = maxOf(sorted[48] - med, 3.0)
        return DoubleArray(64) { ((diff[it] - med - 2.0 * spread) / (3.0 * spread)).coerceIn(0.0, 1.0) }
    }
}

object Features {
    class Result(val absDiff: Double, val signedDiff: Double)

    /** Median ratio of baseline to current square brightness. Compensates auto-exposure changes. */
    fun gain(baseline: Array<IntArray>, current: Array<IntArray>): Double {
        val ratios = DoubleArray(64) { sq ->
            val b = baseline[sq].average()
            val c = current[sq].average()
            if (c < 1.0) 1.0 else b / c
        }
        ratios.sort()
        return (ratios[31] + ratios[32]) / 2
    }

    fun compare(base: IntArray, cur: IntArray, gain: Double): Result {
        var abs = 0.0
        var signed = 0.0
        for (i in base.indices) {
            val d = cur[i] * gain - base[i]
            abs += kotlin.math.abs(d)
            signed += d
        }
        return Result(abs / base.size, signed / base.size)
    }
}
