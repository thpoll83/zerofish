package com.chesscoach.core.vision

import com.chesscoach.core.chess.Board
import com.chesscoach.core.chess.Move
import com.chesscoach.core.chess.Square
import kotlin.math.hypot

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

    enum class Status { NO_BOARD, LEARNING, LEARNED, TRACKING, UNSTABLE, MOVE_PLAYED, WAITING_FOR_START, AMBIGUOUS }

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
        /** When the camera cannot decide: the most likely explanations, for the user to pick from. */
        val suggestions: List<Candidate> = emptyList(),
        /** Every explanation this frame was scored against, best first (diagnostics). */
        val candidates: List<Candidate> = emptyList(),
        /**
         * The board no longer matches the tracked position and the tracker is still working out
         * why: a move is being read, and the user is not asked yet.
         */
        val reading: Boolean = false,
        /** How well this view will work, 0 to 1, with a hint naming the weakest point. */
        val quality: Quality? = null,
    )

    /**
     * How well the camera's view of the board will work, judged from what the tracker measures
     * anyway: how clearly the grid was found, how large the board is in the frame (zoom and
     * distance), and, while learning, how clearly pieces differ from empty squares and white
     * from black (light). The hint names the weakest of these.
     */
    class Quality(val score: Double, val hint: String)

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
    private var lastPatches: Array<IntArray>? = null
    private var lastRotation: Int? = null
    private var pending: List<Move> = emptyList()
    private var pendingCount = 0
    /** Frames in a row (quiet ones excepted) in which the board did not match the tracked position. */
    private var unsettled = 0
    /** Frames in a row that looked like the tracked position. */
    private var quiet = 0

    /**
     * Frames of an unexplained board before the best explanations are offered to the user. Most
     * moves resolve by themselves within a second or two (the hand leaves, the piece settles, the
     * confirming frames arrive), so asking earlier only shows buttons that vanish before they can
     * be tapped; until then the screen shows that a move is being read.
     */
    private val framesBeforeAsking = 14

    /** Frames of an unexplained board before three-move explanations are searched as well. */
    private val framesBeforeDeepSearch = 22

    /** Quiet frames in a row before an unexplained period is considered over. */
    private val quietFramesToSettle = 6

    /**
     * "No move" costs of recent quiet frames. Their median is how well a frame fits when nothing
     * is wrong; a move is only applied when the position after it fits nearly that well, otherwise
     * the explanation is incomplete (a second move went unnoticed) and goes to the user instead.
     */
    private val quietCosts = ArrayDeque<Double>()
    private val baselineWindow = 8
    private val baselineMinSamples = 4

    /**
     * How far above the quiet baseline the best explanation may still be applied. An unnoticed
     * extra move leaves two squares wrong, which on a real board reads as 1 to 2 cost units, so
     * this is tight on purpose: a doubtful move goes to the buttons rather than onto the board.
     */
    private val applySlack = 1.2

    /** A frame whose best explanation still costs more than this (about twenty squares wrong) is a misread. */
    private val badFrameCost = 20.0

    private fun ramp(v: Double, low: Double, high: Double): Double = ((v - low) / (high - low)).coerceIn(0.0, 1.0)

    private fun quality(image: LumaImage, grid: DetectedGrid, geometry: BoardGeometry, extra: List<Pair<Double, String>>): Quality {
        val c = geometry.corners
        val side = (0 until 4).map { i -> val p = c[i]; val q = c[(i + 1) % 4]; hypot(p.x - q.x, p.y - q.y) }.average()
        val fraction = side / minOf(image.width, image.height)
        val parts = ArrayList<Pair<Double, String>>()
        parts += ramp(grid.checkerScore, 0.4, 0.8) to "Board edges unclear: light the board evenly, avoid glare"
        parts += if (fraction > 0.95) 0.6 to "Too close: keep all four edges in the picture"
        else ramp(fraction, 0.25, 0.6) to "The board is small in the picture: move closer or zoom in"
        parts += extra
        val worst = parts.minBy { it.first }
        val score = 0.5 * worst.first + 0.5 * parts.map { it.first }.average()
        return Quality(score, if (worst.first < 0.7) worst.second else "Good view")
    }

    private fun baseline(): Double? =
        if (quietCosts.size < baselineMinSamples) null else quietCosts.sorted()[quietCosts.size / 2]

    private fun noteQuiet(noMoveCost: Double) {
        quietCosts.addLast(noMoveCost)
        while (quietCosts.size > baselineWindow) quietCosts.removeFirst()
    }

    /**
     * How much better than "no move" the best explanation must fit before the frame counts as
     * unexplained. One square read fully wrong costs about 1, so this is half a square: enough to
     * ignore the per-frame noise that makes some move look marginally better than none.
     */
    private val minEvidence = 0.6

    /**
     * Explanations offered to the user, by description, with the cost each had on the latest frame
     * that scored it and the unsettled-frame index when it was last among the best. Kept across
     * frames so the buttons do not change every frame.
     */
    private class Offer(var candidate: Candidate, var lastSeen: Int)
    private val offers = HashMap<String, Offer>()

    /** An explanation stays on offer this many unexplained frames after it last ranked among the best. */
    private val offerMemory = 12

    /**
     * An offer that now fits this much worse than the best offer is dropped: a single move that
     * was offered before the reply to it was played fits two squares worse than the pair once
     * the reply is on the board, and would otherwise stay on the buttons as a move already made.
     */
    private val offerSlack = 2.5

    /** Forget the pending move evidence, for example after the user corrected the position by hand. */
    fun resetPending() {
        pending = emptyList(); pendingCount = 0
        unsettled = 0
        quiet = 0
        offers.clear()
    }

    private fun offer(candidates: List<Candidate>) {
        for (c in candidates) {
            val o = offers[c.description]
            if (o == null) offers[c.description] = Offer(c, unsettled)
            else {
                o.candidate = c
                o.lastSeen = unsettled
            }
        }
        offers.values.removeIf { it.lastSeen < unsettled - offerMemory }
    }

    /** The latest frame's cost for every offer it scored, so stale offers are judged on the board as it is now. */
    private fun rescore(all: List<Candidate>) {
        if (offers.isEmpty()) return
        for (c in all) offers[c.description]?.let { it.candidate = c }
    }

    private fun suggestions(): List<Candidate> {
        val sorted = offers.values.map { it.candidate }.sortedBy { it.cost }
        val best = sorted.firstOrNull()?.cost ?: return emptyList()
        return sorted.filter { it.cost <= best + offerSlack }.take(6)
    }

    /** The user picked one of the offered explanations: apply it and resynchronise on the last frame. */
    fun accept(candidate: Candidate) {
        for (m in candidate.moves) board = board.play(m)
        previousPatches = lastPatches
        lastRotation?.let { rotation = it }
        quietCosts.clear()
        resetPending()
    }

    /** Replace the tracked position (after an undo or a typed move). The last frame no longer matches it. */
    fun setBoard(b: Board) {
        board = b
        previousPatches = null
        quietCosts.clear()
        resetPending()
    }

    /** Start over: wait for the starting position again and relearn thresholds. */
    fun restart() {
        board = Board.start()
        phase = Phase.LEARNING
        calibration = null
        learnStreak = 0
        previousPatches = null
        quietCosts.clear()
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
        // The weakest pieces (black on dark squares at the far rank) read low on real boards, so
        // allow three weak pieces and two phantom pieces: the fourth-weakest piece must still read
        // clearly above the third-strongest empty square. White must be brighter than black.
        val emptyHigh = empties[empties.size - 3]
        val pieceLow = pieces[3]
        val whites = (0 until 64).filter { Square.rank(it) <= 1 }.map { f.colourScore[it] }.average()
        val blacks = (0 until 64).filter { Square.rank(it) >= 6 }.map { f.colourScore[it] }.average()
        val looksLikeStart = pieceLow > emptyHigh + 0.08 && whites > blacks + 0.2
        val q = quality(
            image, grid, located.geometry,
            listOf(
                ramp(pieceLow - emptyHigh, 0.0, 0.25) to "Pieces hard to tell from empty squares: more light from above",
                ramp(whites - blacks, 0.1, 0.6) to "White and black pieces look alike: more light, or turn the torch on",
            ),
        )
        if (!looksLikeStart) {
            learnStreak = 0
            return FrameResult(
                Status.WAITING_FOR_START, located.geometry, located.observations, null, 0, emptyList(),
                "Board found. Set up the starting position with White's pieces nearest to you or facing the camera.",
                quality = q,
            )
        }
        learnStreak++
        rotation = located.rotation
        if (learnStreak < framesToLearn) {
            return FrameResult(Status.LEARNING, located.geometry, located.observations, null, learnStreak, emptyList(), "Learning your pieces ($learnStreak/$framesToLearn)", quality = q)
        }
        val cal = Calibration.learn(f)
        calibration = cal
        previousPatches = located.patches
        board = Board.start()
        phase = Phase.TRACKING
        resetPending()
        return FrameResult(Status.LEARNED, located.geometry, cal.observe(f), null, 0, emptyList(), "Ready. Play on the board.", quality = q)
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
        lastPatches = located.patches
        lastRotation = located.rotation
        val change = previousPatches?.let { ChangeDetector.scores(it, located.patches) }
        val result = MoveInference.infer(board, obs, change, maxPlies = 2, nearSide = located.geometry.nearSide)
        val best = result.best ?: return FrameResult(Status.TRACKING, located.geometry, obs, null, 0, emptyList(), "Tracking")
        if (best.cost > badFrameCost) {
            // even the best explanation leaves a third of the board wrong: the grid was misread
            // (or a body covers it). Like a hand over the board, the frame counts for nothing.
            return FrameResult(Status.UNSTABLE, located.geometry, obs, null, pendingCount, emptyList(), "Hold still, cannot read the board", candidates = result.candidates)
        }
        val noMove = result.candidates.firstOrNull { it.moves.isEmpty() }
        val evidence = (noMove?.cost ?: Double.POSITIVE_INFINITY) - best.cost
        if (best.moves.isEmpty() || evidence < minEvidence) {
            // The board looks like the tracked position. A few such frames in a row end any
            // unexplained period; a single one (a bad frame) keeps the offers on the screen.
            quiet++
            // only settled frames define the baseline: a weakly seen move would otherwise raise it
            if (unsettled == 0) noMove?.let { noteQuiet(it.cost) }
            if (quiet >= quietFramesToSettle) resetPending()
            rescore(result.candidates)
            val asking = unsettled >= framesBeforeAsking && offers.isNotEmpty()
            return if (asking) FrameResult(Status.AMBIGUOUS, located.geometry, obs, best, pendingCount, emptyList(), "Not sure what was played. Tap the right one, or type it.", suggestions(), candidates = result.candidates)
            else FrameResult(Status.TRACKING, located.geometry, obs, best, 0, emptyList(), if (unsettled > 0) "Reading the move..." else "Tracking", candidates = result.candidates, reading = unsettled > 0)
        }
        // The board no longer matches the tracked position. Count how long this lasts.
        quiet = 0
        unsettled++
        rescore(result.candidates)
        // three agreeing frames are required anyway, so a modest per-frame margin is enough
        if (result.margin >= 0.3) {
            if (best.moves == pending) pendingCount++ else {
                pending = best.moves; pendingCount = 1
            }
            val base = baseline()
            val fits = base == null || best.cost <= base + applySlack
            if (pendingCount >= framesToConfirm && fits) {
                val applied = pending
                for (m in applied) board = board.play(m)
                previousPatches = located.patches
                rotation = located.rotation
                quietCosts.clear()
                resetPending()
                return FrameResult(Status.MOVE_PLAYED, located.geometry, obs, best, framesToConfirm, applied, "Played ${best.description}", candidates = result.candidates)
            }
            if (pendingCount >= framesToConfirm && !fits) {
                // The move alone does not explain the board: something else changed as well.
                // Offer it, and keep looking for the fuller explanation.
                offer(listOf(best))
                if (unsettled < framesBeforeAsking) {
                    return FrameResult(
                        Status.TRACKING, located.geometry, obs, best, pendingCount, emptyList(),
                        "Seeing ${best.description}, but more changed (%.1f, quiet is %.1f)".format(best.cost, base), candidates = result.candidates,
                        reading = true,
                    )
                }
            }
        }
        if (unsettled >= framesBeforeAsking) {
            // Offer the most likely explanations. After a while also search three-move sequences
            // (once a second: it is a hundred times more work than two moves).
            offer(result.candidates.filter { it.moves.isNotEmpty() }.take(4))
            if (unsettled >= framesBeforeDeepSearch && (unsettled - framesBeforeDeepSearch) % 4 == 0) {
                val deep = MoveInference.infer(board, obs, change, maxPlies = 3, nearSide = located.geometry.nearSide)
                offer(deep.candidates.filter { it.moves.size == 3 }.take(5))
            }
            return FrameResult(
                Status.AMBIGUOUS, located.geometry, obs, best, pendingCount, emptyList(),
                "Not sure what was played. Tap the right one, or type it.", suggestions(), result.candidates,
            )
        }
        val runnerUp = result.candidates.getOrNull(1)
        val msg = if (result.margin >= 0.3) "Seeing ${best.description} ($pendingCount/$framesToConfirm)"
        else "Maybe ${best.description} (%.2f) or ${runnerUp?.description} (%.2f); unchanged %.2f".format(best.cost, runnerUp?.cost ?: 0.0, noMove?.cost ?: 0.0)
        return FrameResult(Status.TRACKING, located.geometry, obs, best, pendingCount, emptyList(), msg, candidates = result.candidates, reading = true)
    }
}
