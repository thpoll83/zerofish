package com.chesscoach.core.vision

/**
 * A learned reader of single squares: given [count] crops made by [ChesscogCrops] (laid out one
 * after the other, each 3 x 100 x 100, RGB, normalised), the probability that each shows a
 * piece. The app runs Chesscog's occupancy network (a ResNet-18 trained on rendered boards from
 * many angles, see tools/chesscog_to_onnx.py) behind this.
 */
fun interface SquareClassifier {
    fun occupied(crops: FloatArray, count: Int): FloatArray
}

/**
 * The crop Chesscog's occupancy network was trained on: the board warped to a top-down view at
 * 50 pixels per square, and a 100 by 100 window centred on the square, so the square itself
 * and half a square around it, with the camera's side at the bottom. Sampled straight from the
 * camera frame through the board's homography (bilinear, as the warp is), outside the frame
 * black, RGB normalised with the ImageNet mean and deviation.
 */
object ChesscogCrops {
    const val SIZE = 100
    private const val PER_SQUARE = 50.0
    private val MEAN = doubleArrayOf(0.485, 0.456, 0.406)
    private val STD = doubleArrayOf(0.229, 0.224, 0.225)

    /** Board directions (file, rank) of the crop's "up" and "right", seen from the camera's side. */
    private fun axes(near: NearSide): Pair<IntArray, IntArray> = when (near) {
        NearSide.RANK_8 -> intArrayOf(0, -1) to intArrayOf(-1, 0)
        NearSide.FILE_A -> intArrayOf(1, 0) to intArrayOf(0, -1)
        NearSide.FILE_H -> intArrayOf(-1, 0) to intArrayOf(0, 1)
        NearSide.RANK_1, NearSide.NONE -> intArrayOf(0, 1) to intArrayOf(1, 0)
    }

    fun crop(image: YuvImage, geometry: BoardGeometry, squares: IntArray): FloatArray {
        val n = SIZE * SIZE
        val out = FloatArray(squares.size * 3 * n)
        val (up, right) = axes(geometry.nearSide)
        val h = geometry.homography
        val w = image.width; val hh = image.height
        val rgb = DoubleArray(3)
        for ((k, sq) in squares.withIndex()) {
            val cf = (sq and 7) + 0.5
            val cr = (sq shr 3) + 0.5
            val base = k * 3 * n
            for (v in 0 until SIZE) {
                val dv = 1.0 - (v + 0.5) / PER_SQUARE
                for (u in 0 until SIZE) {
                    val du = (u + 0.5) / PER_SQUARE - 1.0
                    val p = h.map(cf + right[0] * du + up[0] * dv, cr + right[1] * du + up[1] * dv)
                    val i = v * SIZE + u
                    if (!sample(image, p.x, p.y, w, hh, rgb)) {
                        // black, as the warp fills outside the frame
                        for (c in 0..2) out[base + c * n + i] = ((0.0 - MEAN[c]) / STD[c]).toFloat()
                        continue
                    }
                    for (c in 0..2) out[base + c * n + i] = ((rgb[c] / 255.0 - MEAN[c]) / STD[c]).toFloat()
                }
            }
        }
        return out
    }

    /** Bilinear RGB at pixel coordinates (x, y) (pixel centres at integers); false outside the frame. */
    private fun sample(image: YuvImage, x: Double, y: Double, w: Int, h: Int, rgb: DoubleArray): Boolean {
        if (x < -0.5 || y < -0.5 || x > w - 0.5 || y > h - 0.5) return false
        val fx = x.coerceIn(0.0, (w - 1).toDouble()); val fy = y.coerceIn(0.0, (h - 1).toDouble())
        val ix = fx.toInt(); val iy = fy.toInt()
        val ax = fx - ix; val ay = fy - iy
        val jx = minOf(ix + 1, w - 1); val jy = minOf(iy + 1, h - 1)
        rgb[0] = 0.0; rgb[1] = 0.0; rgb[2] = 0.0
        tap(image, ix, iy, (1 - ax) * (1 - ay), rgb); tap(image, jx, iy, ax * (1 - ay), rgb)
        tap(image, ix, jy, (1 - ax) * ay, rgb); tap(image, jx, jy, ax * ay, rgb)
        for (c in 0..2) rgb[c] = rgb[c].coerceIn(0.0, 255.0)
        return true
    }

    private fun tap(image: YuvImage, x: Int, y: Int, wgt: Double, rgb: DoubleArray) {
        if (wgt == 0.0) return
        val yy = image.luma(x, y).toDouble(); val u = image.u(x, y) - 128.0; val v = image.v(x, y) - 128.0
        rgb[0] += wgt * (yy + 1.402 * v)
        rgb[1] += wgt * (yy - 0.344136 * u - 0.714136 * v)
        rgb[2] += wgt * (yy + 1.772 * u)
    }
}
