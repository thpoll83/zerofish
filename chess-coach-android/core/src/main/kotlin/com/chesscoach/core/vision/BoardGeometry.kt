package com.chesscoach.core.vision

import kotlin.math.hypot

/** Which board edge is closest to the camera, judged from the edge that appears longest. */
enum class NearSide { NONE, RANK_1, RANK_8, FILE_A, FILE_H }

/**
 * Where the board sits in the photo: four outer corners in image pixels, ordered a1, h1, h8, a8.
 */
class BoardGeometry(val corners: List<Pt>) {
    init {
        require(corners.size == 4) { "Need 4 corners (a1, h1, h8, a8)" }
    }

    val homography: Homography = Homography.boardToImage(corners)

    /** Estimates the camera side. Opposite edges that differ in length by less than 12% count as overhead. */
    val nearSide: NearSide by lazy {
        val (a1, h1, h8, a8) = corners
        val rank1 = dist(a1, h1)
        val rank8 = dist(a8, h8)
        val fileA = dist(a1, a8)
        val fileH = dist(h1, h8)
        val rankRatio = maxOf(rank1, rank8) / minOf(rank1, rank8)
        val fileRatio = maxOf(fileA, fileH) / minOf(fileA, fileH)
        when {
            rankRatio < 1.12 && fileRatio < 1.12 -> NearSide.NONE
            rankRatio >= fileRatio -> if (rank1 > rank8) NearSide.RANK_1 else NearSide.RANK_8
            else -> if (fileA > fileH) NearSide.FILE_A else NearSide.FILE_H
        }
    }

    /** Image position of board-plane coordinates (file 0..8, rank 0..8). */
    fun toImage(file: Double, rank: Double): Pt = homography.map(file, rank)

    /**
     * The step, in squares (file, rank), from a square to the one a piece standing on it falls
     * onto in the picture: straight up in the image, mapped to the board at that square. From
     * White's seat looking along the files it is (0, 1); from a seat off to the side it is a
     * diagonal, and a queen on f3 then fills g4 as well. Each component is taken when it is at
     * least four tenths of the larger one. (0, 0) when the board is seen from above.
     */
    fun coverStep(file: Int, rank: Int): Pair<Int, Int> {
        if (nearSide == NearSide.NONE) return 0 to 0
        val c = toImage(file + 0.5, rank + 0.5)
        val df = toImage(file + 0.51, rank + 0.5)
        val dr = toImage(file + 0.5, rank + 0.51)
        // image = J * board; solve J * v = (0, -1) for the board direction of image-up
        val a = (df.x - c.x) * 100; val b = (dr.x - c.x) * 100
        val cc = (df.y - c.y) * 100; val d = (dr.y - c.y) * 100
        val det = a * d - b * cc
        if (kotlin.math.abs(det) < 1e-9) return 0 to 0
        val vf = (0.0 * d - b * -1.0) / det
        val vr = (a * -1.0 - cc * 0.0) / det
        val m = maxOf(kotlin.math.abs(vf), kotlin.math.abs(vr))
        if (m < 1e-9) return 0 to 0
        fun step(v: Double) = if (kotlin.math.abs(v) >= 0.4 * m) (if (v > 0) 1 else -1) else 0
        return step(vf) to step(vr)
    }

    /**
     * Sampling window inside square ([file], [rank]) in board units, as (fileMin, fileMax, rankMin, rankMax).
     * The window is shifted away from the camera so a piece standing in front of the square hides less of it.
     */
    fun sampleWindow(file: Int, rank: Int): DoubleArray {
        val lateralLo = 0.22
        val lateralHi = 0.78
        val depthNear = 0.42   // start of the window measured from the edge nearest the camera
        val depthFar = 0.92
        return when (nearSide) {
            NearSide.NONE -> doubleArrayOf(file + lateralLo, file + lateralHi, rank + 0.2, rank + 0.8)
            NearSide.RANK_1 -> doubleArrayOf(file + lateralLo, file + lateralHi, rank + depthNear, rank + depthFar)
            NearSide.RANK_8 -> doubleArrayOf(file + lateralLo, file + lateralHi, rank + 1 - depthFar, rank + 1 - depthNear)
            NearSide.FILE_A -> doubleArrayOf(file + depthNear, file + depthFar, rank + lateralLo, rank + lateralHi)
            NearSide.FILE_H -> doubleArrayOf(file + 1 - depthFar, file + 1 - depthNear, rank + lateralLo, rank + lateralHi)
        }
    }

    /** Image-space polygon (4 points) of the sampling window of a square, for drawing overlays. */
    fun sampleWindowPolygon(file: Int, rank: Int): List<Pt> {
        val w = sampleWindow(file, rank)
        return listOf(toImage(w[0], w[2]), toImage(w[1], w[2]), toImage(w[1], w[3]), toImage(w[0], w[3]))
    }

    /** Image-space polygon of the whole square, for drawing overlays. */
    fun squarePolygon(file: Int, rank: Int): List<Pt> = listOf(
        toImage(file.toDouble(), rank.toDouble()),
        toImage(file + 1.0, rank.toDouble()),
        toImage(file + 1.0, rank + 1.0),
        toImage(file.toDouble(), rank + 1.0),
    )

    private fun dist(a: Pt, b: Pt) = hypot(a.x - b.x, a.y - b.y)
}
