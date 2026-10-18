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
    private const val PLY_PENALTY = 0.3

    /**
     * Mismatch between [expectedOccupancy] and the camera. [occluders] (default: the expected
     * position itself) says which squares hold pieces that may hide their neighbours; pass the
     * position before the move so every candidate is judged with the same weights.
     */
    fun cost(
        expectedOccupancy: IntArray,
        obs: Array<SquareObservation>,
        nearSide: NearSide = NearSide.NONE,
        occluders: IntArray = expectedOccupancy,
    ): Double {
        var total = 0.0
        for (sq in 0 until 64) {
            val o = obs[sq]
            // a square hidden behind a piece in either the old or the new position counts less;
            // taking the minimum keeps a candidate from buying credibility with its own pieces
            val w = minOf(reliability(occluders, sq, nearSide), reliability(expectedOccupancy, sq, nearSide))
            when (expectedOccupancy[sq]) {
                0 -> total += w * o.occupied
                1 -> total += w * ((1 - o.occupied) + o.occupied * (1 - o.white))
                else -> total += w * ((1 - o.occupied) + o.occupied * o.white)
            }
        }
        return total
    }

    /**
     * How much to trust the camera's reading of [sq]: a piece standing between the square and the
     * camera hides part of it, so its reading counts less (0.5 when the next square towards the
     * camera is occupied, 0.8 when only the one behind that is).
     */
    fun reliability(occupancy: IntArray, sq: Int, nearSide: NearSide): Double {
        if (nearSide == NearSide.NONE) return 1.0
        val f = sq and 7
        val r = sq shr 3
        fun occ(ff: Int, rr: Int): Boolean = ff in 0..7 && rr in 0..7 && occupancy[rr * 8 + ff] != 0
        val (df, dr) = when (nearSide) {
            NearSide.RANK_1 -> 0 to -1
            NearSide.RANK_8 -> 0 to 1
            NearSide.FILE_A -> -1 to 0
            NearSide.FILE_H -> 1 to 0
            NearSide.NONE -> 0 to 0
        }
        return when {
            occ(f + df, r + dr) -> 0.5
            occ(f + 2 * df, r + 2 * dr) -> 0.8
            else -> 1.0
        }
    }

    /** Weight of the "which squares changed since the last scan" evidence relative to occupancy. */
    private const val CHANGE_WEIGHT = 0.35

    /**
     * Penalty for changes the camera saw (from [ChangeDetector], 0..1 per square) on squares the
     * candidate does not touch. Missed changes are not penalised: when the phone moved between
     * scans the detector sees nothing reliable, and that must not count against a real move.
     */
    fun changeCost(before: IntArray, after: IntArray, change: DoubleArray): Double {
        var total = 0.0
        for (sq in 0 until 64) {
            if (before[sq] == after[sq]) total += change[sq]
        }
        return CHANGE_WEIGHT * total
    }

    fun infer(
        board: Board,
        obs: Array<SquareObservation>,
        change: DoubleArray? = null,
        maxPlies: Int = 2,
        nearSide: NearSide = NearSide.NONE,
    ): InferenceResult {
        val out = ArrayList<Candidate>()
        val base = board.occupancy()
        fun total(after: IntArray, plies: Int): Double =
            cost(after, obs, nearSide, base) + plies * PLY_PENALTY + (if (change != null) changeCost(base, after, change) else 0.0)
        out.add(Candidate(emptyList(), total(base, 0), emptyList()))
        fun expand(b: Board, moves: List<Move>, sans: List<String>, depth: Int) {
            if (depth >= maxPlies) return
            for (m in b.legalMoves()) {
                val next = b.play(m)
                val ms = moves + m
                val ss = sans + b.san(m)
                out.add(Candidate(ms, total(next.occupancy(), ms.size), ss))
                expand(next, ms, ss, depth + 1)
            }
        }
        expand(board, emptyList(), emptyList(), 0)
        // Promotions to different pieces look identical to the camera; keep the queen and drop the rest.
        val dedup = out.filter { c -> c.moves.all { it.promotion == 0 || it.promotion == 5 } }
        return InferenceResult(dedup.sortedBy { it.cost })
    }
}
