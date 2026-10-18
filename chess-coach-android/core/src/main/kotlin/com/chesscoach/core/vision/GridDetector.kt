package com.chesscoach.core.vision

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt

/** A detected straight line in original-image pixel coordinates, for overlays. */
data class ImageLine(val x1: Double, val y1: Double, val x2: Double, val y2: Double, val family: Int)

/** Result of [GridDetector.detect]. [corners] are the board's outer corners in cyclic order (any rotation). */
class DetectedGrid(
    val corners: List<Pt>,
    val lineSupport: Int,
    val checkerScore: Double,
    val lines: List<ImageLine>,
    val notes: String,
)

/**
 * Finds the 8x8 board in a photo without user input.
 *
 * Pipeline: downscale, Sobel edges, weighted Hough transform, peak lines, split into two
 * families by direction, vanishing point per family, affine rectification through the
 * vanishing line (which makes grid lines parallel and equally spaced again), fit nine equally
 * spaced lines per family, and verify candidate grids by the light/dark alternation of squares.
 */
object GridDetector {
    private const val SMALL_SIDE = 640
    private const val THETA_BINS = 180
    private const val MAX_LINES = 60

    class Line(val theta: Double, val rho: Double, val weight: Double) // x cosθ + y sinθ = ρ, centred coords

    private class Small(val w: Int, val h: Int, val px: FloatArray, val stride: Int)

    private class Edges(val mag: FloatArray, val ang: FloatArray, val thr: Float)

    fun detect(image: LumaImage, debugLines: Boolean = true, log: ((String) -> Unit)? = null): DetectedGrid? {
        val small = downscale(image)
        val lines = houghLines(small) ?: return null
        val families = splitFamilies(lines) ?: return null
        val (famA, famB) = families
        val s = max(small.w, small.h) / 2.0
        log?.invoke("family A: " + famA.joinToString { "(%.0f°, %.0f, w%.2f)".format(it.theta * 180 / PI, it.rho, it.weight) })
        log?.invoke("family B: " + famB.joinToString { "(%.0f°, %.0f, w%.2f)".format(it.theta * 180 / PI, it.rho, it.weight) })
        val toImageLine = { l: Line, fam: Int -> clipLine(l, small, fam) }
        val debug = if (debugLines) famA.map { toImageLine(it, 0) } + famB.map { toImageLine(it, 1) } else emptyList()

        val vpsA = vanishingPoints(famA, s)
        val vpsB = vanishingPoints(famB, s)
        if (vpsA.isEmpty() || vpsB.isEmpty()) return null

        var best: DetectedGrid? = null
        var bestTotal = Double.NEGATIVE_INFINITY
        log?.invoke("VPs A: " + vpsA.joinToString { "(%.2f, %.2f, %.2f)".format(it[0], it[1], it[2]) })
        log?.invoke("VPs B: " + vpsB.joinToString { "(%.2f, %.2f, %.2f)".format(it[0], it[1], it[2]) })
        for (vA in vpsA) for (vB in vpsB) {
        val lInf = normalize3(cross(vA, vB))
        val h = rectifier(lInf)
        val hInv = invert3(h) ?: continue
        val rectA = rectify(famA, s, hInv) ?: continue
        val rectB = rectify(famB, s, hInv) ?: continue
        // The two families must not collapse onto each other after rectification.
        val ang = abs(rectA.nx * rectB.nx + rectA.ny * rectB.ny)
        if (ang > cos(25 * PI / 180)) continue

        val hypA = fitProgressions(rectA)
        val hypB = fitProgressions(rectB)
        log?.invoke("rect A positions: " + rectA.positions.sortedArray().joinToString { "%.3f".format(it) })
        log?.invoke("rect B positions: " + rectB.positions.sortedArray().joinToString { "%.3f".format(it) })
        log?.invoke("hyp A: " + hypA.joinToString { "(p0 %.3f s %.3f sup %d)".format(it.p0, it.s, it.support) })
        log?.invoke("hyp B: " + hypB.joinToString { "(p0 %.3f s %.3f sup %d)".format(it.p0, it.s, it.support) })
        if (hypA.isEmpty() || hypB.isEmpty()) continue

        for (a in hypA) for (b in hypB) {
            val cornersRect = listOf(0 to 0, 8 to 0, 8 to 8, 0 to 8).map { (ka, kb) ->
                intersect(rectA.nx, rectA.ny, a.p0 + ka * a.s, rectB.nx, rectB.ny, b.p0 + kb * b.s) ?: return@map null
            }
            if (cornersRect.any { it == null }) continue
            val corners = cornersRect.map { p ->
                val q = apply3(hInv, doubleArrayOf(p!!.x, p.y, 1.0))
                val x = q[0] / q[2] * s + small.w / 2.0
                val y = q[1] / q[2] * s + small.h / 2.0
                Pt((x + 0.5) * small.stride - 0.5, (y + 0.5) * small.stride - 0.5)
            }
            val ordered = orderCorners(corners) ?: continue
            if (!plausible(ordered, image)) continue
            val geometry = try {
                BoardGeometry(ordered)
            } catch (e: IllegalArgumentException) {
                continue
            }
            val checker = checkerScore(image, geometry)
            if (checker < 0.22) continue
            // Lines coinciding with the grid count for it; a strong line one square outside the
            // board counts against it (the grid would be shifted by a square).
            val aligned = alignmentScore(ordered, lines, small, 0..8)
            val outside = alignmentScore(ordered, lines, small, listOf(-1, 9))
            log?.invoke("  cand A(p0 %.3f s %.3f) B(p0 %.3f s %.3f): checker %.2f aligned %.1f outside %.1f corners %s".format(a.p0, a.s, b.p0, b.s, checker, aligned, outside, ordered.joinToString { "(%.0f,%.0f)".format(it.x, it.y) }))
            val total = aligned + 20.0 * checker - 6.0 * outside
            if (total > bestTotal) {
                bestTotal = total
                best = DetectedGrid(
                    ordered, a.support + b.support, checker, debug,
                    "lines %d+%d, checker %.2f".format(a.support, b.support, checker),
                )
            }
        }
        }
        val result = best ?: return null
        if (result.lineSupport < 10 || result.checkerScore < 0.22) return null
        val refined = refine(result.corners, lines, small, image)
        if (refined != null) {
            val checker = checkerScore(image, BoardGeometry(refined))
            val before = alignmentScore(result.corners, lines, small, 0..8)
            val after = alignmentScore(refined, lines, small, 0..8)
            log?.invoke("refined checker %.2f alignment %.1f -> %.1f corners %s".format(checker, before, after, refined.joinToString { "(%.0f,%.0f)".format(it.x, it.y) }))
            if (checker >= 0.22 && after >= before) {
                return DetectedGrid(refined, result.lineSupport, checker, debug, result.notes + ", refined")
            }
        }
        return result
    }

    /** Detected lines in unit-normal homogeneous form, in original-image pixel coordinates. */
    private fun imageLines(lines: List<Line>, small: Small): List<Triple<DoubleArray, Double, Double>> {
        val st = small.stride.toDouble()
        val cx = small.w / 2.0
        val cy = small.h / 2.0
        return lines.map { l ->
            val c = cos(l.theta); val sn = sin(l.theta)
            val a = c / st
            val b = sn / st
            val cc = c * (0.5 / st - 0.5 - cx) + sn * (0.5 / st - 0.5 - cy) - l.rho
            val n = hypot(a, b)
            Triple(doubleArrayOf(a / n, b / n, cc / n), l.weight, l.theta)
        }
    }

    /**
     * Weighted count of grid lines (at the given indices, in both families) that coincide with a
     * detected line of matching direction. Each line contributes at most its weight (0..1).
     */
    private fun alignmentScore(corners: List<Pt>, lines: List<Line>, small: Small, indices: Iterable<Int>): Double {
        val det = imageLines(lines, small)
        val h0 = Homography.boardToImage(corners)
        var total = 0.0
        for (k in indices) for (family in 0..1) {
            val kd = k.toDouble()
            val p1 = if (family == 0) h0.map(kd, 0.0) else h0.map(0.0, kd)
            val p2 = if (family == 0) h0.map(kd, 8.0) else h0.map(8.0, kd)
            val q1 = if (family == 0) h0.map(kd + 0.5, 4.0) else h0.map(4.0, kd + 0.5)
            val q2 = if (family == 0) h0.map(kd - 0.5, 4.0) else h0.map(4.0, kd - 0.5)
            val tol = 0.12 * hypot(q1.x - q2.x, q1.y - q2.y)
            val predTheta = atan2(p2.y - p1.y, p2.x - p1.x) + PI / 2
            var best = 0.0
            for ((l, w, theta) in det) {
                if (angDist(theta, predTheta) > 8 * PI / 180) continue
                val d = (abs(l[0] * p1.x + l[1] * p1.y + l[2]) + abs(l[0] * p2.x + l[1] * p2.y + l[2])) / 2
                if (d < tol) best = max(best, w * (1 - d / tol))
            }
            total += best
        }
        return total
    }

    /**
     * Snaps the 18 grid lines predicted by [corners] to the nearest detected lines and refits the
     * board-to-image homography by least squares over the intersections of the snapped lines.
     */
    private fun refine(corners: List<Pt>, lines: List<Line>, small: Small, image: LumaImage): List<Pt>? {
        val det = imageLines(lines, small)
        fun distance(l: DoubleArray, p: Pt) = abs(l[0] * p.x + l[1] * p.y + l[2])
        // Pick the detected line closest to the predicted one, preferring strong (long, polarity-flipping) lines.
        fun snap(p1: Pt, p2: Pt, tol: Double): DoubleArray? {
            val predTheta = atan2(p2.y - p1.y, p2.x - p1.x) + PI / 2
            var best: DoubleArray? = null
            var bestScore = Double.MAX_VALUE
            for ((l, w, theta) in det) {
                if (angDist(theta, predTheta) > 8 * PI / 180) continue
                val d = (distance(l, p1) + distance(l, p2)) / 2
                if (d > tol) continue
                val score = d / tol + 0.7 * (1 - w)
                if (score < bestScore) { bestScore = score; best = l }
            }
            return best
        }
        var current = corners
        for (tolFactor in doubleArrayOf(0.4, 0.25, 0.15)) {
            val h0 = Homography.boardToImage(current)
            val fileLines = arrayOfNulls<DoubleArray>(9)
            val rankLines = arrayOfNulls<DoubleArray>(9)
            for (k in 0..8) {
                val fa = h0.map(k.toDouble(), 0.0); val fb = h0.map(k.toDouble(), 8.0)
                val fn = h0.map(min(k + 1, 8).toDouble(), 4.0); val fp = h0.map(max(k - 1, 0).toDouble(), 4.0)
                val fileStep = hypot(fn.x - fp.x, fn.y - fp.y) / (if (k in 1..7) 2 else 1)
                fileLines[k] = snap(fa, fb, tolFactor * fileStep)
                val ra = h0.map(0.0, k.toDouble()); val rb = h0.map(8.0, k.toDouble())
                val rn = h0.map(4.0, min(k + 1, 8).toDouble()); val rp = h0.map(4.0, max(k - 1, 0).toDouble())
                val rankStep = hypot(rn.x - rp.x, rn.y - rp.y) / (if (k in 1..7) 2 else 1)
                rankLines[k] = snap(ra, rb, tolFactor * rankStep)
            }
            val src = ArrayList<Pt>()
            val dst = ArrayList<Pt>()
            for (i in 0..8) for (j in 0..8) {
                val fl = fileLines[i] ?: continue
                val rl = rankLines[j] ?: continue
                val x = cross(fl, rl)
                if (abs(x[2]) < 1e-12) continue
                src.add(Pt(i.toDouble(), j.toDouble()))
                dst.add(Pt(x[0] / x[2], x[1] / x[2]))
            }
            if (src.size < 6 || fileLines.count { it != null } < 3 || rankLines.count { it != null } < 3) return null
            val h = leastSquaresHomography(src, dst, image) ?: return null
            val next = listOf(Pt(0.0, 0.0), Pt(8.0, 0.0), Pt(8.0, 8.0), Pt(0.0, 8.0)).map { h.map(it) }
            if (!plausible(next, image)) return null
            current = next
        }
        return current
    }

    /** DLT with h33 = 1 solved through the normal equations, with coordinate normalisation. */
    private fun leastSquaresHomography(src: List<Pt>, dst: List<Pt>, image: LumaImage): Homography? {
        val sx = image.width / 2.0
        val sy = image.height / 2.0
        val sc = max(sx, sy)
        val a = Array(8) { DoubleArray(8) }
        val b = DoubleArray(8)
        for (k in src.indices) {
            val x = src[k].x / 4 - 1
            val y = src[k].y / 4 - 1
            val u = (dst[k].x - sx) / sc
            val v = (dst[k].y - sy) / sc
            val rows = arrayOf(
                doubleArrayOf(x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y) to u,
                doubleArrayOf(0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y) to v,
            )
            for ((row, rhs) in rows) {
                for (i in 0 until 8) {
                    b[i] += row[i] * rhs
                    for (j in 0 until 8) a[i][j] += row[i] * row[j]
                }
            }
        }
        // Gaussian elimination
        val m = Array(8) { i -> DoubleArray(9) { j -> if (j < 8) a[i][j] else b[i] } }
        for (col in 0 until 8) {
            var pivot = col
            for (r in col + 1 until 8) if (abs(m[r][col]) > abs(m[pivot][col])) pivot = r
            val tmp = m[col]; m[col] = m[pivot]; m[pivot] = tmp
            val p = m[col][col]
            if (abs(p) < 1e-12) return null
            for (j in col until 9) m[col][j] /= p
            for (r in 0 until 8) {
                if (r == col) continue
                val f = m[r][col]
                if (f == 0.0) continue
                for (j in col until 9) m[r][j] -= f * m[col][j]
            }
        }
        val hn = DoubleArray(9) { if (it < 8) m[it][8] else 1.0 }
        // undo normalisation: H = T_img^{-1} * Hn * T_board, with T_board: (x/4-1), T_img: ((u-sx)/sc)
        val tb = doubleArrayOf(0.25, 0.0, -1.0, 0.0, 0.25, -1.0, 0.0, 0.0, 1.0)
        val tiInv = doubleArrayOf(sc, 0.0, sx, 0.0, sc, sy, 0.0, 0.0, 1.0)
        val h = mul3(tiInv, mul3(hn, tb))
        return Homography(h)
    }

    private fun mul3(a: DoubleArray, b: DoubleArray): DoubleArray {
        val out = DoubleArray(9)
        for (i in 0..2) for (j in 0..2) {
            var sum = 0.0
            for (k in 0..2) sum += a[i * 3 + k] * b[k * 3 + j]
            out[i * 3 + j] = sum
        }
        return out
    }

    // ---- image preparation -------------------------------------------------------------------

    private fun downscale(image: LumaImage): Small {
        val stride = max(1, (max(image.width, image.height) + SMALL_SIDE - 1) / SMALL_SIDE)
        val w = image.width / stride
        val h = image.height / stride
        val px = FloatArray(w * h)
        val norm = 1f / (stride * stride)
        for (y in 0 until h) for (x in 0 until w) {
            var sum = 0
            for (dy in 0 until stride) for (dx in 0 until stride) sum += image.luma(x * stride + dx, y * stride + dy)
            px[y * w + x] = sum * norm
        }
        return Small(w, h, px, stride)
    }

    private fun houghLines(img: Small): List<Line>? {
        val w = img.w
        val h = img.h
        val p = img.px
        if (w < 32 || h < 32) return null
        // Sobel
        val mag = FloatArray(w * h)
        val ang = FloatArray(w * h)
        var maxMag = 0f
        for (y in 1 until h - 1) for (x in 1 until w - 1) {
            val i = y * w + x
            val gx = (p[i - w + 1] + 2 * p[i + 1] + p[i + w + 1]) - (p[i - w - 1] + 2 * p[i - 1] + p[i + w - 1])
            val gy = (p[i + w - 1] + 2 * p[i + w] + p[i + w + 1]) - (p[i - w - 1] + 2 * p[i - w] + p[i - w + 1])
            val m = hypot(gx, gy)
            mag[i] = m
            ang[i] = atan2(gy, gx)
            if (m > maxMag) maxMag = m
        }
        if (maxMag < 1f) return null
        // Threshold at the 92nd percentile of gradient magnitude.
        val hist = IntArray(512)
        for (m in mag) hist[min(511, (m / maxMag * 511).toInt())]++
        var acc = 0
        var thrBin = 511
        val target = (w * h * 0.08).toInt()
        for (b in 511 downTo 0) {
            acc += hist[b]
            if (acc >= target) {
                thrBin = b; break
            }
        }
        val thr = max(12f, thrBin / 511f * maxMag)

        val cx = w / 2.0
        val cy = h / 2.0
        val diag = hypot(w.toDouble(), h.toDouble())
        val rhoOff = (diag / 2).toInt() + 1
        val rhoBins = 2 * rhoOff + 1
        val accu = FloatArray(THETA_BINS * rhoBins)
        val cosT = DoubleArray(THETA_BINS) { cos(it * PI / THETA_BINS) }
        val sinT = DoubleArray(THETA_BINS) { sin(it * PI / THETA_BINS) }
        for (y in 1 until h - 1) for (x in 1 until w - 1) {
            val i = y * w + x
            val m = mag[i]
            if (m < thr) continue
            var a = ang[i].toDouble()
            if (a < 0) a += PI
            val b0 = (a / PI * THETA_BINS).roundToInt()
            val dx = x - cx
            val dy = y - cy
            for (db in -5..5) {
                var b = b0 + db
                if (b < 0) b += THETA_BINS
                if (b >= THETA_BINS) b -= THETA_BINS
                val rho = dx * cosT[b] + dy * sinT[b]
                val r = rho.roundToInt() + rhoOff
                if (r in 0 until rhoBins) accu[b * rhoBins + r] += m
            }
        }
        // Smooth along rho and find peaks.
        val sm = FloatArray(accu.size)
        var peakMax = 0f
        for (t in 0 until THETA_BINS) for (r in 1 until rhoBins - 1) {
            val i = t * rhoBins + r
            sm[i] = 0.25f * accu[i - 1] + 0.5f * accu[i] + 0.25f * accu[i + 1]
            if (sm[i] > peakMax) peakMax = sm[i]
        }
        val minPeak = peakMax * 0.12f
        val peaks = ArrayList<Line>()
        for (t in 0 until THETA_BINS) for (r in 2 until rhoBins - 2) {
            val v = sm[t * rhoBins + r]
            if (v < minPeak) continue
            var isMax = true
            loop@ for (dt in -2..2) for (dr in -3..3) {
                if (dt == 0 && dr == 0) continue
                var tt = t + dt
                var rr = r + dr
                if (tt < 0) { tt += THETA_BINS; rr = 2 * rhoOff - rr }
                if (tt >= THETA_BINS) { tt -= THETA_BINS; rr = 2 * rhoOff - rr }
                if (rr !in 0 until rhoBins) continue
                val o = sm[tt * rhoBins + rr]
                if (o > v || (o == v && (dt < 0 || (dt == 0 && dr < 0)))) {
                    isMax = false; break@loop
                }
            }
            if (isMax) peaks.add(Line(t * PI / THETA_BINS, (r - rhoOff).toDouble(), (v / peakMax).toDouble()))
        }
        peaks.sortByDescending { it.weight }
        val kept = ArrayList<Line>()
        for (l in peaks) {
            if (kept.size >= MAX_LINES) break
            if (kept.none { lineClose(it, l, 3.0 * PI / 180, 6.0) }) kept.add(l)
        }
        if (kept.size < 8) return null
        // Re-weight by supported length and by how often the edge polarity flips along the line:
        // grid lines run across the whole board and flip polarity every square, piece edges do not.
        val edges = Edges(mag, ang, thr)
        val stats = kept.map { lineStats(it, img, edges) }
        val maxSupport = stats.maxOf { it.first }
        if (maxSupport < 20.0) return null
        val weighted = kept.mapIndexedNotNull { i, l ->
            val (len, runs) = stats[i]
            val sn = len / maxSupport
            val polarity = when {
                runs >= 5 -> 1.0
                runs >= 3 -> 0.6
                else -> 0.2
            }
            if (sn < 0.15 || (runs <= 1 && sn < 0.5)) null
            else Line(l.theta, l.rho, sn * polarity * (0.5 + 0.5 * l.weight))
        }.sortedByDescending { it.weight }
        return if (weighted.size >= 8) weighted else null
    }

    /**
     * Walks along the line and returns (supported length in pixels, number of polarity runs).
     * A pixel supports the line when an edge of matching orientation lies within one pixel of it.
     */
    private fun lineStats(l: Line, img: Small, e: Edges): Pair<Double, Int> {
        val cx = img.w / 2.0
        val cy = img.h / 2.0
        val c = cos(l.theta)
        val s = sin(l.theta)
        val px = c * l.rho + cx
        val py = s * l.rho + cy
        val dx = -s
        val dy = c
        val len = hypot(img.w.toDouble(), img.h.toDouble())
        var count = 0
        var runs = 0
        var lastSign = 0
        var runLen = 0
        var t = -len
        while (t <= len) {
            val x = (px + dx * t).roundToInt()
            val y = (py + dy * t).roundToInt()
            t += 1.0
            if (x < 1 || y < 1 || x >= img.w - 1 || y >= img.h - 1) continue
            var sign = 0
            for (k in -1..1) {
                val xx = (x + c * k).roundToInt()
                val yy = (y + s * k).roundToInt()
                if (xx < 0 || yy < 0 || xx >= img.w || yy >= img.h) continue
                val i = yy * img.w + xx
                if (e.mag[i] < e.thr * 0.7f) continue
                var a = e.ang[i].toDouble()
                if (a < 0) a += PI
                if (angDist(a, l.theta) < 12 * PI / 180) {
                    // polarity: does the gradient point along the normal or against it?
                    val g = cos(e.ang[i].toDouble()) * c + sin(e.ang[i].toDouble()) * s
                    sign = if (g >= 0) 1 else -1
                    break
                }
            }
            if (sign == 0) continue
            count++
            if (sign == lastSign) {
                runLen++
            } else {
                if (runLen >= 3) runs++
                lastSign = sign
                runLen = 1
            }
        }
        if (runLen >= 3) runs++
        return count.toDouble() to runs
    }

    private fun lineClose(a: Line, b: Line, dTheta: Double, dRho: Double): Boolean {
        var dt = abs(a.theta - b.theta)
        var rb = b.rho
        if (dt > PI / 2) { dt = PI - dt; rb = -rb }
        return dt <= dTheta && abs(a.rho - rb) <= dRho
    }

    // ---- line families ----------------------------------------------------------------------

    private fun splitFamilies(lines: List<Line>): Pair<List<Line>, List<Line>>? {
        // 2-means on doubled angles, seeded by the strongest line and its perpendicular.
        var c1 = lines[0].theta
        var c2 = c1 + PI / 2
        val assign = IntArray(lines.size)
        repeat(12) {
            for ((i, l) in lines.withIndex()) assign[i] = if (angDist(l.theta, c1) <= angDist(l.theta, c2)) 0 else 1
            c1 = meanAngle(lines, assign, 0, c1)
            c2 = meanAngle(lines, assign, 1, c2)
        }
        val a = ArrayList<Line>()
        val b = ArrayList<Line>()
        val maxDev = 38 * PI / 180
        for ((i, l) in lines.withIndex()) {
            if (assign[i] == 0 && angDist(l.theta, c1) < maxDev) a.add(l)
            if (assign[i] == 1 && angDist(l.theta, c2) < maxDev) b.add(l)
        }
        if (a.size < 4 || b.size < 4) return null
        if (angDist(c1, c2) < 40 * PI / 180) return null
        return a to b
    }

    private fun angDist(a: Double, b: Double): Double {
        var d = abs(a - b) % PI
        if (d > PI / 2) d = PI - d
        return d
    }

    private fun meanAngle(lines: List<Line>, assign: IntArray, k: Int, fallback: Double): Double {
        var sx = 0.0
        var sy = 0.0
        for ((i, l) in lines.withIndex()) if (assign[i] == k) {
            sx += l.weight * cos(2 * l.theta); sy += l.weight * sin(2 * l.theta)
        }
        if (sx == 0.0 && sy == 0.0) return fallback
        var m = 0.5 * atan2(sy, sx)
        if (m < 0) m += PI
        return m
    }

    // ---- projective geometry helpers ----------------------------------------------------------

    /** Homogeneous line in normalised centred coordinates (unit normal). */
    private fun homog(l: Line, s: Double) = doubleArrayOf(cos(l.theta), sin(l.theta), -l.rho / s)

    /**
     * Candidate vanishing points for one family: every pair of lines proposes one, lines agreeing
     * within 1.5 degrees vote for it, and the strongest distinct proposals are refined by least
     * squares over their supporters.
     */
    private fun vanishingPoints(fam: List<Line>, s: Double): List<DoubleArray> {
        val hom = fam.map { homog(it, s) }
        val anchors = fam.map { doubleArrayOf(cos(it.theta) * it.rho / s, sin(it.theta) * it.rho / s, 1.0) }
        val tol = 1.5 * PI / 180
        class Prop(val v: DoubleArray, val inliers: List<Int>, val score: Double)
        val props = ArrayList<Prop>()
        for (i in fam.indices) for (j in i + 1 until fam.size) {
            val v = normalize3(cross(hom[i], hom[j]))
            if (v.all { it == 0.0 }) continue
            val inl = ArrayList<Int>()
            var score = 0.0
            for (k in fam.indices) {
                val through = cross(v, anchors[k]) // line through the VP and this line's anchor point
                val n = hypot(through[0], through[1])
                if (n < 1e-12) continue
                val cosA = abs((through[0] * hom[k][0] + through[1] * hom[k][1]) / n)
                if (cosA >= cos(tol)) {
                    inl.add(k); score += fam[k].weight
                }
            }
            if (inl.size >= 3) props.add(Prop(v, inl, score))
        }
        props.sortByDescending { it.score }
        val out = ArrayList<DoubleArray>()
        val used = ArrayList<Set<Int>>()
        for (p in props) {
            if (out.size >= 3) break
            val set = p.inliers.toSet()
            if (used.any { (it intersect set).size > 0.7 * set.size }) continue
            val m = DoubleArray(9)
            for (k in p.inliers) for (a in 0..2) for (b in 0..2) m[a * 3 + b] += fam[k].weight * hom[k][a] * hom[k][b]
            val refined = smallestEigenvector(m) ?: p.v
            out.add(refined)
            used.add(set)
        }
        return out
    }

    private class Rectified(val nx: Double, val ny: Double, val positions: DoubleArray, val weights: DoubleArray)

    private fun rectify(fam: List<Line>, s: Double, hInv: DoubleArray): Rectified? {
        // l' = H^{-T} l
        val ls = fam.map { l ->
            val h = homog(l, s)
            val t = doubleArrayOf(
                hInv[0] * h[0] + hInv[3] * h[1] + hInv[6] * h[2],
                hInv[1] * h[0] + hInv[4] * h[1] + hInv[7] * h[2],
                hInv[2] * h[0] + hInv[5] * h[1] + hInv[8] * h[2],
            )
            val n = hypot(t[0], t[1])
            if (n < 1e-12) return null
            doubleArrayOf(t[0] / n, t[1] / n, t[2] / n)
        }
        var sx = 0.0
        var sy = 0.0
        for ((i, l) in ls.withIndex()) {
            val th = atan2(l[1], l[0])
            sx += fam[i].weight * cos(2 * th); sy += fam[i].weight * sin(2 * th)
        }
        val psi = 0.5 * atan2(sy, sx)
        val nx = cos(psi)
        val ny = sin(psi)
        val pos = DoubleArray(ls.size)
        val wts = DoubleArray(ls.size)
        for ((i, l) in ls.withIndex()) {
            var d = l[0] * nx + l[1] * ny
            var c = l[2]
            if (d < 0) { d = -d; c = -c }
            if (d < 0.5) return null // a line more than 60 degrees off its family after rectification
            pos[i] = -c / d
            wts[i] = fam[i].weight
        }
        return Rectified(nx, ny, pos, wts)
    }

    private class Progression(val p0: Double, val s: Double, val support: Int, val weighted: Double, val score: Double)

    private fun fitProgressions(r: Rectified): List<Progression> {
        val n = r.positions.size
        val out = ArrayList<Progression>()
        for (i in 0 until n) for (j in 0 until n) {
            if (r.positions[j] <= r.positions[i]) continue
            for (g in 1..8) {
                val s = (r.positions[j] - r.positions[i]) / g
                if (s < 0.035 || s > 0.5) continue
                val tol = 0.14 * s
                for (k in 0..(8 - g)) {
                    val p0 = r.positions[i] - k * s
                    var support = 0
                    var score = 0.0
                    // weighted regression of matched line positions on their grid index refines p0 and s
                    var sw = 0.0; var sx = 0.0; var sy = 0.0; var sxx = 0.0; var sxy = 0.0
                    for (idx in 0..8) {
                        val target = p0 + idx * s
                        var bestW = 0.0
                        var bestPos = 0.0
                        var found = false
                        for (m in 0 until n) {
                            if (abs(r.positions[m] - target) <= tol) {
                                found = true
                                if (r.weights[m] > bestW) { bestW = r.weights[m]; bestPos = r.positions[m] }
                            }
                        }
                        if (found) {
                            support++; score += bestW
                            sw += bestW; sx += bestW * idx; sy += bestW * bestPos
                            sxx += bestW * idx * idx; sxy += bestW * idx * bestPos
                        }
                    }
                    // score by summed line weights: piece edges and table edges carry little weight
                    if (support >= 5 && score >= 2.5) {
                        val det = sw * sxx - sx * sx
                        val (rp0, rs) = if (det > 1e-12) {
                            val slope = (sw * sxy - sx * sy) / det
                            val icpt = (sy - slope * sx) / sw
                            icpt to slope
                        } else p0 to s
                        out.add(Progression(rp0, rs, support, score, score + 0.1 * support))
                    }
                }
            }
        }
        out.sortByDescending { it.score }
        val distinct = ArrayList<Progression>()
        for (p in out) {
            if (distinct.size >= 8) break
            if (distinct.none { abs(it.p0 - p.p0) < 0.05 * p.s && abs(it.s - p.s) < 0.05 * p.s }) distinct.add(p)
        }
        return distinct
    }

    private fun intersect(ax: Double, ay: Double, ap: Double, bx: Double, by: Double, bp: Double): Pt? {
        val det = ax * by - ay * bx
        if (abs(det) < 1e-9) return null
        return Pt((ap * by - ay * bp) / det, (ax * bp - ap * bx) / det)
    }

    /** Puts corners in the a1,h1,h8,a8 handedness (negative cross product in y-down image coordinates). */
    private fun orderCorners(c: List<Pt>): List<Pt>? {
        if (c.any { it.x.isNaN() || it.y.isNaN() }) return null
        val cross = (c[1].x - c[0].x) * (c[3].y - c[0].y) - (c[1].y - c[0].y) * (c[3].x - c[0].x)
        return if (cross < 0) c else listOf(c[0], c[3], c[2], c[1])
    }

    private fun plausible(c: List<Pt>, image: LumaImage): Boolean {
        val mx = image.width * 0.15
        val my = image.height * 0.15
        if (c.any { it.x < -mx || it.x > image.width + mx || it.y < -my || it.y > image.height + my }) return false
        var minSide = Double.MAX_VALUE
        for (i in 0 until 4) {
            val j = (i + 1) % 4
            minSide = min(minSide, hypot(c[i].x - c[j].x, c[i].y - c[j].y))
        }
        if (minSide < 0.12 * min(image.width, image.height)) return false
        // convexity: all cross products of consecutive edges share a sign
        var sign = 0
        for (i in 0 until 4) {
            val a = c[i]; val b = c[(i + 1) % 4]; val d = c[(i + 2) % 4]
            val cr = (b.x - a.x) * (d.y - b.y) - (b.y - a.y) * (d.x - b.x)
            val s = if (cr > 0) 1 else -1
            if (sign == 0) sign = s else if (s != sign) return false
        }
        return true
    }

    /**
     * Checkerboard evidence for a hypothesised grid, 0..1. Rows and columns inside the board must
     * alternate light/dark; the ring of squares just outside it must not (otherwise the grid is
     * shifted by a whole square and the frame or table would be inside it).
     */
    fun checkerScore(image: LumaImage, geometry: BoardGeometry): Double {
        // means of a 10x10 grid, index -1..8 in both axes
        val means = Array(10) { DoubleArray(10) }
        for (fi in 0 until 10) for (ri in 0 until 10) {
            val f = fi - 1
            val r = ri - 1
            // median over a ring just inside the square's border: piece bases rarely reach it,
            // and a grid that is off by part of a square puts the ring across two squares.
            val samples = IntArray(32)
            var n = 0
            val inset = 0.12
            for (k in 0 until 8) {
                val t = 0.15 + 0.7 * (k + 0.5) / 8
                for (p in listOf(
                    geometry.toImage(f + t, r + inset), geometry.toImage(f + t, r + 1 - inset),
                    geometry.toImage(f + inset, r + t), geometry.toImage(f + 1 - inset, r + t),
                )) {
                    val x = p.x.toInt()
                    val y = p.y.toInt()
                    if (x in 0 until image.width && y in 0 until image.height) samples[n++] = image.luma(x, y)
                }
            }
            means[fi][ri] = if (n >= 10) {
                val sub = samples.copyOf(n); sub.sort(); sub[n / 2].toDouble()
            } else Double.NaN
        }
        fun alternation(values: List<Pair<Int, Double>>): Double {
            val v = values.filter { !it.second.isNaN() }
            if (v.size < 4) return 0.0
            val avg = v.sumOf { it.second } / v.size
            var signed = 0.0
            var total = 0.0
            for ((parity, m) in v) {
                val sign = if (parity % 2 == 0) -1 else 1
                signed += sign * (m - avg)
                total += abs(m - avg)
            }
            return if (total < 1e-6) 0.0 else abs(signed) / total
        }
        var inner = 0.0
        var ring = 0.0
        for (r in 0 until 10) { // rows r-1, over inner files 0..7
            val a = alternation((1..8).map { fi -> (fi - 1 + (r - 1) + 200) to means[fi][r] })
            if (r in 1..8) inner += a else ring += a
        }
        for (f in 0 until 10) {
            val a = alternation((1..8).map { ri -> (f - 1 + (ri - 1) + 200) to means[f][ri] })
            if (f in 1..8) inner += a else ring += a
        }
        // inner: 16 lines, ring: 4 lines
        val score = inner / 16 - ring / 4
        return score.coerceIn(0.0, 1.0)
    }

    private fun clipLine(l: Line, img: Small, fam: Int): ImageLine {
        val cx = img.w / 2.0
        val cy = img.h / 2.0
        val c = cos(l.theta)
        val s = sin(l.theta)
        // point on line + direction
        val px = c * l.rho
        val py = s * l.rho
        val dx = -s
        val dy = c
        val len = hypot(img.w.toDouble(), img.h.toDouble())
        val st = img.stride.toDouble()
        return ImageLine(
            (px - dx * len + cx) * st, (py - dy * len + cy) * st,
            (px + dx * len + cx) * st, (py + dy * len + cy) * st, fam,
        )
    }

    // ---- small linear algebra ----------------------------------------------------------------

    private fun cross(a: DoubleArray, b: DoubleArray) = doubleArrayOf(
        a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0],
    )

    private fun dot(a: DoubleArray, b: DoubleArray) = a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    private fun normalize3(v: DoubleArray): DoubleArray {
        val n = sqrt(dot(v, v))
        return if (n < 1e-15) v else doubleArrayOf(v[0] / n, v[1] / n, v[2] / n)
    }

    /** A projective transform that sends the line [l] to infinity. */
    private fun rectifier(l: DoubleArray): DoubleArray {
        val k = (0..2).maxByOrNull { abs(l[it]) }!!
        return when (k) {
            2 -> doubleArrayOf(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, l[0], l[1], l[2])
            0 -> doubleArrayOf(0.0, 1.0, 0.0, 0.0, 0.0, 1.0, l[0], l[1], l[2])
            else -> doubleArrayOf(0.0, 0.0, 1.0, 1.0, 0.0, 0.0, l[0], l[1], l[2])
        }
    }

    private fun apply3(m: DoubleArray, v: DoubleArray) = doubleArrayOf(
        m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
        m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
        m[6] * v[0] + m[7] * v[1] + m[8] * v[2],
    )

    private fun invert3(m: DoubleArray): DoubleArray? {
        val a = m[0]; val b = m[1]; val c = m[2]
        val d = m[3]; val e = m[4]; val f = m[5]
        val g = m[6]; val h = m[7]; val i = m[8]
        val det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
        if (abs(det) < 1e-12) return null
        return doubleArrayOf(
            (e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det,
            (f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det,
            (d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det,
        )
    }

    /** Eigenvector of the smallest eigenvalue of a symmetric 3x3 matrix, by Jacobi rotations. */
    private fun smallestEigenvector(m: DoubleArray): DoubleArray? {
        val a = m.copyOf()
        val v = doubleArrayOf(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
        repeat(50) {
            var p = 0; var q = 1
            var maxOff = abs(a[1])
            if (abs(a[2]) > maxOff) { maxOff = abs(a[2]); p = 0; q = 2 }
            if (abs(a[5]) > maxOff) { maxOff = abs(a[5]); p = 1; q = 2 }
            if (maxOff < 1e-14) return@repeat
            val app = a[p * 3 + p]; val aqq = a[q * 3 + q]; val apq = a[p * 3 + q]
            val theta = 0.5 * atan2(2 * apq, aqq - app)
            val c = cos(theta); val s = sin(theta)
            // A' = J^T A J
            val tmp = a.copyOf()
            for (k in 0..2) {
                tmp[k * 3 + p] = c * a[k * 3 + p] - s * a[k * 3 + q]
                tmp[k * 3 + q] = s * a[k * 3 + p] + c * a[k * 3 + q]
            }
            val tmp2 = tmp.copyOf()
            for (k in 0..2) {
                tmp2[p * 3 + k] = c * tmp[p * 3 + k] - s * tmp[q * 3 + k]
                tmp2[q * 3 + k] = s * tmp[p * 3 + k] + c * tmp[q * 3 + k]
            }
            for (k in 0..8) a[k] = tmp2[k]
            for (k in 0..2) {
                val vp = v[k * 3 + p]; val vq = v[k * 3 + q]
                v[k * 3 + p] = c * vp - s * vq
                v[k * 3 + q] = s * vp + c * vq
            }
        }
        var idx = 0
        for (k in 1..2) if (a[k * 3 + k] < a[idx * 3 + idx]) idx = k
        val out = doubleArrayOf(v[idx], v[3 + idx], v[6 + idx])
        return if (out.any { it.isNaN() }) null else out
    }
}
