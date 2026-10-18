package com.chesscoach.core.vision

import com.chesscoach.core.chess.Board
import com.chesscoach.core.chess.Move
import com.chesscoach.core.chess.Square

/**
 * Follows a game through a stream of camera frames. Feed every frame to [process]; the tracker
 * first waits for the starting position to be visible and stable (that is its calibration), then
 * applies a move once the same move explains several consecutive frames.
 *
 * Pure Kotlin, no timing: the caller decides the frame rate. Not thread-safe; call from one thread.
 */
class LiveTracker(
    board: Board = Board.start(),
    /** Consecutive frames that must agree before a move is applied. */
    private val framesToConfirm: Int = 3,
    /** Consecutive frames showing the starting position before thresholds are locked. */
    private val framesToLearn: Int = 3,
) {
    enum class Phase { LEARNING, TRACKING }

    enum class Status { NO_BOARD, LEARNING, LEARNED, TRACKING, UNSTABLE, MOVE_PLAYED, WAITING_FOR_START }

    class FrameResult(
        val status: Status,
        val geometry: BoardGeometry?,
        val observations: Array<SquareObservation>?,
        /** Best explanation of the current frame while tracking (may be "no move"). */
        val candidate: Candidate?,
        /** Frames in a row that agreed on [candidate]. */
        val agreement: Int,
        /** Moves applied by this frame, if any. */
        val applied: List<Move>,
        val message: String,
    )

    var board: Board = board
        private set
    var phase: Phase = Phase.LEARNING
        private set
    var calibration: Calibration? = null
        private set
    var rotation: Int? = null
        private set

    private var learnStreak = 0
    private var previousPatches: Array<IntArray>? = null
    private var pending: List<Move> = emptyList()
    private var pendingCount = 0

    /** Forget the pending move evidence, for example after the user corrected the position by hand. */
    fun resetPending() {
        pending = emptyList(); pendingCount = 0
    }

    /** Replace the tracked position (after an undo or a typed move). The last frame no longer matches it. */
    fun setBoard(b: Board) {
        board = b
        previousPatches = null
        resetPending()
    }

    /** Start over: wait for the starting position again and relearn thresholds. */
    fun restart() {
        board = Board.start()
        phase = Phase.LEARNING
        calibration = null
        learnStreak = 0
        previousPatches = null
        resetPending()
    }

    fun process(image: LumaImage): FrameResult {
        val grid = GridDetector.detect(image, debugLines = false)
            ?: return FrameResult(Status.NO_BOARD, null, null, null, 0, emptyList(), "Looking for the board")
        return when (phase) {
            Phase.LEARNING -> learn(image, grid)
            Phase.TRACKING -> track(image, grid)
        }
    }

    private fun learn(image: LumaImage, grid: DetectedGrid): FrameResult {
        val located = BoardLocator.locate(image, grid.corners, Calibration.default(), Board.start().occupancy(), rotation)
        val f = located.features
        // Does this frame look like the starting position? Occupied ranks must clearly differ from
        // empty ones and white pieces must be brighter than black ones, before any thresholds exist.
        val empties = (0 until 64).filter { Square.rank(it) in 2..5 }.map { f.occFraction[it] }.sorted()
        val pieces = (0 until 64).filter { Square.rank(it) !in 2..5 }.map { f.occFraction[it] }.sorted()
        val split = (empties[empties.size / 2] + pieces[pieces.size / 2]) / 2
        val piecesSeen = pieces.count { it > split + 0.03 }
        val emptiesSeen = empties.count { it < split - 0.03 }
        val whites = (0 until 64).filter { Square.rank(it) <= 1 }.map { f.colourScore[it] }.average()
        val blacks = (0 until 64).filter { Square.rank(it) >= 6 }.map { f.colourScore[it] }.average()
        // at most two pieces missing or two phantom pieces, and white clearly brighter than black
        val looksLikeStart = piecesSeen >= 30 && emptiesSeen >= 30 && whites > blacks + 0.2
        if (!looksLikeStart) {
            learnStreak = 0
            return FrameResult(
                Status.WAITING_FOR_START, located.geometry, located.observations, null, 0, emptyList(),
                "Board found. Set up the starting position with White's pieces nearest to you or facing the camera.",
            )
        }
        learnStreak++
        rotation = located.rotation
        if (learnStreak < framesToLearn) {
            return FrameResult(Status.LEARNING, located.geometry, located.observations, null, learnStreak, emptyList(), "Learning your pieces ($learnStreak/$framesToLearn)")
        }
        val cal = Calibration.learn(f)
        calibration = cal
        previousPatches = located.patches
        board = Board.start()
        phase = Phase.TRACKING
        resetPending()
        return FrameResult(Status.LEARNED, located.geometry, cal.observe(f), null, 0, emptyList(), "Ready. Play on the board.")
    }

    private fun track(image: LumaImage, grid: DetectedGrid): FrameResult {
        val cal = calibration ?: return FrameResult(Status.NO_BOARD, null, null, null, 0, emptyList(), "No calibration")
        val located = BoardLocator.locate(image, grid.corners, cal, board.occupancy(), rotation)
        val obs = located.observations
        val unsure = obs.count { it.unsure }
        if (unsure > 14) {
            // a hand or a shadow over the board: do not count this frame for or against anything
            return FrameResult(Status.UNSTABLE, located.geometry, obs, null, pendingCount, emptyList(), "Hold still, hand or shadow over the board")
        }
        val change = previousPatches?.let { ChangeDetector.scores(it, located.patches) }
        val result = MoveInference.infer(board, obs, change, maxPlies = 2, nearSide = located.geometry.nearSide)
        val best = result.best ?: return FrameResult(Status.TRACKING, located.geometry, obs, null, 0, emptyList(), "Tracking")
        // three agreeing frames are required anyway, so a modest per-frame margin is enough
        if (best.moves.isEmpty() || result.margin < 0.3) {
            // settled or ambiguous frame: evidence for a pending move does not accumulate
            if (best.moves.isEmpty()) resetPending()
            val runnerUp = result.candidates.getOrNull(1)
            val msg = if (best.moves.isEmpty()) "Tracking" else "Maybe ${best.description} (%.2f) or ${runnerUp?.description} (%.2f)".format(best.cost, runnerUp?.cost ?: 0.0)
            return FrameResult(Status.TRACKING, located.geometry, obs, best, pendingCount, emptyList(), msg)
        }
        if (best.moves == pending) pendingCount++ else {
            pending = best.moves; pendingCount = 1
        }
        if (pendingCount < framesToConfirm) {
            return FrameResult(Status.TRACKING, located.geometry, obs, best, pendingCount, emptyList(), "Seeing ${best.description} ($pendingCount/$framesToConfirm)")
        }
        val applied = pending
        for (m in applied) board = board.play(m)
        previousPatches = located.patches
        rotation = located.rotation
        resetPending()
        return FrameResult(Status.MOVE_PLAYED, located.geometry, obs, best, framesToConfirm, applied, "Played ${best.description}")
    }
}
