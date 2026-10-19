package com.chesscoach.core.vision

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt
import kotlin.math.sin

/**
 * Proposes where the board is in a cluttered photo. Where four squares meet the brightness has a
 * saddle point (dark-light-dark-light around the corner), and nothing else in a room has 49 of
 * them packed into a small area. The saddle points are found from the Hessian of the smoothed
 * image, counted per cell, and the densest connected group of cells, with a margin, is the region.
 */
object BoardFinder {
    /** A window of the original image, in pixels, and how many saddle points it holds. */
    class Region(val x0: Int, val y0: Int, val width: Int, val height: Int, val saddles: Int, val points: List<Pt>)

    /** Only the strongest saddle points count; a board's corners are high-contrast and few things compete. */
    private const val MAX_POINTS = 240

    /** At most this many regions are proposed, strongest first. */
    private const val MAX_REGIONS = 4

    private const val WORK_SIDE = 640
    private const val CELL = 16

    fun propose(image: LumaImage, log: ((String) -> Unit)? = null): Region? = proposeAll(image, log).firstOrNull()

    /**
     * The strongest saddle points of the image (at most [maxPoints]), in image pixels. On a board
     * they sit where four squares meet; a grid whose inner corners land on them is well placed.
     */
    fun saddlePoints(image: LumaImage, maxPoints: Int = MAX_POINTS): List<Pt> {
        val found = findSaddles(image, maxPoints) ?: return emptyList()
        val (kept, w, stride) = found
        return kept.map { (i, _) -> Pt(((i % w) + 0.5) * stride, ((i / w) + 0.5) * stride) }
    }

    private class Saddles(val kept: List<Pair<Int, Float>>, val w: Int, val stride: Int) {
        operator fun component1() = kept
        operator fun component2() = w
        operator fun component3() = stride
    }

    private fun findSaddles(image: LumaImage, maxPoints: Int): Saddles? {
        val stride = max(1, (max(image.width, image.height) + WORK_SIDE - 1) / WORK_SIDE)
        val w = image.width / stride
        val h = image.height / stride
        if (w < 48 || h < 48) return null
        val px = FloatArray(w * h)
        val norm = 1f / (stride * stride)
        for (y in 0 until h) for (x in 0 until w) {
            var sum = 0
            for (dy in 0 until stride) for (dx in 0 until stride) sum += image.luma(x * stride + dx, y * stride + dy)
            px[y * w + x] = sum * norm
        }
        // 5-tap binomial blur, separable
        val tmp = FloatArray(w * h)
        val b = FloatArray(w * h)
        val k = floatArrayOf(1f, 4f, 6f, 4f, 1f)
        for (y in 0 until h) for (x in 0 until w) {
            var s = 0f
            for (i in -2..2) s += k[i + 2] * px[y * w + (x + i).coerceIn(0, w - 1)]
            tmp[y * w + x] = s / 16f
        }
        for (y in 0 until h) for (x in 0 until w) {
            var s = 0f
            for (i in -2..2) s += k[i + 2] * tmp[(y + i).coerceIn(0, h - 1) * w + x]
            b[y * w + x] = s / 16f
        }
        // X-corner response on a ring of 16 samples around each pixel: where four squares meet,
        // the ring is two light arcs and two dark arcs, so its second harmonic is strong and its
        // first harmonic (a plain edge, or the corner of a single square) is weak.
        val n = 16
        val radius = 4
        val dxs = IntArray(n) { (radius * cos(2 * PI * it / n)).roundToInt() }
        val dys = IntArray(n) { (radius * sin(2 * PI * it / n)).roundToInt() }
        val c1 = DoubleArray(n) { cos(2 * PI * it / n) }
        val s1 = DoubleArray(n) { sin(2 * PI * it / n) }
        val c2 = DoubleArray(n) { cos(4 * PI * it / n) }
        val s2 = DoubleArray(n) { sin(4 * PI * it / n) }
        val c4 = DoubleArray(n) { cos(8 * PI * it / n) }
        val s4 = DoubleArray(n) { sin(8 * PI * it / n) }
        val resp = FloatArray(w * h)
        var maxR = 0f
        val m = radius + 1
        val ring = DoubleArray(n)
        for (y in m until h - m) for (x in m until w - m) {
            var a1 = 0.0; var b1 = 0.0; var a2 = 0.0; var b2 = 0.0; var a4 = 0.0; var b4 = 0.0; var sum = 0.0
            for (k in 0 until n) {
                val v = b[(y + dys[k]) * w + x + dxs[k]].toDouble()
                ring[k] = v
                sum += v
                a1 += v * c1[k]; b1 += v * s1[k]; a2 += v * c2[k]; b2 += v * s2[k]; a4 += v * c4[k]; b4 += v * s4[k]
            }
            // A thin line through the centre also gives two bright spots opposite each other, but
            // as narrow spikes (strong fourth harmonic) with a bright centre; four square sectors
            // have neither. Where a frame edge meets two squares (a T), opposite points on the
            // ring differ, while at a corner between four squares they match.
            val centreOff = kotlin.math.abs(b[y * w + x] - sum / n) * n / 2
            var opposite = 0.0
            for (k in 0 until n / 2) opposite += kotlin.math.abs(ring[k] - ring[k + n / 2])
            val r = (hypot(a2, b2) - 1.5 * hypot(a1, b1) - 1.5 * hypot(a4, b4) - centreOff - opposite).toFloat()
            if (r > 0f) {
                resp[y * w + x] = r
                if (r > maxR) maxR = r
            }
        }
        if (maxR <= 0f) return null
        val thr = 0.02f * maxR
        // local maxima of the response, strongest first
        val maxima = ArrayList<Pair<Int, Float>>()
        for (y in 2 until h - 2) for (x in 2 until w - 2) {
            val v = resp[y * w + x]
            if (v < thr) continue
            var isMax = true
            loop@ for (dy in -2..2) for (dx in -2..2) {
                if ((dx != 0 || dy != 0) && resp[(y + dy) * w + x + dx] > v) { isMax = false; break@loop }
            }
            if (isMax) maxima.add((y * w + x) to v)
        }
        maxima.sortByDescending { it.second }
        return Saddles(maxima.take(maxPoints), w, stride)
    }

    /** Candidate regions, the one with most saddle points first. */
    fun proposeAll(image: LumaImage, log: ((String) -> Unit)? = null): List<Region> {
        val (kept, w, stride) = findSaddles(image, MAX_POINTS) ?: return emptyList()
        val h = image.height / stride
        val cw = (w + CELL - 1) / CELL
        val ch = (h + CELL - 1) / CELL
        val counts = IntArray(cw * ch)
        val points = ArrayList<Pt>()
        for ((i, _) in kept) {
            val x = i % w; val y = i / w
            counts[(y / CELL) * cw + x / CELL]++
            points.add(Pt((x + 0.5) * stride, (y + 0.5) * stride))
        }
        val total = kept.size
        if (total < 12) return emptyList()
        val assigned = BooleanArray(cw * ch)
        val regions = ArrayList<Region>()
        while (regions.size < MAX_REGIONS) {
            // Grow the densest group of unassigned cells.
            var seed = -1
            for (i in counts.indices) if (!assigned[i] && counts[i] >= 2 && (seed < 0 || counts[i] > counts[seed])) seed = i
            if (seed < 0) break
            val minCount = max(2, (counts[seed] * 0.3).toInt())
            val queue = ArrayDeque<Int>()
            queue.add(seed); assigned[seed] = true
            var saddles = 0
            var minCx = cw; var maxCx = -1; var minCy = ch; var maxCy = -1
            while (queue.isNotEmpty()) {
                val c = queue.removeFirst()
                val cx = c % cw; val cy = c / cw
                saddles += counts[c]
                minCx = min(minCx, cx); maxCx = max(maxCx, cx); minCy = min(minCy, cy); maxCy = max(maxCy, cy)
                for (dy in -1..1) for (dx in -1..1) {
                    val nx = cx + dx; val ny = cy + dy
                    if (nx !in 0 until cw || ny !in 0 until ch) continue
                    val n = ny * cw + nx
                    if (!assigned[n] && counts[n] >= minCount) { assigned[n] = true; queue.add(n) }
                }
            }
            if (saddles < 12) continue
            // Bounding box in work pixels, with a generous margin: the saddle points are inner
            // corners, often only of the better-lit half of the board, and the outer squares and
            // the frame lie outside them.
            val bx0 = minCx * CELL; val bx1 = min(w, (maxCx + 1) * CELL)
            val by0 = minCy * CELL; val by1 = min(h, (maxCy + 1) * CELL)
            val mx = ((bx1 - bx0) * 0.6).toInt() + CELL
            val my = ((by1 - by0) * 0.6).toInt() + CELL
            val x0 = max(0, (bx0 - mx) * stride)
            val y0 = max(0, (by0 - my) * stride)
            val x1 = min(image.width, (bx1 + mx) * stride)
            val y1 = min(image.height, (by1 + my) * stride)
            log?.invoke("board region: %d saddle points of %d, window (%d,%d)-(%d,%d)".format(saddles, total, x0, y0, x1, y1))
            if (x1 - x0 < 48 || y1 - y0 < 48) continue
            // the whole picture is not a proposal
            if ((x1 - x0).toLong() * (y1 - y0) > 0.8 * image.width.toLong() * image.height) continue
            regions.add(Region(x0, y0, x1 - x0, y1 - y0, saddles, points.filter { it.x >= x0 && it.x < x1 && it.y >= y0 && it.y < y1 }))
        }
        return regions.sortedByDescending { it.saddles }
    }
}
