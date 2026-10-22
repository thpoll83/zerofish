package com.chesscoach.core.vision

import com.chesscoach.core.chess.Square
import kotlin.math.abs

/**
 * A camera frame with its colour: the luma plane at full size and the two chroma planes at half
 * size, as the camera delivers them (YUV 4:2:0). As a [LumaImage] it is the luma plane, which
 * the grid finder uses on every board; the chroma is for reading pieces whose colour, not
 * brightness, sets them apart from their squares.
 */
class YuvImage(override val width: Int, override val height: Int, val y: IntArray, val u: IntArray, val v: IntArray) : LumaImage {
    val chromaWidth = (width + 1) / 2
    val chromaHeight = (height + 1) / 2

    init {
        require(y.size == width * height && u.size == chromaWidth * chromaHeight && v.size == chromaWidth * chromaHeight)
    }

    override fun luma(x: Int, y: Int): Int = this.y[y * width + x]
    fun u(x: Int, y: Int): Int = u[(y shr 1) * chromaWidth + (x shr 1)]
    fun v(x: Int, y: Int): Int = v[(y shr 1) * chromaWidth + (x shr 1)]

    /** The U plane addressed in full-size coordinates, for the square sampler. */
    val uView: LumaImage = object : LumaImage {
        override val width get() = this@YuvImage.width
        override val height get() = this@YuvImage.height
        override fun luma(x: Int, y: Int) = u(x, y)
    }

    /** The V plane addressed in full-size coordinates, for the square sampler. */
    val vView: LumaImage = object : LumaImage {
        override val width get() = this@YuvImage.width
        override val height get() = this@YuvImage.height
        override fun luma(x: Int, y: Int) = v(x, y)
    }
}

/**
 * A colour shift: one grayscale channel made from luma and chroma, `128 + gain * (wy*Y + wu*U +
 * wv*V - centre)`, chosen so that the pieces of a particular set stand out from the squares of
 * a particular board. On a red board with brown and yellow pieces the brown pieces are as dark
 * as the red squares and the yellow ones as light as the cream squares in plain luma, while a
 * channel leaning on the chroma tells them apart.
 */
class ColorProjection(val wy: Double, val wu: Double, val wv: Double, val centre: Double, val gain: Double) {
    fun value(y: Int, u: Int, v: Int): Int = (128 + gain * (wy * y + wu * u + wv * v - centre)).toInt().coerceIn(0, 255)

    /** The frame with its luma plane replaced by the shifted channel; the chroma stays for the colour features. */
    fun apply(image: YuvImage): YuvImage {
        val w = image.width
        val out = IntArray(w * image.height)
        for (yy in 0 until image.height) {
            val row = yy * w
            val crow = (yy shr 1) * image.chromaWidth
            for (x in 0 until w) {
                val ci = crow + (x shr 1)
                out[row + x] = value(image.y[row + x], image.u[ci], image.v[ci])
            }
        }
        return YuvImage(w, image.height, out, image.u, image.v)
    }

    override fun toString() = "%.0f Y %+.0f U %+.0f V, gain %.2f".format(wy, wu, wv, gain)

    companion object {
        /** The channels tried besides luma: each chroma plane alone, and sums and differences. */
        private val directions: List<DoubleArray> = listOf(
            doubleArrayOf(0.0, 1.0, 0.0), doubleArrayOf(0.0, 0.0, 1.0), doubleArrayOf(0.0, 1.0, 1.0), doubleArrayOf(0.0, 1.0, -1.0),
            doubleArrayOf(1.0, 1.0, 0.0), doubleArrayOf(1.0, -1.0, 0.0), doubleArrayOf(1.0, 0.0, 1.0), doubleArrayOf(1.0, 0.0, -1.0),
            doubleArrayOf(1.0, 1.0, 1.0), doubleArrayOf(1.0, 1.0, -1.0), doubleArrayOf(1.0, -1.0, 1.0), doubleArrayOf(1.0, -1.0, -1.0),
        )

        /**
         * Luma is kept whenever it reads the pieces apart from the squares at all: the tracker
         * accepts a starting position from an occupancy margin of 0.08, and a channel that read
         * marginally better on the learning frame lost the game on a wooden board under changing
         * light. A shift is taken only when luma fails outright and the shift reads clearly.
         */
        private const val LUMA_FAILS_BELOW = 0.08
        private const val SHIFT_READS_FROM = 0.15

        /**
         * Luma that reads the position but leaves a square hidden behind a piece reading as
         * clearly as a piece (a gap this far below zero) fits soft thresholds; it gives way to
         * a channel in which every piece beats every hidden square, so that the thresholds fit
         * clean. A near tie in luma is left alone: a channel that merely fitted a little
         * cleaner on the learning frame lost a game on a wooden board.
         */
        private const val LUMA_UNCLEAN_BELOW = -0.05
        private const val SHIFT_CLEAN_FROM = 0.0

        /** How a channel reads the board, judged as the tracker judges a starting position. */
        class Reading(val occupancyMargin: Double, val colourMargin: Double, val cleanGap: Double = 0.0) {
            /**
             * One number: pieces apart from empty squares first, white apart from black second.
             * The colour margin counts up to the level the tracker is comfortable with (0.6), so
             * a channel cannot buy a worse occupancy reading with ever more colour contrast.
             */
            val score: Double get() = occupancyMargin + 0.3 * colourMargin.coerceIn(-0.6, 0.6)
            /** Whether the thresholds would split pieces from every empty square, hidden ones included, on both shades (see [cleanGap]). */
            val clean: Boolean get() = cleanGap >= SHIFT_CLEAN_FROM
            /** Whether a hidden square reads as clearly as a piece, so the thresholds would be soft. */
            val unclean: Boolean get() = cleanGap < LUMA_UNCLEAN_BELOW
            override fun toString() = "occupancy %.3f, colour %.3f, clean gap %.3f".format(occupancyMargin, colourMargin, cleanGap)
        }

        /**
         * Reads [image] with the square sampler and measures how clearly the pieces of [occupancy]
         * stand out: the fourth-weakest piece against the third-strongest empty square (as the
         * tracker demands of a starting position), and white pieces against black.
         */
        fun read(image: LumaImage, geometry: BoardGeometry, occupancy: IntArray): Reading {
            val located = BoardLocator.locate(image, geometry.corners, Calibration.default(), occupancy, 0, allowRotation = false)
            val m = Calibration.Margins.of(located.features, occupancy)
            return Reading(m.occupancy, m.colour, cleanGap(located.features.occFraction, occupancy))
        }

        /**
         * The smaller, over the two shades, of the gap between the weakest piece and the
         * strongest empty square of the middle ranks, the squares hidden behind the pieces
         * included: what [Calibration.learn] fits its thresholds on. Negative when a hidden
         * square reads as a piece, which leaves the thresholds soft (see [Calibration.learn]).
         */
        private fun cleanGap(occ: DoubleArray, occupancy: IntArray): Double {
            var gap = Double.MAX_VALUE
            for (shade in 0..1) {
                val squares = (0 until 64).filter { (if (Square.isLight(it)) 1 else 0) == shade }
                val empties = squares.filter { occupancy[it] == 0 && Square.rank(it) in 2..5 }
                val pieces = squares.filter { occupancy[it] != 0 }
                if (empties.isEmpty() || pieces.isEmpty()) return 0.0
                gap = minOf(gap, pieces.minOf { occ[it] } - empties.maxOf { occ[it] })
            }
            return gap
        }

        /**
         * Chooses the channel through which the sampler reads the pieces of [occupancy] most
         * clearly on [image], given the board's [geometry] (oriented: a1 at board origin),
         * normally with the starting position. Returns null when plain luma reads as well:
         * wooden and plastic sets on most boards differ from their squares in brightness, and
         * nothing is gained by changing what has worked on them. Each channel is normalised so
         * that the square means span the same range as a well-lit luma picture, and white pieces
         * come out brighter than black ones.
         */
        fun choose(image: YuvImage, geometry: BoardGeometry, occupancy: IntArray, log: ((String) -> Unit)? = null): ColorProjection? {
            val luma = read(image, geometry, occupancy)
            log?.invoke("luma reads $luma")
            // Luma that reads the position is kept unless it leaves a hidden square among the
            // pieces (soft thresholds, see Calibration.learn); then it gives way only to a
            // channel that reads clearly and fits clean thresholds by a clear gap.
            if (luma.occupancyMargin >= LUMA_FAILS_BELOW && !luma.unclean) return null
            val needClean = luma.occupancyMargin >= LUMA_FAILS_BELOW
            var best: ColorProjection? = null
            var bestScore = if (needClean) SHIFT_READS_FROM else maxOf(luma.score, SHIFT_READS_FROM)
            for (d in directions) {
                val p = normalised(image, geometry, occupancy, d) ?: continue
                val r = read(p.apply(image), geometry, occupancy)
                log?.invoke("$p reads $r")
                if (needClean && !r.clean) continue
                if (r.occupancyMargin >= SHIFT_READS_FROM && r.score > bestScore) { best = p; bestScore = r.score }
            }
            return best
        }

        /** The projection along [d] with centre, gain and sign set from the square means of [image]. */
        private fun normalised(image: YuvImage, geometry: BoardGeometry, occupancy: IntArray, d: DoubleArray): ColorProjection? {
            val values = DoubleArray(64)
            for (sq in 0 until 64) {
                val w = geometry.sampleWindow(Square.file(sq), Square.rank(sq))
                var n = 0
                var acc = 0.0
                for (i in 0 until 6) for (j in 0 until 6) {
                    val p = geometry.toImage(w[0] + (w[1] - w[0]) * (i + 0.5) / 6, w[2] + (w[3] - w[2]) * (j + 0.5) / 6)
                    val x = p.x.toInt(); val y = p.y.toInt()
                    if (x < 0 || y < 0 || x >= image.width || y >= image.height) continue
                    acc += d[0] * image.luma(x, y) + d[1] * image.u(x, y) + d[2] * image.v(x, y)
                    n++
                }
                if (n == 0) return null
                values[sq] = acc / n
            }
            val whites = (0 until 64).filter { occupancy[it] == 1 }.map { values[it] }
            val blacks = (0 until 64).filter { occupancy[it] == 2 }.map { values[it] }
            val sign = if (whites.isEmpty() || blacks.isEmpty() || whites.average() >= blacks.average()) 1.0 else -1.0
            val centre = values.average()
            val spread = values.maxOf { abs(it - centre) }.coerceAtLeast(1.0)
            return ColorProjection(sign * d[0], sign * d[1], sign * d[2], sign * centre, 110.0 / spread)
        }
    }
}
