package com.chesscoach.core.vision

import com.chesscoach.core.chess.Board
import com.chesscoach.core.chess.Move

/** One explanation of the scanned board: zero, one or two plies played since [MoveInference.infer] was given [Board]. */
data class Candidate(val moves: List<Move>, val cost: Double, val sans: List<String>) {
    val description: String get() = if (moves.isEmpty()) "no move" else sans.joinToString(" ")
}

class InferenceResult(val candidates: List<Candidate>) {
    val best: Candidate? get() = candidates.firstOrNull()

    /** Gap between the best and the runner-up. Larger is more certain; below ~0.5 is a coin flip. */
    val margin: Double get() = if (candidates.size < 2) Double.POSITIVE_INFINITY else candidates[1].cost - candidates[0].cost
}

/**
 * Picks the legal move sequence whose resulting occupancy best matches what the camera saw.
 * Only empty/white/black per square is needed, so no piece classifier is involved.
 */
object MoveInference {
    /** Each extra ply costs this much, so a single move wins over two moves that fit equally well. */
    private const val PLY_PENALTY = 0.6

    fun cost(expectedOccupancy: IntArray, obs: Array<SquareObservation>): Double {
        var total = 0.0
        for (sq in 0 until 64) {
            val o = obs[sq]
            when (expectedOccupancy[sq]) {
                0 -> total += o.occupied
                1 -> total += (1 - o.occupied) + o.occupied * (1 - o.white)
                else -> total += (1 - o.occupied) + o.occupied * o.white
            }
        }
        return total
    }

    fun infer(board: Board, obs: Array<SquareObservation>, maxPlies: Int = 2): InferenceResult {
        val out = ArrayList<Candidate>()
        out.add(Candidate(emptyList(), cost(board.occupancy(), obs), emptyList()))
        if (maxPlies >= 1) {
            for (m1 in board.legalMoves()) {
                val b1 = board.play(m1)
                val c1 = cost(b1.occupancy(), obs) + PLY_PENALTY
                out.add(Candidate(listOf(m1), c1, listOf(board.san(m1))))
                if (maxPlies >= 2) {
                    for (m2 in b1.legalMoves()) {
                        val b2 = b1.play(m2)
                        val c2 = cost(b2.occupancy(), obs) + 2 * PLY_PENALTY
                        out.add(Candidate(listOf(m1, m2), c2, listOf(board.san(m1), b1.san(m2))))
                    }
                }
            }
        }
        // Promotions to different pieces look identical to the camera; keep the queen and drop the rest.
        val dedup = out.filter { c -> c.moves.all { it.promotion == 0 || it.promotion == 5 } }
        return InferenceResult(dedup.sortedBy { it.cost })
    }
}
