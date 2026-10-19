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

    /**
     * The square readings of the last stable frame, blended into each new frame's readings: a
     * piece does not change between two frames unless a hand came in between, so a square that
     * reads as a piece in one frame and empty in the next is noise, not a move. A hand over the
     * board (an unstable frame) resets the blend, so the first clean frame after it counts in
     * full.
     */
    private var smoothed: Array<SquareObservation>? = null

    /** Weight of the current frame in the blend; the rest is the blend so far. */
    private val smoothingWeight = 0.6

    private fun smooth(obs: Array<SquareObservation>): Array<SquareObservation> {
        val prev = smoothed ?: return obs.also { smoothed = it }
        val w = smoothingWeight
        val out = Array(64) { i ->
            val a = obs[i]; val b = prev[i]
            SquareObservation(
                w * a.occupied + (1 - w) * b.occupied, w * a.white + (1 - w) * b.white,
                w * a.occFraction + (1 - w) * b.occFraction, w * a.colourScore + (1 - w) * b.colourScore,
            )
        }
        smoothed = out
        return out
    }

    /**
     * The user said the starting position is set up: learn from the next frames even when the
     * pieces cannot be told from empty squares well enough to recognise it (black pieces on
     * dark squares of a glossy board). Where every piece stands is then known regardless.
     */
    private var startConfirmed = false
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

    /**
     * How the board reads when nothing is wrong: the number of unsure squares and the cost of
     * the tracked position on the learning frame, updated on quiet frames. A board whose pieces
     * are hard to tell from its squares reads unsure and costly on every frame; a hand or a
     * misread grid is a frame that reads much worse than that, not worse than a fixed number.
     */
    private var usualUnsure = 0.0
    private var usualCost = 0.0
    private val unsureSlack = 10
    private val costSlack = 10.0

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
     * Explanations offered to the user, by description, in the order they were first seen. Once
     * offered, an explanation stays until the position is settled or changed, and new ones are
     * only appended: a button that moves or vanishes cannot be tapped. At most [maxOffers]
     * one- and two-move explanations; three-move ones from the deep search are always added.
     */
    private val offers = LinkedHashMap<String, Candidate>()
    private val maxOffers = 10

    /** Unexplained frames before the likeliest explanations are offered as buttons (while still reading). */
    private val framesBeforeOffering = 3

    /** An explanation is offered only while it fits within this of the best one on that frame. */
    private val offerWindow = 1.5

    /** Forget the pending move evidence, for example after the user corrected the position by hand. */
    fun resetPending() {
        pending = emptyList(); pendingCount = 0
        unsettled = 0
        quiet = 0
        offers.clear()
    }

    private fun offer(candidates: List<Candidate>, always: Boolean = false) {
        for (c in candidates) {
            if (offers.containsKey(c.description)) continue
            if (!always && offers.size >= maxOffers) continue
            offers[c.description] = c
        }
    }

    private fun suggestions(): List<Candidate> = offers.values.toList()

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

    /** The user confirms that all pieces stand on their starting squares. */
    fun confirmStart() {
        if (phase == Phase.LEARNING) startConfirmed = true
    }

    /** Start over: wait for the starting position again and relearn thresholds. */
    fun restart() {
        board = Board.start()
        phase = Phase.LEARNING
        calibration = null
        learnStreak = 0
        startConfirmed = false
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
        if (!looksLikeStart && !startConfirmed) {
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
        startConfirmed = false
        smoothed = null
        resetPending()
        val obs = cal.observe(f)
        usualUnsure = obs.count { it.unsure }.toDouble()
        usualCost = MoveInference.cost(board.occupancy(), obs, located.geometry.nearSide)
        return FrameResult(Status.LEARNED, located.geometry, obs, null, 0, emptyList(), "Ready. Play on the board.", quality = q)
    }

    private fun track(image: LumaImage, grid: DetectedGrid): FrameResult {
        val cal = calibration ?: return FrameResult(Status.NO_BOARD, null, null, null, 0, emptyList(), "No calibration")
        val located = BoardLocator.locate(image, grid.corners, cal, board.occupancy(), rotation)
        val raw = located.observations
        val unsure = raw.count { it.unsure }
        if (unsure > maxOf(14.0, usualUnsure + unsureSlack)) {
            // a hand or a shadow over the board: do not count this frame for or against anything
            smoothed = null
            return FrameResult(Status.UNSTABLE, located.geometry, raw, null, pendingCount, emptyList(), "Hold still, hand or shadow over the board")
        }
        val obs = smooth(raw)
        lastPatches = located.patches
        lastRotation = located.rotation
        val change = previousPatches?.let { ChangeDetector.scores(it, located.patches) }
        val result = MoveInference.infer(board, obs, change, maxPlies = 2, nearSide = located.geometry.nearSide)
        val best = result.best ?: return FrameResult(Status.TRACKING, located.geometry, obs, null, 0, emptyList(), "Tracking")
        if (best.cost > maxOf(badFrameCost, (baseline() ?: usualCost) + costSlack)) {
            // even the best explanation leaves far more of the board wrong than usual: the grid
            // was misread (or a body covers it). Like a hand over the board, the frame counts for nothing.
            return FrameResult(Status.UNSTABLE, located.geometry, obs, null, pendingCount, emptyList(), "Hold still, cannot read the board", candidates = result.candidates)
        }
        // the usual readings follow the light slowly
        usualUnsure = 0.9 * usualUnsure + 0.1 * unsure
        val noMove = result.candidates.firstOrNull { it.moves.isEmpty() }
        val evidence = (noMove?.cost ?: Double.POSITIVE_INFINITY) - best.cost
        if (best.moves.isEmpty() || evidence < minEvidence) {
            // The board looks like the tracked position. A few such frames in a row end any
            // unexplained period; a single one (a bad frame) keeps the offers on the screen.
            quiet++
            // only settled frames define the baseline: a weakly seen move would otherwise raise it
            if (unsettled == 0) noMove?.let { noteQuiet(it.cost); usualCost = 0.9 * usualCost + 0.1 * it.cost }
            if (quiet >= quietFramesToSettle) resetPending()
            val asking = unsettled >= framesBeforeAsking && offers.isNotEmpty()
            return if (asking) FrameResult(Status.AMBIGUOUS, located.geometry, obs, best, pendingCount, emptyList(), "Not sure what was played. Tap the right one, or type it.", suggestions(), candidates = result.candidates)
            else FrameResult(Status.TRACKING, located.geometry, obs, best, 0, emptyList(), if (unsettled > 0) "Reading the move..." else "Tracking", suggestions(), candidates = result.candidates, reading = unsettled > 0)
        }
        // The board no longer matches the tracked position. Count how long this lasts.
        quiet = 0
        unsettled++
        // From the first second on, the likeliest explanations are offered as buttons while the
        // reading goes on: the user may know the move and need not wait for the question.
        if (unsettled >= framesBeforeOffering) offer(result.candidates.filter { it.moves.isNotEmpty() && it.cost <= best.cost + offerWindow }.take(3))
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
                        "Seeing ${best.description}, but more changed (%.1f, quiet is %.1f)".format(best.cost, base), suggestions(), candidates = result.candidates,
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
                offer(deep.candidates.filter { it.moves.size == 3 }.take(3), always = true)
            }
            return FrameResult(
                Status.AMBIGUOUS, located.geometry, obs, best, pendingCount, emptyList(),
                "Not sure what was played. Tap the right one, or type it.", suggestions(), result.candidates,
            )
        }
        val runnerUp = result.candidates.getOrNull(1)
        val msg = if (result.margin >= 0.3) "Seeing ${best.description} ($pendingCount/$framesToConfirm)"
        else "Maybe ${best.description} (%.2f) or ${runnerUp?.description} (%.2f); unchanged %.2f".format(best.cost, runnerUp?.cost ?: 0.0, noMove?.cost ?: 0.0)
        return FrameResult(Status.TRACKING, located.geometry, obs, best, pendingCount, emptyList(), msg, suggestions(), candidates = result.candidates, reading = true)
    }
}
