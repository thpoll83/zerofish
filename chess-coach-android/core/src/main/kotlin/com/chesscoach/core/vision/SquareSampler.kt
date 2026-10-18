package com.chesscoach.core.vision

import com.chesscoach.core.chess.Square

/**
 * Pulls a small luminance patch out of every square. Each patch holds [side]*[side] samples
 * taken on a grid inside the square's sampling window.
 */
object SquareSampler {
    const val DEFAULT_SIDE = 12

    fun sample(image: LumaImage, geometry: BoardGeometry, side: Int = DEFAULT_SIDE): Array<IntArray> {
        return Array(64) { sq ->
            val file = Square.file(sq)
            val rank = Square.rank(sq)
            val w = geometry.sampleWindow(file, rank)
            val patch = IntArray(side * side)
            for (j in 0 until side) {
                val v = w[2] + (w[3] - w[2]) * (j + 0.5) / side
                for (i in 0 until side) {
                    val u = w[0] + (w[1] - w[0]) * (i + 0.5) / side
                    val p = geometry.toImage(u, v)
                    val x = p.x.toInt().coerceIn(0, image.width - 1)
                    val y = p.y.toInt().coerceIn(0, image.height - 1)
                    patch[j * side + i] = image.luma(x, y)
                }
            }
            patch
        }
    }
}
