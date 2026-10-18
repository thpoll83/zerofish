package com.chesscoach.core.vision

import com.chesscoach.core.chess.Square

/** A located, oriented board with everything the move inference needs. */
class Located(
    val geometry: BoardGeometry,
    val patches: Array<IntArray>,
    val features: SquareFeatures,
    val observations: Array<SquareObservation>,
    val rotation: Int,
)

/**
 * Turns detected (or tapped) corners into an oriented board. The detector returns the corners in
 * an arbitrary rotation; the dark a1 rule fixes it up to 180 degrees and the expected position
 * (plus the rotation used last time) settles the rest.
 */
object BoardLocator {
    fun locate(
        image: LumaImage,
        corners: List<Pt>,
        calibration: Calibration,
        expectedOccupancy: IntArray?,
        previousRotation: Int?,
        allowRotation: Boolean = true,
    ): Located {
        val rotations = if (allowRotation) listOf(0, 1, 2, 3) else listOf(0)
        val candidates = rotations.mapNotNull { rot ->
            val c = List(4) { corners[(it + rot) % 4] }
            val g = try {
                BoardGeometry(c)
            } catch (e: IllegalArgumentException) {
                return@mapNotNull null
            }
            val patches = SquareSampler.sample(image, g)
            val features = SquareFeatures.extract(patches, SquareSampler.sampleGradient(image, g))
            val obs = calibration.observe(features)
            // a1 is dark: squares with even file+rank must be the darker group.
            var dark = 0.0
            var light = 0.0
            for (sq in 0 until 64) {
                val m = patches[sq].average()
                if (Square.isLight(sq)) light += m else dark += m
            }
            val shadeOk = light > dark
            var cost = if (shadeOk) 0.0 else 12.0
            if (expectedOccupancy != null) cost += MoveInference.cost(expectedOccupancy, obs)
            if (previousRotation != null && rot == previousRotation) cost -= 1.0
            Located(g, patches, features, obs, rot) to cost
        }
        require(candidates.isNotEmpty()) { "No valid orientation" }
        return candidates.minByOrNull { it.second }!!.first
    }
}
