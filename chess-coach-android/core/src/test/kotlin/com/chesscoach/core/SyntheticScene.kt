package com.chesscoach.core

import com.chesscoach.core.chess.Square
import com.chesscoach.core.vision.ArrayLumaImage
import com.chesscoach.core.vision.Homography
import com.chesscoach.core.vision.Pt
import kotlin.math.abs
import kotlin.math.hypot

/** Photo-like rendering of a board with pieces, shared by the vision tests. */
object SyntheticScene {
    fun render(
        corners: List<Pt>, occupancy: IntArray, w: Int, h: Int,
        brightness: Double = 1.0, seed: Int = 1, lightTone: Double = 175.0, darkTone: Double = 85.0,
        /** Optional "hand": an opaque mid-grey blob centred at this image point with this radius. */
        hand: Pt? = null, handRadius: Double = 0.0,
    ): ArrayLumaImage {
        val hom = Homography.boardToImage(corners)
        val inv = hom.inverse()
        val rnd = java.util.Random(seed.toLong())
        val data = IntArray(w * h)
        for (y in 0 until h) for (x in 0 until w) {
            val b = inv.map(x + 0.5, y + 0.5)
            val grad = 1.0 + 0.12 * (x.toDouble() / w - 0.5) - 0.08 * (y.toDouble() / h - 0.5)
            val v: Double = if (b.x in -0.7..8.7 && b.y in -0.7..8.7) {
                if (b.x in 0.0..8.0 && b.y in 0.0..8.0) {
                    val f = b.x.toInt().coerceIn(0, 7)
                    val r = b.y.toInt().coerceIn(0, 7)
                    if (Square.isLight(Square.of(f, r))) lightTone else darkTone
                } else 120.0
            } else {
                140.0 + 12 * kotlin.math.sin(x / 41.0 + 2 * kotlin.math.sin(y / 67.0)) + 6 * kotlin.math.cos(y / 29.0)
            }
            data[y * w + x] = (v * grad * brightness).toInt().coerceIn(0, 255)
        }
        for (sq in 0 until 64) {
            val occ = occupancy[sq]
            if (occ == 0) continue
            val f = Square.file(sq)
            val r = Square.rank(sq)
            val c = hom.map(f + 0.5, r + 0.5)
            val e1 = hom.map(f + 1.0, r + 0.5)
            val e2 = hom.map(f + 0.5, r + 1.0)
            val halfW = hypot(e1.x - c.x, e1.y - c.y)
            val halfH = hypot(e2.x - c.x, e2.y - c.y)
            val rx = 0.32 * halfW * 2
            val ry = 0.32 * halfH * 2
            val height = 1.1 * halfW * 2
            val tone = if (occ == 1) 230.0 else 30.0
            val x0 = (c.x - rx - 1).toInt().coerceAtLeast(0)
            val x1 = (c.x + rx + 1).toInt().coerceAtMost(w - 1)
            val y0 = (c.y - height - 1).toInt().coerceAtLeast(0)
            val y1 = (c.y + ry + 1).toInt().coerceAtMost(h - 1)
            for (y in y0..y1) for (x in x0..x1) {
                val dx = x - c.x
                val dy = y - c.y
                val inDisc = (dx * dx) / (rx * rx) + (dy * dy) / (ry * ry) <= 1.0
                val inBody = abs(dx) <= rx * 0.45 && dy < 0 && dy > -height
                if (inDisc || inBody) {
                    val shade = if (inBody && abs(dx) > rx * 0.3) tone * 0.8 + 10 else tone
                    data[y * w + x] = shade.toInt().coerceIn(0, 255)
                }
            }
        }
        if (hand != null) {
            for (y in 0 until h) for (x in 0 until w) {
                if (hypot(x - hand.x, y - hand.y) < handRadius) data[y * w + x] = 150
            }
        }
        for (i in data.indices) data[i] = (data[i] + rnd.nextGaussian() * 3).toInt().coerceIn(0, 255)
        return ArrayLumaImage(w, h, data)
    }
}
