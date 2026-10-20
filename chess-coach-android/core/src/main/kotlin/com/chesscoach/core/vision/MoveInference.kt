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
        /** The pieces' heights (see [Board.heights]) in the two positions, when known: a king hides far more than a pawn. */
        occluderHeights: IntArray? = null,
        expectedHeights: IntArray? = occluderHeights,
    ): Double {
        var total = 0.0
        for (sq in 0 until 64) {
            val o = obs[sq]
            // a square hidden behind a piece in either the old or the new position counts less;
            // taking the minimum keeps a candidate from buying credibility with its own pieces
            val w = minOf(reliability(occluders, sq, nearSide, occluderHeights), reliability(expectedOccupancy, sq, nearSide, expectedHeights))
            // A body in front can only make a square read as occupied, never as empty: an
            // "occupied" reading behind a piece counts less, an "empty" reading counts in full
            // (a vacated square behind the king is still plainly bare when it reads so).
            when (expectedOccupancy[sq]) {
                0 -> total += w * o.occupied
                1 -> total += (1 - o.occupied) + w * o.occupied * (1 - o.white)
                else -> total += (1 - o.occupied) + w * o.occupied * o.white
            }
        }
        return total
    }

    /**
     * How much to trust the camera's reading of [sq]: a piece standing between the square and the
     * camera hides part of it, so its reading counts less (0.5 when the next square towards the
     * camera is occupied, 0.8 when only the one behind that is). With [heights] known, a pawn in
     * front hides less (0.6, and nothing two squares on) and a queen or king more (0.35 and
     * 0.65): from a low seat the king's body fills e2 after e2-e4, and the vacated square's
     * reading must count for little or the move is never seen.
     */
    fun reliability(occupancy: IntArray, sq: Int, nearSide: NearSide, heights: IntArray? = null): Double {
        if (nearSide == NearSide.NONE) return 1.0
        val f = sq and 7
        val r = sq shr 3
        fun occ(ff: Int, rr: Int): Boolean = ff in 0..7 && rr in 0..7 && occupancy[rr * 8 + ff] != 0
        fun height(ff: Int, rr: Int): Int = heights?.get(rr * 8 + ff) ?: 2
        val (df, dr) = when (nearSide) {
            NearSide.RANK_1 -> 0 to -1
            NearSide.RANK_8 -> 0 to 1
            NearSide.FILE_A -> -1 to 0
            NearSide.FILE_H -> 1 to 0
            NearSide.NONE -> 0 to 0
        }
        return when {
            occ(f + df, r + dr) -> when (height(f + df, r + dr)) { 1 -> 0.6; 3 -> 0.35; else -> 0.5 }
            occ(f + 2 * df, r + 2 * dr) -> when (height(f + 2 * df, r + 2 * dr)) { 1 -> 1.0; 3 -> 0.65; else -> 0.8 }
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
        val baseHeights = board.heights()
        fun total(after: IntArray, afterHeights: IntArray, plies: Int): Double =
            cost(after, obs, nearSide, base, baseHeights, afterHeights) + plies * PLY_PENALTY + (if (change != null) changeCost(base, after, change) else 0.0)
        out.add(Candidate(emptyList(), total(base, baseHeights, 0), emptyList()))
        fun expand(b: Board, moves: List<Move>, sans: List<String>, depth: Int) {
            if (depth >= maxPlies) return
            for (m in b.legalMoves()) {
                val next = b.play(m)
                val ms = moves + m
                val ss = sans + b.san(m)
                out.add(Candidate(ms, total(next.occupancy(), next.heights(), ms.size), ss))
                expand(next, ms, ss, depth + 1)
            }
        }
        expand(board, emptyList(), emptyList(), 0)
        // Promotions to different pieces look identical to the camera; keep the queen and drop the rest.
        val dedup = out.filter { c -> c.moves.all { it.promotion == 0 || it.promotion == 5 } }
        return InferenceResult(dedup.sortedBy { it.cost })
    }
}
