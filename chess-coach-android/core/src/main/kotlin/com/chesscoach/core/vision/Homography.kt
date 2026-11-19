package com.chesscoach.core.vision

data class Pt(val x: Double, val y: Double)

/**
 * 3x3 projective transform. [map] takes board-plane coordinates (file 0..8, rank 0..8,
 * a1 corner at the origin) to image pixels when built with [boardToImage].
 */
class Homography(val h: DoubleArray) {
    init {
        require(h.size == 9)
    }

    fun map(x: Double, y: Double): Pt {
        val w = h[6] * x + h[7] * y + h[8]
        val px = (h[0] * x + h[1] * y + h[2]) / w
        val py = (h[3] * x + h[4] * y + h[5]) / w
        return Pt(px, py)
    }

    fun map(p: Pt): Pt = map(p.x, p.y)

    fun inverse(): Homography {
        val m = h
        val a = m[0]; val b = m[1]; val c = m[2]
        val d = m[3]; val e = m[4]; val f = m[5]
        val g = m[6]; val hh = m[7]; val i = m[8]
        val det = a * (e * i - f * hh) - b * (d * i - f * g) + c * (d * hh - e * g)
        require(kotlin.math.abs(det) > 1e-12) { "Singular homography" }
        val inv = doubleArrayOf(
            (e * i - f * hh) / det, (c * hh - b * i) / det, (b * f - c * e) / det,
            (f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det,
            (d * hh - e * g) / det, (b * g - a * hh) / det, (a * e - b * d) / det,
        )
        return Homography(inv)
    }

    companion object {
        /**
         * Builds the transform from board coordinates to image pixels. [corners] are the image
         * positions of the board's outer corners in the order a1, h1, h8, a8.
         */
        fun boardToImage(corners: List<Pt>): Homography {
            require(corners.size == 4) { "Need exactly 4 corners" }
            val src = listOf(Pt(0.0, 0.0), Pt(8.0, 0.0), Pt(8.0, 8.0), Pt(0.0, 8.0))
            return fromCorrespondences(src, corners)
        }

        /** Solves the 8 unknowns of H (h[8] = 1) from four point pairs by Gaussian elimination. */
        fun fromCorrespondences(src: List<Pt>, dst: List<Pt>): Homography {
            require(src.size == 4 && dst.size == 4)
            val a = Array(8) { DoubleArray(9) }
            for (k in 0 until 4) {
                val (x, y) = src[k]
                val (u, v) = dst[k]
                a[2 * k] = doubleArrayOf(x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y, u)
                a[2 * k + 1] = doubleArrayOf(0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y, v)
            }
            for (col in 0 until 8) {
                var pivot = col
                for (r in col + 1 until 8) if (kotlin.math.abs(a[r][col]) > kotlin.math.abs(a[pivot][col])) pivot = r
                val tmp = a[col]; a[col] = a[pivot]; a[pivot] = tmp
                val p = a[col][col]
                require(kotlin.math.abs(p) > 1e-12) { "Degenerate corner configuration" }
                for (j in col until 9) a[col][j] /= p
                for (r in 0 until 8) {
                    if (r == col) continue
                    val factor = a[r][col]
                    if (factor == 0.0) continue
                    for (j in col until 9) a[r][j] -= factor * a[col][j]
                }
            }
            val h = DoubleArray(9)
            for (k in 0 until 8) h[k] = a[k][8]
            h[8] = 1.0
            return Homography(h)
        }
    }
}
