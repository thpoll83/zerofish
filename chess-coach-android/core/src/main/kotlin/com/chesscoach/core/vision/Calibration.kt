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

/**
 * What each square looked like the last time it was known to be empty, as sampled through the
 * locked grid: luma, gradient and chroma patches. A square compared with its own empty picture
 * differs only where something stands on it; its wood grain, print and shadow cancel exactly,
 * which the shade-wide template cannot do. A square occupied from the start has no picture until
 * it is vacated, but every square a piece arrives on was empty just before.
 */
class SquareTemplates {
    val luma = arrayOfNulls<IntArray>(64)
    val gradient = arrayOfNulls<IntArray>(64)
    val u = arrayOfNulls<IntArray>(64)
    val v = arrayOfNulls<IntArray>(64)

    fun has(sq: Int) = luma[sq] != null

    /** Records or refreshes a square's empty picture; a refresh blends in [blend] of the new one. */
    fun remember(sq: Int, lumaPatch: IntArray, gradientPatch: IntArray, uPatch: IntArray?, vPatch: IntArray?, blend: Double) {
        luma[sq] = mix(luma[sq], lumaPatch, blend)
        gradient[sq] = mix(gradient[sq], gradientPatch, blend)
        u[sq] = uPatch?.let { mix(u[sq], it, blend) }
        v[sq] = vPatch?.let { mix(v[sq], it, blend) }
    }

    fun clear() {
        for (i in 0 until 64) { luma[i] = null; gradient[i] = null; u[i] = null; v[i] = null }
    }

    private fun mix(old: IntArray?, new: IntArray, blend: Double): IntArray =
        if (old == null || old.size != new.size) new.copyOf() else IntArray(new.size) { (old[it] + blend * (new[it] - old[it])).toInt() }
}

/**
 * Per-square features that do not depend on a fixed camera: see [SquareFeatures.extract].
 * [occFraction] and [colourScore] come from luma (texture and brightness); [chromaFraction],
 * [chromaDu] and [chromaDv] from the colour planes when the frame carries them, else null.
 */
class SquareFeatures(
    val occFraction: DoubleArray,
    val colourScore: DoubleArray,
    val chromaFraction: DoubleArray? = null,
    val chromaDu: DoubleArray? = null,
    val chromaDv: DoubleArray? = null,
    /** The two luma cues behind [occFraction] on their own: pixels of another tone, and edges. */
    val toneFraction: DoubleArray? = null,
    val edgeFraction: DoubleArray? = null,
) {
    val hasChroma: Boolean get() = chromaFraction != null

    companion object {
        /**
         * Builds, for each square shade, an "empty square" template as the per-pixel median over
         * the 32 squares of that shade in this very photo (pieces never cover more than half of
         * them at any pixel), then measures how much of each square differs from its template and
         * whether the differing pixels are brighter or darker than the board.
         */
        fun extract(
            patches: Array<IntArray>,
            gradients: Array<IntArray>? = null,
            uPatches: Array<IntArray>? = null,
            vPatches: Array<IntArray>? = null,
            /** The position the board is believed to hold (0 empty, else a piece), when known. */
            expectedOccupancy: IntArray? = null,
            /** Each square's own empty picture where one is known; it replaces the shade template there. */
            own: SquareTemplates? = null,
        ): SquareFeatures {
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
            val tone = DoubleArray(64)
            val edge = DoubleArray(64)
            val col = DoubleArray(64)
            val d = DoubleArray(n)
            val pieceLum = ArrayList<Int>(n)
            for (sq in 0 until 64) {
                val ownLuma = own?.luma?.get(sq)?.takeIf { it.size == n }
                val t = ownLuma ?: templates[if (Square.isLight(sq)) 1 else 0]
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
                    // against the square's own empty picture, only edges it did not have count
                    val g0 = own?.gradient?.get(sq)?.takeIf { it.size == n }
                    val edgeTau = 0.2 * toneDiff
                    var edges = 0
                    for (p in 0 until n) if (g[p] - (g0?.get(p) ?: 0) > edgeTau) edges++
                    edgeFraction = edges.toDouble() / n
                }
                tone[sq] = changed.toDouble() / n
                edge[sq] = edgeFraction
                occ[sq] = maxOf(tone[sq], minOf(1.0, 2.5 * edgeFraction))
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
            if (uPatches == null || vPatches == null) return SquareFeatures(occ, col, toneFraction = tone, edgeFraction = edge)
            return withChroma(occ, col, tone, edge, uPatches, vPatches, expectedOccupancy, own)
        }

        /**
         * The same idea in colour: an "empty square" chroma template per shade (per-pixel median
         * of U and V over the 32 squares of that shade), the distance of every pixel from it,
         * and the fraction of a square's pixels further away than the board's own chroma noise
         * allows. Wood grain is a brightness pattern of one hue, so it stays close to the template
         * in chroma while a piece of another hue does not. The mean chroma offset of the pixels
         * that differ says which way the piece's colour lies, for telling white from black.
         */
        private fun withChroma(occ: DoubleArray, col: DoubleArray, tone: DoubleArray, edge: DoubleArray, uPatches: Array<IntArray>, vPatches: Array<IntArray>, expected: IntArray?, own: SquareTemplates?): SquareFeatures {
            val n = uPatches[0].size
            val templates = Array(2) { shade ->
                val squares = (0 until 64).filter { (if (Square.isLight(it)) 1 else 0) == shade }
                val tmp = IntArray(squares.size)
                val tu = IntArray(n) { p -> for ((k, sq) in squares.withIndex()) tmp[k] = uPatches[sq][p]; tmp.sort(); (tmp[tmp.size / 2 - 1] + tmp[tmp.size / 2]) / 2 }
                val tv = IntArray(n) { p -> for ((k, sq) in squares.withIndex()) tmp[k] = vPatches[sq][p]; tmp.sort(); (tmp[tmp.size / 2 - 1] + tmp[tmp.size / 2]) / 2 }
                tu to tv
            }
            // The light's tint drifts across the board (a lamp on one side, a window on the
            // other), by more than a piece differs from its square on a hard board. Each square's
            // median offset from the template is fitted, per shade, by a plane over file and rank
            // through the squares believed empty (pieces stand in rows, which a fit over every
            // square would take for a gradient), and that fitted tint is the square's own reference.
            val medU = DoubleArray(64); val medV = DoubleArray(64)
            for (sq in 0 until 64) {
                val (tu, tv) = templates[if (Square.isLight(sq)) 1 else 0]
                medU[sq] = median(IntArray(n) { p -> uPatches[sq][p] - tu[p] })
                medV[sq] = median(IntArray(n) { p -> vPatches[sq][p] - tv[p] })
            }
            val tintU = fitPlanes(medU, expected); val tintV = fitPlanes(medV, expected)
            // distances of every pixel of every square from its shade's template, tint removed; a
            // square with its own empty picture is measured against that instead, with the
            // median offset of its pixels removed (the light may have changed since)
            val ownU = Array(64) { sq -> own?.u?.get(sq)?.takeIf { it.size == n } }
            val ownV = Array(64) { sq -> own?.v?.get(sq)?.takeIf { it.size == n } }
            val dist = Array(64) { sq ->
                val ou = ownU[sq]; val ov = ownV[sq]
                if (ou != null && ov != null) {
                    val offU = median(IntArray(n) { p -> uPatches[sq][p] - ou[p] })
                    val offV = median(IntArray(n) { p -> vPatches[sq][p] - ov[p] })
                    DoubleArray(n) { p -> val du = uPatches[sq][p] - ou[p] - offU; val dv = vPatches[sq][p] - ov[p] - offV; kotlin.math.sqrt(du * du + dv * dv) }
                } else {
                    val (tu, tv) = templates[if (Square.isLight(sq)) 1 else 0]
                    DoubleArray(n) { p -> val du = uPatches[sq][p] - tu[p] - tintU[sq]; val dv = vPatches[sq][p] - tv[p] - tintV[sq]; kotlin.math.sqrt(du * du + dv * dv) }
                }
            }
            // The board's own chroma noise per shade: the median distance over all its pixels
            // (pieces cover less than half of them). A piece is a pixel well beyond that.
            val tau = DoubleArray(2) { shade ->
                val all = (0 until 64).filter { (if (Square.isLight(it)) 1 else 0) == shade }.flatMap { dist[it].asList() }.sorted()
                maxOf(2.0 * all[all.size / 2], 5.0)
            }
            val fraction = DoubleArray(64)
            val du = DoubleArray(64)
            val dv = DoubleArray(64)
            for (sq in 0 until 64) {
                val shade = if (Square.isLight(sq)) 1 else 0
                val (tu, tv) = templates[shade]
                var changed = 0
                var su = 0.0; var sv = 0.0
                for (p in 0 until n) {
                    if (dist[sq][p] > tau[shade]) { changed++; su += uPatches[sq][p] - tu[p] - tintU[sq]; sv += vPatches[sq][p] - tv[p] - tintV[sq] }
                }
                fraction[sq] = changed.toDouble() / n
                if (changed >= n / 20) { du[sq] = su / changed; dv[sq] = sv / changed } else {
                    // nothing differs: the mean offset of the whole window, near zero
                    for (p in 0 until n) { su += uPatches[sq][p] - tu[p] - tintU[sq]; sv += vPatches[sq][p] - tv[p] - tintV[sq] }
                    du[sq] = su / n; dv[sq] = sv / n
                }
            }
            return SquareFeatures(occ, col, fraction, du, dv, tone, edge)
        }

        /**
         * Fits, per shade, a plane a + b*file + c*rank to the 32 values of that shade by least
         * squares, twice: the second pass leaves out the squares whose residual exceeds twice
         * the median residual (the squares with pieces). Returns the fitted value per square.
         */
        private fun fitPlanes(values: DoubleArray, expected: IntArray?): DoubleArray {
            val out = DoubleArray(64)
            for (shade in 0..1) {
                val all = (0 until 64).filter { (if (Square.isLight(it)) 1 else 0) == shade }
                val known = if (expected != null) all.filter { expected[it] == 0 } else emptyList()
                var squares = if (known.size >= 6) known else all
                var coef = plane(squares, values)
                val residual = DoubleArray(64) { sq -> kotlin.math.abs(values[sq] - (coef[0] + coef[1] * Square.file(sq) + coef[2] * Square.rank(sq))) }
                val limit = maxOf(2.0 * median(squares.map { residual[it] }.toDoubleArray()), 2.0)
                val inliers = squares.filter { residual[it] <= limit }
                if (inliers.size >= 8) { squares = inliers; coef = plane(squares, values) }
                for (sq in all) out[sq] = coef[0] + coef[1] * Square.file(sq) + coef[2] * Square.rank(sq)
            }
            return out
        }

        /** Least-squares plane a + b*file + c*rank through the given squares' values. */
        private fun plane(squares: List<Int>, values: DoubleArray): DoubleArray {
            // normal equations for 3 unknowns
            val m = Array(3) { DoubleArray(4) }
            for (sq in squares) {
                val x = doubleArrayOf(1.0, Square.file(sq).toDouble(), Square.rank(sq).toDouble())
                for (i in 0..2) { for (j in 0..2) m[i][j] += x[i] * x[j]; m[i][3] += x[i] * values[sq] }
            }
            for (i in 0..2) {
                var pivot = i
                for (r in i + 1..2) if (kotlin.math.abs(m[r][i]) > kotlin.math.abs(m[pivot][i])) pivot = r
                val t = m[i]; m[i] = m[pivot]; m[pivot] = t
                if (kotlin.math.abs(m[i][i]) < 1e-9) return doubleArrayOf(values.filterIndexed { k, _ -> k in squares }.average(), 0.0, 0.0)
                for (r in 0..2) if (r != i) {
                    val f = m[r][i] / m[i][i]
                    for (c in i..3) m[r][c] -= f * m[i][c]
                }
            }
            return DoubleArray(3) { m[it][3] / m[it][it] }
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
 * Decision thresholds on [SquareFeatures], per square shade (index 0 = dark, 1 = light), and
 * which cue each decision is read from: occupancy from luma texture or from the colour distance
 * to the empty squares, piece colour from brightness or from the chroma offset along the
 * direction that separates the two sets. [default] reads luma only and works for typical boards;
 * [learn] tunes the thresholds from a photo of the starting position and picks, per shade, the
 * cue that separates better there.
 */
class Calibration(
    val occThreshold: DoubleArray,
    val occScale: DoubleArray,
    val colourThreshold: DoubleArray,
    val colourScale: DoubleArray,
    val notes: List<String>,
    val occFromChroma: BooleanArray = BooleanArray(2),
    val colourFromChroma: BooleanArray = BooleanArray(2),
    /** Per shade: occupancy is the larger of the luma and the colour reading (each cue sees the pieces the other misses). */
    val occWithChroma: BooleanArray = BooleanArray(2),
    /** Unit direction in (du, dv) from the black pieces towards the white ones. */
    val chromaDir: DoubleArray = doubleArrayOf(0.0, 0.0),
    /** Occupancy cues besides the one read first, each fitted on the learning frame; see [reconcile]. */
    val backups: List<BackupCue> = emptyList(),
) {
    val isUsable: Boolean get() = notes.none { it.startsWith("FAIL") }

    /** One occupancy cue: pixels of another tone than the square, edges, or colour distance. */
    enum class Cue { TONE, EDGE, CHROMA }

    /** A cue's threshold and scale per shade, and whether it separated pieces from empty squares cleanly on the learning frame. */
    class BackupCue(val cue: Cue, val threshold: DoubleArray, val scale: DoubleArray, val ok: BooleanArray) {
        fun value(f: SquareFeatures, sq: Int): Double? = when (cue) {
            Cue.TONE -> f.toneFraction?.get(sq)
            Cue.EDGE -> f.edgeFraction?.get(sq)
            Cue.CHROMA -> f.chromaFraction?.get(sq)
        }
    }

    fun observe(f: SquareFeatures): Array<SquareObservation> = Array(64) { sq ->
        val shade = if (Square.isLight(sq)) 1 else 0
        val occFeature = when {
            occWithChroma[shade] && f.chromaFraction != null -> maxOf(f.occFraction[sq], f.chromaFraction[sq])
            occFromChroma[shade] && f.chromaFraction != null -> f.chromaFraction[sq]
            else -> f.occFraction[sq]
        }
        val colFeature = if (colourFromChroma[shade] && f.chromaDu != null) chromaColour(f, sq, chromaDir) else f.colourScore[sq]
        val primary = sigmoid((occFeature - occThreshold[shade]) / occScale[shade])
        val opinions = backups.mapNotNull { b -> if (!b.ok[shade]) null else b.value(f, sq)?.let { sigmoid((it - b.threshold[shade]) / b.scale[shade]) } }
        val occ = reconcile(primary, opinions)
        val white = sigmoid((colFeature - colourThreshold[shade]) / colourScale[shade])
        SquareObservation(occ, white, occFeature, colFeature)
    }

    private fun sigmoid(z: Double) = 1.0 / (1.0 + exp(-z))

    /**
     * The reading with the backup cues heard. A cue is confident below 0.3 or above 0.7. A
     * primary reading that is unsure takes the side the confident backups agree on. A confident
     * primary reading that a confident backup contradicts keeps its side, but weakly (0.4 or
     * 0.6): two cues disagree, so the square settles little and the move search must lean on
     * the others. An empty square lit brighter than the shade's typical square reads as a white
     * piece by tone, while its edges say empty; a black piece on a dark square reads as empty by
     * tone, while its edges say piece.
     */
    fun reconcile(primary: Double, opinions: List<Double>): Double {
        fun confident(x: Double) = x < 0.3 || x > 0.7
        val sure = opinions.filter { confident(it) }
        if (sure.isEmpty()) return primary
        if (!confident(primary)) {
            return when {
                sure.all { it > 0.5 } -> sure.max()
                sure.all { it < 0.5 } -> sure.min()
                else -> primary
            }
        }
        val against = sure.any { (it > 0.5) != (primary > 0.5) }
        return if (!against) primary else if (primary > 0.5) 0.6 else 0.4
    }

    /**
     * How clearly a set of features separates the pieces of a known position from the empty
     * squares (the fourth-weakest piece against the third-strongest empty square, as the tracker
     * demands of a starting position) and white pieces from black, by each cue and by the better
     * one. Used while learning, for the view quality, and for choosing a colour channel.
     */
    class Margins(
        val occupancyTexture: Double,
        val occupancyChroma: Double?,
        val colourLuma: Double,
        val colourChroma: Double?,
        val chromaDir: DoubleArray,
        /** By the larger of the luma and the colour reading per square. */
        val occupancyBoth: Double? = null,
    ) {
        val occupancy: Double get() = maxOf(occupancyTexture, occupancyChroma ?: Double.NEGATIVE_INFINITY, occupancyBoth ?: Double.NEGATIVE_INFINITY)
        val colour: Double get() = maxOf(colourLuma, colourChroma ?: Double.NEGATIVE_INFINITY)

        override fun toString() = "occupancy %.3f (texture %.3f, colour %s), piece colour %.2f (brightness %.2f, chroma %s)".format(
            occupancy, occupancyTexture, occupancyChroma?.let { "%.3f".format(it) } ?: "-", colour, colourLuma, colourChroma?.let { "%.2f".format(it) } ?: "-",
        )

        companion object {
            /** [ignore] marks squares left out as empties: those hidden behind a piece from the camera read as occupied whatever stands there. */
            fun of(f: SquareFeatures, occupancy: IntArray, ignore: BooleanArray? = null): Margins {
                fun occMargin(values: DoubleArray): Double {
                    val empties = (0 until 64).filter { occupancy[it] == 0 && ignore?.get(it) != true }.map { values[it] }.sorted()
                    val pieces = (0 until 64).filter { occupancy[it] != 0 }.map { values[it] }.sorted()
                    return if (pieces.size >= 4 && empties.size >= 3) pieces[3] - empties[empties.size - 3] else 0.0
                }
                val whites = (0 until 64).filter { occupancy[it] == 1 }
                val blacks = (0 until 64).filter { occupancy[it] == 2 }
                val colourLuma = if (whites.isNotEmpty() && blacks.isNotEmpty()) whites.map { f.colourScore[it] }.average() - blacks.map { f.colourScore[it] }.average() else 0.0
                var dir = doubleArrayOf(0.0, 0.0)
                var colourChroma: Double? = null
                if (f.chromaDu != null && f.chromaDv != null && whites.isNotEmpty() && blacks.isNotEmpty()) {
                    val dx = whites.map { f.chromaDu[it] }.average() - blacks.map { f.chromaDu[it] }.average()
                    val dy = whites.map { f.chromaDv[it] }.average() - blacks.map { f.chromaDv[it] }.average()
                    val len = kotlin.math.hypot(dx, dy)
                    if (len > 1e-6) {
                        dir = doubleArrayOf(dx / len, dy / len)
                        colourChroma = whites.map { chromaColour(f, it, dir) }.average() - blacks.map { chromaColour(f, it, dir) }.average()
                    }
                }
                val both = f.chromaFraction?.let { c -> occMargin(DoubleArray(64) { maxOf(f.occFraction[it], c[it]) }) }
                return Margins(occMargin(f.occFraction), f.chromaFraction?.let { occMargin(it) }, colourLuma, colourChroma, dir, both)
            }
        }
    }

    companion object {
        /** Chroma units per unit of piece-colour score: an offset of 20 in (U, V) reads as 1.0. */
        private const val CHROMA_UNIT = 20.0

        /** The chroma offset of a square's differing pixels along [dir], in the same units as the brightness colour score. */
        fun chromaColour(f: SquareFeatures, sq: Int, dir: DoubleArray): Double =
            ((f.chromaDu!![sq]) * dir[0] + (f.chromaDv!![sq]) * dir[1]) / CHROMA_UNIT

        fun default(): Calibration = Calibration(
            doubleArrayOf(0.22, 0.22), doubleArrayOf(0.07, 0.07),
            doubleArrayOf(-0.35, -0.35), doubleArrayOf(0.25, 0.25),
            listOf("default thresholds"),
        )

        /** Threshold, scale and a note for one cue on one shade, plus how well it separates (gap over spread). */
        private class Fit(val threshold: Double, val scale: Double, val note: String, val separation: Double, val ok: Boolean, val maxEmpty: Double = 0.0, val minOcc: Double = 0.0)

        private fun fit(empty: List<Double>, occupied: List<Double>, what: String, shadeName: String, warnGap: Double, minScale: Double): Fit {
            val maxEmpty = empty.max()
            val minOcc = occupied.min()
            val meanEmpty = empty.average()
            val meanOcc = occupied.average()
            val spread = kotlin.math.sqrt((empty.sumOf { (it - meanEmpty) * (it - meanEmpty) } + occupied.sumOf { (it - meanOcc) * (it - meanOcc) }) / (empty.size + occupied.size)) + 0.01
            val separation = (meanOcc - meanEmpty) / spread
            return if (minOcc > maxEmpty) {
                Fit((maxEmpty + minOcc) / 2, maxOf((minOcc - maxEmpty) / 4, minScale), "OK $what on $shadeName squares: %.2f vs %.2f".format(maxEmpty, minOcc), separation, true, maxEmpty, minOcc)
            } else {
                val tag = if (meanOcc > meanEmpty + warnGap) "WARN" else "FAIL"
                Fit((meanEmpty + meanOcc) / 2, maxOf((meanOcc - meanEmpty) / 4, minScale), "$tag $what on $shadeName squares overlaps: %.2f vs %.2f".format(maxEmpty, minOcc), separation, false, maxEmpty, minOcc)
            }
        }

        /**
         * Learns thresholds from the features of a photo showing all 32 pieces on their starting
         * squares. Per shade, occupancy is read from luma texture and piece colour from brightness,
         * the cues proven on wooden and plastic sets over whole games; the colour cues (distance
         * from the empty squares' chroma, chroma offset between the sets) take over only where the
         * proven cue fails to separate the two groups on the learning frame and the colour cue
         * separates them better. A cue that merely looked a little better on the learning frame
         * applied a wrong move later in a game, so the switch is not made on a small margin.
         */
        /**
         * The squares of the starting position that a piece hides from the camera: the first
         * and second square beyond each piece along the step its body covers in the picture.
         * From a low seat behind White, the third rank lies in the pawns' bodies and reads as
         * occupied whatever stands there, and counted as empty it would make every cue look as
         * if it failed.
         */
        fun coveredAtStart(geometry: BoardGeometry): BooleanArray {
            val start = IntArray(64) { sq -> when (Square.rank(sq)) { 0, 1 -> 1; 6, 7 -> 2; else -> 0 } }
            val covered = BooleanArray(64)
            for (sq in 0 until 64) {
                if (start[sq] == 0) continue
                for ((df, dr) in geometry.coverSteps(Square.file(sq), Square.rank(sq))) for (k in 1..2) {
                    val ff = Square.file(sq) + k * df
                    val rr = Square.rank(sq) + k * dr
                    if (ff in 0..7 && rr in 0..7) covered[Square.of(ff, rr)] = true
                }
            }
            return covered
        }

        fun learn(f: SquareFeatures, covered: BooleanArray? = null): Calibration {
            val notes = ArrayList<String>()
            val occThreshold = DoubleArray(2)
            val occScale = DoubleArray(2)
            val colourThreshold = DoubleArray(2)
            val colourScale = DoubleArray(2)
            val occFromChroma = BooleanArray(2)
            val colourFromChroma = BooleanArray(2)
            val occWithChroma = BooleanArray(2)
            val start = IntArray(64) { sq -> when (Square.rank(sq)) { 0, 1 -> 1; 6, 7 -> 2; else -> 0 } }
            val margins = Margins.of(f, start, covered)
            val backups = listOf(Cue.TONE, Cue.EDGE, Cue.CHROMA).map { BackupCue(it, DoubleArray(2), DoubleArray(2), BooleanArray(2)) }
            for (shade in 0..1) {
                val shadeName = if (shade == 0) "dark" else "light"
                val squares = (0 until 64).filter { (if (Square.isLight(it)) 1 else 0) == shade }
                val pieceSq = squares.filter { Square.rank(it) !in 2..5 }
                // The empty squares of the middle ranks set the threshold, the ones hidden behind
                // the pieces included: such squares read as occupied to a degree, and the threshold
                // between the means keeps as many of them below it as the pieces allow. (Leaving
                // them out lowered the threshold until every hidden square read as a piece.)
                val emptySq = squares.filter { Square.rank(it) in 2..5 }
                var occ = fit(emptySq.map { f.occFraction[it] }, pieceSq.map { f.occFraction[it] }, "occupancy (texture)", shadeName, 0.15, 0.02)
                f.chromaFraction?.let { c ->
                    // Yellow pieces on cream squares are invisible to the luma cues and plain to the
                    // colour cue; brown pieces on the same squares the reverse. Where the luma cue
                    // fails, the larger of the two readings per square is tried before colour alone.
                    if (!occ.ok) {
                        val byColour = fit(emptySq.map { c[it] }, pieceSq.map { c[it] }, "occupancy (colour)", shadeName, 0.15, 0.02)
                        val both = DoubleArray(64) { maxOf(f.occFraction[it], c[it]) }
                        val byBoth = fit(emptySq.map { both[it] }, pieceSq.map { both[it] }, "occupancy (texture or colour)", shadeName, 0.15, 0.02)
                        val better = listOf(byBoth to 2, byColour to 1).filter { (fit, _) -> fit.separation > occ.separation }
                            .maxWithOrNull(compareBy({ (fit, _) -> if (fit.ok) 1 else 0 }, { (fit, _) -> fit.separation }))
                        if (better != null) {
                            occ = better.first
                            if (better.second == 2) occWithChroma[shade] = true else occFromChroma[shade] = true
                        }
                    }
                }
                occThreshold[shade] = occ.threshold; occScale[shade] = occ.scale; notes.add(occ.note)
                // The other cues, each on its own, stand by for squares the first one misreads;
                // only a cue that separates the two groups cleanly here is trusted to contradict it.
                val okBackups = ArrayList<String>()
                for (b in backups) {
                    if (b.cue == Cue.CHROMA && (occFromChroma[shade] || occWithChroma[shade])) continue
                    val values = (0 until 64).map { b.value(f, it) }
                    if (values.any { it == null }) continue
                    val (gap, minScale) = if (b.cue == Cue.EDGE) 0.06 to 0.01 else 0.15 to 0.02
                    val bf = fit(emptySq.map { values[it]!! }, pieceSq.map { values[it]!! }, "backup", shadeName, gap, minScale)
                    // a clean split alone is not trust: the gap must be wide against the cue's
                    // noise (a split of 0.17 against 0.19 on one frame contradicted every frame after)
                    // (and the pieces must register plainly: edges of 0.06 on flat pieces fitted a
                    // threshold so low that an empty square's jitter passed for a piece)
                    val trusted = bf.ok && bf.minOcc - bf.maxEmpty >= (if (b.cue == Cue.EDGE) 0.04 else 0.08) && bf.separation >= 2.5 &&
                        (b.cue != Cue.EDGE || bf.minOcc >= 0.1)
                    b.threshold[shade] = bf.threshold; b.scale[shade] = bf.scale; b.ok[shade] = trusted
                    okBackups.add("%s %s (%.2f vs %.2f, separation %.1f)".format(b.cue.name.lowercase(), if (trusted) "ok" else "no", bf.maxEmpty, bf.minOcc, bf.separation))
                }
                notes.add("backup cues on $shadeName squares: " + okBackups.joinToString())
                val whiteSq = squares.filter { Square.rank(it) <= 1 }
                val blackSq = squares.filter { Square.rank(it) >= 6 }
                var col = fit(blackSq.map { f.colourScore[it] }, whiteSq.map { f.colourScore[it] }, "piece colour (brightness)", shadeName, 0.2, 0.08)
                if (margins.colourChroma != null) {
                    val byChroma = fit(blackSq.map { chromaColour(f, it, margins.chromaDir) }, whiteSq.map { chromaColour(f, it, margins.chromaDir) }, "piece colour (chroma)", shadeName, 0.2, 0.08)
                    if (!col.ok && byChroma.separation > col.separation) { col = byChroma; colourFromChroma[shade] = true }
                }
                colourThreshold[shade] = col.threshold; colourScale[shade] = col.scale; notes.add(col.note)
            }
            return Calibration(occThreshold, occScale, colourThreshold, colourScale, notes, occFromChroma, colourFromChroma, occWithChroma, margins.chromaDir, backups)
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
