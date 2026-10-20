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

    /**
     * The colour shift the pieces are read through, chosen while learning when the frames carry
     * colour and the pieces differ from their squares in colour more than in brightness; null
     * for plain luma. The grid is always found on plain luma.
     */
    var projection: ColorProjection? = null
        private set

    private var learnStreak = 0

    /**
     * The board's corners (a1, h1, h8, a8) as verified by the starting position. The grid
     * finder, working afresh, lands a square off or turned by a quarter now and then on a board
     * whose frame matches its dark squares, and such a grid reads a move that was not played.
     * Once locked, each frame first looks for the board where it was ([GridDetector.track]:
     * the lock pulled onto the x-corners around it, which follows the few pixels a touch moves
     * the phone by and cannot land a square off); as long as that succeeds the board has not
     * moved, and the lock follows it by [lockFollow] of the difference. Only when it fails
     * (the camera moved further, a hand covers the corners) does the full search run. A found
     * grid within [lockTolerance] squares of the lock nudges it; one further away puts the
     * grid in dispute: the frame is still read through the lock, but nothing it shows is
     * applied or remembered, and when the same new grid (within the tolerance of itself) is
     * seen [framesToRelock] frames in a row while the board is not seen at the lock, the
     * camera was moved and it becomes the lock. The orientation is never chosen again: a board
     * does not turn by a quarter between two frames, and the grid's corners are matched to the
     * lock's by the rotation that fits best. A frame without any grid is read through the lock
     * for up to [framesWithoutGrid] frames.
     */
    private var locked: List<Pt>? = null
    private var awayCandidate: List<Pt>? = null

    /** Each square's own empty picture, gathered on quiet frames through the locked grid. */
    private val templates = SquareTemplates()
    private val templateBlend = 0.3

    /**
     * Squares a move has just left, with the settled frames left in which their empty picture
     * is taken whatever they read: the moment a move vacates a square, the square is known
     * empty, and that is the one chance to learn a square that misreads when empty (the
     * square nearest the camera is lit brighter than the shade's typical square and reads as
     * a white piece by tone). Later the picture refreshes only while the square reads empty.
     */
    private val vacated = HashMap<Int, Int>()
    private val vacatedFrames = 6

    private fun noteVacated(before: Board, after: Board) {
        val was = before.occupancy()
        val now = after.occupancy()
        for (sq in 0 until 64) if (was[sq] != 0 && now[sq] == 0) vacated[sq] = vacatedFrames
    }
    private var awayFrames = 0
    private var missingFrames = 0
    private val lockTolerance = 0.35
    private val framesToRelock = 3
    private val framesWithoutGrid = 8
    private val lockFollow = 0.2

    /** True while a detection elsewhere disputes the lock: the frame's reading settles nothing. */
    private var disputed = false

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

    /** Squares changed since the last frame above which something is in motion over the board. */
    private val maxMovingSquares = 5

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

    /** How far the best explanation must lead the runner-up, per frame, to be applied without asking. */
    private val applyMargin = 0.3

    /** The lead the far one of two cover twins needs (see [coverTwins]). */
    private val twinMargin = 1.5

    /** True when [longer] is [shorter] with one or more moves appended. */
    private fun extends(longer: Candidate, shorter: Candidate): Boolean =
        longer.moves.size > shorter.moves.size && longer.moves.take(shorter.moves.size) == shorter.moves

    /** The destination of [b]'s move where it differs from [a]'s: the near square of two cover twins. */
    private fun nearSquare(a: Candidate, b: Candidate): Int {
        val i = a.moves.indices.first { a.moves[it] != b.moves[it] }
        return b.moves[i].to
    }

    /** True when [a]'s differing destination lies one cover step beyond [b]'s: the square a body on [b]'s square would fill. */
    private fun farTwin(a: Candidate, b: Candidate, geometry: BoardGeometry): Boolean {
        val i = a.moves.indices.firstOrNull { a.moves[it] != b.moves[it] } ?: return false
        val near = b.moves[i].to
        val (df, dr) = geometry.coverStep(Square.file(near), Square.rank(near))
        return Square.file(a.moves[i].to) - Square.file(near) == df && Square.rank(a.moves[i].to) - Square.rank(near) == dr
    }

    /** True when [a] and [b] differ only in one move's destination, by the step a piece's body covers in the picture. */
    private fun coverTwins(a: Candidate, b: Candidate, geometry: BoardGeometry): Boolean {
        if (a.moves.size != b.moves.size || a.moves.isEmpty()) return false
        val differing = a.moves.indices.filter { a.moves[it] != b.moves[it] }
        if (differing.size != 1) return false
        val ma = a.moves[differing[0]]; val mb = b.moves[differing[0]]
        if (ma.from != mb.from) return false
        val (df, dr) = geometry.coverStep(Square.file(ma.to), Square.rank(ma.to))
        if (df == 0 && dr == 0) return false
        val fileDiff = Square.file(mb.to) - Square.file(ma.to)
        val rankDiff = Square.rank(mb.to) - Square.rank(ma.to)
        return (fileDiff == df && rankDiff == dr) || (fileDiff == -df && rankDiff == -dr)
    }

    /** Forget the pending move evidence, for example after the user corrected the position by hand. */
    fun resetPending() {
        pending = emptyList(); pendingCount = 0
        unsettled = 0
        quiet = 0
        offers.clear()
    }

    /**
     * Offers the first move of each explanation: the user confirms one move at a time, and
     * once it is applied the next one is read from the new position (or offered in turn). A
     * button for a pair of moves was easy to misread and tap.
     */
    private fun offer(candidates: List<Candidate>, always: Boolean = false) {
        for (full in candidates) {
            if (full.moves.isEmpty()) continue
            val c = if (full.moves.size == 1) full else Candidate(listOf(full.moves[0]), full.cost, listOf(full.sans[0]))
            if (offers.containsKey(c.description)) continue
            if (!always && offers.size >= maxOffers) continue
            offers[c.description] = c
        }
    }

    private fun suggestions(): List<Candidate> = offers.values.toList()

    /** The user picked one of the offered explanations: apply it and resynchronise on the last frame. */
    fun accept(candidate: Candidate) {
        val before = board
        for (m in candidate.moves) board = board.play(m)
        noteVacated(before, board)
        previousPatches = lastPatches
        lastRotation?.let { rotation = it }
        quietCosts.clear()
        resetPending()
    }

    /** Replace the tracked position (after an undo or a typed move). The last frame no longer matches it. */
    fun setBoard(b: Board) {
        noteVacated(board, b)
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
        projection = null
        locked = null
        awayCandidate = null
        awayFrames = 0
        missingFrames = 0
        templates.clear()
        vacated.clear()
        learnStreak = 0
        startConfirmed = false
        previousPatches = null
        quietCosts.clear()
        resetPending()
    }

    fun process(image: LumaImage): FrameResult {
        val lock = locked
        if (phase == Phase.TRACKING && lock != null) {
            // the board where it was: most frames end here, at a fraction of a search's cost
            val tracked = GridDetector.track(image, lock)
            if (tracked != null && !disputed) return track(image, null, tracked)
            return track(image, GridDetector.detect(image, debugLines = false), tracked)
        }
        val grid = GridDetector.detect(image, debugLines = false)
        return when (phase) {
            Phase.LEARNING -> if (grid == null) FrameResult(Status.NO_BOARD, null, null, null, 0, emptyList(), "Looking for the board") else learn(image, grid)
            Phase.TRACKING -> track(image, grid, null)
        }
    }

    /**
     * The corners to read this frame through, and whether the orientation may be chosen anew:
     * the lock, following the board [tracked] at it or nudged towards a found [grid] that
     * agrees with it, or the grid itself when there is no lock or the camera has moved. Null
     * when there is nothing to read.
     */
    private fun cornersForFrame(grid: DetectedGrid?, tracked: DetectedGrid?): Pair<List<Pt>, Boolean>? {
        val lock = locked
        disputed = false
        if (lock == null) return grid?.let { it.corners to true }
        if (tracked != null) {
            // the board is still where it was: whatever a search found elsewhere was a slip
            missingFrames = 0
            awayFrames = 0
            awayCandidate = null
            return follow(lock, alignTo(tracked.corners, lock).first) to false
        }
        if (grid == null) {
            missingFrames++
            if (missingFrames > framesWithoutGrid) { locked = null; templates.clear(); return null }
            return lock to false
        }
        missingFrames = 0
        val square = squareSize(lock)
        val (aligned, dist) = alignTo(grid.corners, lock)
        disputed = dist > lockTolerance * square
        if (!disputed) {
            awayFrames = 0
            awayCandidate = null
            return follow(lock, aligned) to false
        }
        // A grid elsewhere: counted only while it is the same grid frame after frame.
        val candidate = awayCandidate
        if (candidate != null && alignTo(aligned, candidate).second <= lockTolerance * square) awayFrames++ else { awayCandidate = aligned; awayFrames = 1 }
        if (awayFrames >= framesToRelock) {
            awayFrames = 0
            awayCandidate = null
            disputed = false
            locked = aligned  // in the lock's orientation: the board has not turned
            templates.clear() // the squares are sampled elsewhere now
            return aligned to false
        }
        return lock to false
    }

    /** The lock moved by [lockFollow] of the way towards [target] (in the lock's corner order), which becomes the lock. */
    private fun follow(lock: List<Pt>, target: List<Pt>): List<Pt> {
        val nudged = List(4) { i -> Pt(lock[i].x + lockFollow * (target[i].x - lock[i].x), lock[i].y + lockFollow * (target[i].y - lock[i].y)) }
        locked = nudged
        return nudged
    }

    private fun squareSize(corners: List<Pt>): Double =
        (0 until 4).map { i -> val p = corners[i]; val q = corners[(i + 1) % 4]; hypot(p.x - q.x, p.y - q.y) }.average() / 8

    /** [corners] rotated cyclically to match [reference] best, with the largest corner distance that remains. */
    private fun alignTo(corners: List<Pt>, reference: List<Pt>): Pair<List<Pt>, Double> {
        var bestRot = 0
        var bestDist = Double.MAX_VALUE
        for (rot in 0 until 4) {
            val d = (0 until 4).maxOf { i -> val p = corners[(i + rot) % 4]; hypot(p.x - reference[i].x, p.y - reference[i].y) }
            if (d < bestDist) { bestDist = d; bestRot = rot }
        }
        return List(4) { i -> corners[(i + bestRot) % 4] } to bestDist
    }

    /** The frame as the pieces are read: through the colour shift when one was chosen. */
    private fun view(image: LumaImage): LumaImage {
        val p = projection ?: return image
        val colour = image as? YuvImage ?: return image
        return p.apply(colour)
    }

    private fun learn(image: LumaImage, grid: DetectedGrid): FrameResult {
        val start = Board.start().occupancy()
        var located = BoardLocator.locate(image, grid.corners, Calibration.default(), start, rotation)
        // With colour in the frame, the pieces may stand out better in a channel other than
        // luma: choose it on the first learning frames, from where the pieces are known to be,
        // and read this frame again through it. Until the starting position is actually set up
        // the choice is meaningless, so it is made again on every learning frame.
        if (image is YuvImage) {
            projection = ColorProjection.choose(image, located.geometry, start)
            if (projection != null) located = BoardLocator.locate(view(image), grid.corners, Calibration.default(), start, rotation)
        }
        val f = located.features
        // Does this frame look like the starting position? Occupied ranks must clearly differ from
        // empty ones and white pieces from black ones, before any thresholds exist, by texture or
        // by colour. The weakest pieces (black on dark squares at the far rank) read low on real
        // boards, so allow three weak pieces and two phantom pieces: the fourth-weakest piece must
        // still read clearly above the third-strongest empty square.
        val margins = Calibration.Margins.of(f, start)
        val looksLikeStart = margins.occupancy > 0.08 && margins.colour > 0.2
        val q = quality(
            image, grid, located.geometry,
            listOf(
                ramp(margins.occupancy, 0.0, 0.25) to "Pieces hard to tell from empty squares: more light from above",
                ramp(margins.colour, 0.1, 0.6) to "White and black pieces look alike: more light, or turn the torch on",
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
        locked = located.geometry.corners
        awayFrames = 0
        missingFrames = 0
        templates.clear()
        resetPending()
        val obs = cal.observe(f)
        usualUnsure = obs.count { it.unsure }.toDouble()
        usualCost = MoveInference.cost(board.occupancy(), obs, located.geometry.nearSide)
        return FrameResult(Status.LEARNED, located.geometry, obs, null, 0, emptyList(), "Ready. Play on the board.", quality = q)
    }

    private fun track(image: LumaImage, grid: DetectedGrid?, tracked: DetectedGrid?): FrameResult {
        val cal = calibration ?: return FrameResult(Status.NO_BOARD, null, null, null, 0, emptyList(), "No calibration")
        val (corners, allowRotation) = cornersForFrame(grid, tracked)
            ?: return FrameResult(Status.NO_BOARD, null, null, null, 0, emptyList(), "Looking for the board")
        val located = BoardLocator.locate(view(image), corners, cal, board.occupancy(), rotation, allowRotation, templates)
        if (locked == null) locked = located.geometry.corners
        if (disputed) {
            // the grid finder sees the board elsewhere: until that is settled, this frame counts
            // for nothing, like a hand over the board
            smoothed = null
            return FrameResult(Status.UNSTABLE, located.geometry, located.observations, null, pendingCount, emptyList(), "Hold still, the board moved")
        }
        val raw = located.observations
        val unsure = raw.count { it.unsure }
        if (unsure > maxOf(14.0, usualUnsure + unsureSlack)) {
            // a hand or a shadow over the board: do not count this frame for or against anything
            smoothed = null
            return FrameResult(Status.UNSTABLE, located.geometry, raw, null, pendingCount, emptyList(), "Hold still, hand or shadow over the board")
        }
        val obs = smooth(raw)
        // Squares that changed since the last frame: a hand carrying a piece moves six to ten of
        // them between two frames, a settled board none to two (handheld jitter). A frame with
        // a hand in flight may agree with the frames before, but a move is applied only on a
        // still frame: a queen on its way to d4 read as "e5 d5" for three frames in a row.
        // (Frames in flight must still count towards the agreement: in a fast game the move
        // is confirmed on the first still frame after the hand, and a frame lost there leaves
        // the tracker a move behind.)
        val moving = lastPatches?.let { prev -> ChangeDetector.scores(prev, located.patches).count { it > 0.5 } > maxMovingSquares } ?: false
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
            if (unsettled == 0) {
                noMove?.let { noteQuiet(it.cost); usualCost = 0.9 * usualCost + 0.1 * it.cost }
                // and only settled frames show the empty squares as they are: remember them.
                // Only squares with nothing in front of them: the body of a piece in front would
                // go into the picture, and the square would read as occupied once that piece
                // moved away, which is just when the move needs it read right. And only squares
                // that read empty now: a piece the tracker has not yet seen on a square must not
                // be blended into that square's empty picture, or it would never be seen.
                if (!allowRotation) {
                    val occupancy = board.occupancy()
                    val side = located.geometry.nearSide
                    for (sq in 0 until 64) if (occupancy[sq] == 0 && MoveInference.reliability(occupancy, sq, side) >= 1.0) {
                        val left = vacated[sq]
                        if (left == null && raw[sq].occupied >= 0.2) continue
                        templates.remember(sq, located.patches[sq], located.gradients[sq], located.uPatches?.get(sq), located.vPatches?.get(sq), templateBlend)
                        if (left != null) { if (left <= 1) vacated.remove(sq) else vacated[sq] = left - 1 }
                    }
                }
            }
            // Settled again: the pending evidence is forgotten, but the offers stay until a move
            // is applied. On a still board that flickers, buttons that came and went could not be
            // tapped; the user settles any doubt by tapping or typing, so nothing is taken back.
            if (quiet >= quietFramesToSettle) { pending = emptyList(); pendingCount = 0; unsettled = 0; quiet = 0 }
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
        // Three agreeing frames are required anyway, so a modest per-frame margin is enough.
        // Except between cover twins: two explanations alike but for one destination square
        // and the square behind it in the picture (a queen on f3 seen from a low angle fills g4
        // as well, and occupancy alone cannot tell the two apart); there the best must lead by
        // [twinMargin], or the user settles it.
        // The rival is the first explanation that is not the best one with a further move
        // appended: "b3" against "b3 Ng8", where the second ply is a ghost from a flickering
        // square, is no contest about b3, and waiting for one to lose the frame in which the
        // move could still be confirmed left the tracker behind the game.
        val runnerUp = result.candidates.drop(1).firstOrNull { !extends(it, best) }
        val margin = runnerUp?.let { it.cost - best.cost } ?: Double.POSITIVE_INFINITY
        // Between cover twins the body of a piece on the near square fills the far square, never
        // the other way round. So the far twin (Qg4 against Qf3) is applied only when the near
        // square itself reads empty (a pawn on e4 leaves e3 bare) or the far twin leads by a
        // wide margin; while the near square reads occupied, the piece may well stand there.
        val blockedByTwin = result.candidates.any { c ->
            c !== best && c.cost - best.cost < twinMargin && coverTwins(best, c, located.geometry) && farTwin(best, c, located.geometry) &&
                obs[nearSquare(best, c)].occupied >= 0.5
        }
        if (margin >= applyMargin && !blockedByTwin) {
            if (best.moves == pending) pendingCount++ else {
                pending = best.moves; pendingCount = 1
            }
            // the remembered baseline is from the position before the move: a looser fit
            val base = baseline()
            val fits = base == null || best.cost <= base + applySlack
            if (pendingCount >= framesToConfirm && fits && !moving) {
                val applied = pending
                val before = board
                for (m in applied) board = board.play(m)
                noteVacated(before, board)
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
        val msg = if (margin >= applyMargin && !blockedByTwin) "Seeing ${best.description} ($pendingCount/$framesToConfirm)"
        else "Maybe ${best.description} (%.2f) or ${runnerUp?.description} (%.2f); unchanged %.2f".format(best.cost, runnerUp?.cost ?: 0.0, noMove?.cost ?: 0.0)
        return FrameResult(Status.TRACKING, located.geometry, obs, best, pendingCount, emptyList(), msg, suggestions(), candidates = result.candidates, reading = true)
    }
}
