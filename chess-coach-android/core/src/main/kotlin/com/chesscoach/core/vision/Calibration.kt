package com.chesscoach.core.vision

import com.chesscoach.core.chess.Square
import kotlin.math.exp

/** What the scanner believes about one square. Probabilities are in 0..1. */
data class SquareObservation(val occupied: Double, val white: Double, val absDiff: Double, val signedDiff: Double) {
    /** 0 = empty, 1 = white, 2 = black, by the most likely reading. */
    val label: Int get() = if (occupied < 0.5) 0 else if (white >= 0.5) 1 else 2

    /** True when the reading is close to a decision boundary. */
    val unsure: Boolean get() = occupied in 0.3..0.7 || (occupied >= 0.5 && white in 0.3..0.7)
}

/**
 * Per-shade thresholds learned from the empty board and the starting position.
 * Index 0 = dark squares, 1 = light squares.
 */
class Calibration(
    val baseline: Array<IntArray>,
    val occThreshold: DoubleArray,
    val occScale: DoubleArray,
    val colorThreshold: DoubleArray,
    val colorScale: DoubleArray,
    val notes: List<String>,
) {
    val isUsable: Boolean get() = notes.none { it.startsWith("FAIL") }

    fun observe(samples: Array<IntArray>): Array<SquareObservation> {
        val gain = Features.gain(baseline, samples)
        return Array(64) { sq ->
            val shade = if (Square.isLight(sq)) 1 else 0
            val f = Features.compare(baseline[sq], samples[sq], gain)
            val occ = sigmoid((f.absDiff - occThreshold[shade]) / occScale[shade])
            val white = sigmoid((f.signedDiff - colorThreshold[shade]) / colorScale[shade])
            SquareObservation(occ, white, f.absDiff, f.signedDiff)
        }
    }

    private fun sigmoid(z: Double) = 1.0 / (1.0 + exp(-z))

    companion object {
        /**
         * Learns thresholds from [emptySamples] (no pieces) and [startSamples] (all 32 pieces on
         * their starting squares, White on ranks 1-2).
         */
        fun learn(emptySamples: Array<IntArray>, startSamples: Array<IntArray>): Calibration {
            val notes = ArrayList<String>()
            val gain = Features.gain(emptySamples, startSamples)
            val feats = Array(64) { Features.compare(emptySamples[it], startSamples[it], gain) }
            val occThreshold = DoubleArray(2)
            val occScale = DoubleArray(2)
            val colorThreshold = DoubleArray(2)
            val colorScale = DoubleArray(2)
            for (shade in 0..1) {
                val squares = (0 until 64).filter { (if (Square.isLight(it)) 1 else 0) == shade }
                val empty = squares.filter { Square.rank(it) in 2..5 }.map { feats[it].absDiff }
                val occupied = squares.filter { Square.rank(it) !in 2..5 }.map { feats[it].absDiff }
                val maxEmpty = empty.max()
                val minOcc = occupied.min()
                val shadeName = if (shade == 0) "dark" else "light"
                if (minOcc > maxEmpty) {
                    occThreshold[shade] = (maxEmpty + minOcc) / 2
                    occScale[shade] = maxOf((minOcc - maxEmpty) / 4, 0.5)
                    notes.add("OK occupancy on $shadeName squares: empty <= %.1f, pieces >= %.1f".format(maxEmpty, minOcc))
                } else {
                    val meanEmpty = empty.average()
                    val meanOcc = occupied.average()
                    occThreshold[shade] = (meanEmpty + meanOcc) / 2
                    occScale[shade] = maxOf((meanOcc - meanEmpty) / 4, 0.5)
                    val tag = if (meanOcc > meanEmpty * 1.3) "WARN" else "FAIL"
                    notes.add("$tag occupancy on $shadeName squares overlaps: empty up to %.1f, pieces from %.1f".format(maxEmpty, minOcc))
                }
                val whites = squares.filter { Square.rank(it) <= 1 }.map { feats[it].signedDiff }
                val blacks = squares.filter { Square.rank(it) >= 6 }.map { feats[it].signedDiff }
                val meanWhite = whites.average()
                val meanBlack = blacks.average()
                colorThreshold[shade] = (meanWhite + meanBlack) / 2
                colorScale[shade] = maxOf((meanWhite - meanBlack) / 4, 0.5)
                val minWhite = whites.min()
                val maxBlack = blacks.max()
                when {
                    minWhite > maxBlack -> notes.add("OK piece colour on $shadeName squares: white >= %.1f, black <= %.1f".format(minWhite, maxBlack))
                    meanWhite > meanBlack + 4 -> notes.add("WARN piece colour on $shadeName squares overlaps slightly")
                    else -> notes.add("FAIL cannot tell white from black pieces on $shadeName squares (white %.1f vs black %.1f)".format(meanWhite, meanBlack))
                }
            }
            return Calibration(emptySamples, occThreshold, occScale, colorThreshold, colorScale, notes)
        }
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
