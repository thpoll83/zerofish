package com.chesscoach.app

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.chesscoach.core.chess.Board
import com.chesscoach.core.chess.Color
import com.chesscoach.core.chess.GameResult
import com.chesscoach.core.chess.Move
import com.chesscoach.core.engine.EngineInfo
import com.chesscoach.core.vision.Candidate
import com.chesscoach.core.vision.LiveTracker
import com.chesscoach.core.vision.LumaImage
import com.chesscoach.core.vision.Pt
import com.chesscoach.core.vision.SquareObservation
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.concurrent.Executors

enum class Phase { SETUP, LIVE }

/** What the square viewport shows while playing: the camera picture or the digital board. */
enum class ViewMode { CAMERA, BOARD }

data class HistoryEntry(val before: Board, val move: Move, val san: String)

data class Suggestion(val lines: List<EngineInfo>, val bestMove: Move?, val bestSan: String?, val done: Boolean)

data class UiState(
    /** The app opens on the live view; the setup screen is reached from its button. */
    val phase: Phase = Phase.LIVE,
    val myColor: Color = Color.WHITE,
    val thinkSeconds: Float = 2f,
    /** Playing strength for the advice, or null for full strength. */
    val elo: Int? = null,
    val engineStatus: String = "Starting Stockfish...",
    val engineReady: Boolean = false,
    val board: Board = Board.start(),
    val history: List<HistoryEntry> = emptyList(),
    val suggestion: Suggestion? = null,
    val thinking: Boolean = false,
    val message: String? = null,
    val viewMode: ViewMode = ViewMode.CAMERA,
    /** Draw what the camera read on every square (dots and rings) during the game too. */
    val showDebugOverlay: Boolean = false,
    // live mode
    val liveStatus: String = "Point the camera at the board",
    val liveFrameWidth: Int = 0,
    val liveFrameHeight: Int = 0,
    val liveCorners: List<Pt> = emptyList(),
    val liveObservations: List<SquareObservation>? = null,
    val liveCandidate: String? = null,
    val livePaused: Boolean = false,
    val liveLearned: Boolean = false,
    val liveFps: Float = 0f,
    /** The board changed and the tracker is still working out which move was played. */
    val liveReading: Boolean = false,
    /** How well the view will work, 0 to 1, and what is weakest about it; judged before the game starts. */
    val liveQuality: Double? = null,
    val liveHint: String? = null,
    /** Offered when the camera cannot decide which move was played. */
    val liveSuggestions: List<Candidate> = emptyList(),
    /** Destination squares tapped so far to pick one of [liveSuggestions]. */
    val pickPath: List<Int> = emptyList(),
    val camera: CameraSettings = CameraSettings(),
    val cameras: List<CameraOption> = emptyList(),
    val zoomMin: Float = 1f,
    val zoomMax: Float = 1f,
) {
    val lastMove: Move? get() = history.lastOrNull()?.move
    val myTurn: Boolean get() = board.sideToMove == myColor

    /** The offered moves still compatible with the squares tapped so far. */
    val openChoices: List<Candidate>
        get() = liveSuggestions.filter { c -> pickPath.indices.all { i -> i < c.moves.size && c.moves[i].to == pickPath[i] } }

    fun moveListText(): String {
        val sb = StringBuilder()
        history.forEachIndexed { i, h ->
            if (i % 2 == 0) sb.append(i / 2 + 1).append(". ")
            sb.append(h.san).append(' ')
        }
        return sb.toString().trim()
    }
}

class GameViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("chesscoach", android.content.Context.MODE_PRIVATE)
    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state

    private val engine = StockfishEngine(app)
    private var analysisJob: Job? = null

    /** Not thread-safe: the camera thread and the UI thread both touch it under `synchronized(tracker)`. */
    private val tracker = LiveTracker(framesToConfirm = 3, framesToLearn = 3)
    @Volatile private var liveBusy = false
    private var lastFrameAt = 0L

    /**
     * The tracker runs one frame at a time on its own thread, below normal priority: the camera
     * preview and the screen come first, and a frame read a little later costs nothing.
     */
    private val trackerDispatcher = Executors.newSingleThreadExecutor { r ->
        Thread(r, "tracker").apply { priority = Thread.NORM_PRIORITY - 2; isDaemon = true }
    }.asCoroutineDispatcher()

    init {
        _state.update {
            it.copy(
                camera = CameraSettings(cameraId = prefs.getString("cameraId", null), zoom = prefs.getFloat("zoom", 1f)),
                showDebugOverlay = prefs.getBoolean("debugOverlay", false),
            )
        }
        viewModelScope.launch {
            try {
                // Leave two cores to the camera, the tracker and the screen: Stockfish on every core made the
                // preview stutter while it was thinking.
                val threads = (Runtime.getRuntime().availableProcessors() - 2).coerceIn(1, 4)
                engine.start(threads)
                _state.update { it.copy(engineReady = true, engineStatus = engine.version.ifBlank { "Stockfish ready" }) }
                maybeAnalyze()
            } catch (e: Exception) {
                _state.update { it.copy(engineStatus = "Engine failed to start: ${e.message}") }
            }
        }
    }

    // ---- setup -------------------------------------------------------------------------------

    fun setMyColor(c: Color) = _state.update { it.copy(myColor = c) }
    fun setThinkSeconds(s: Float) = _state.update { it.copy(thinkSeconds = s) }
    fun setElo(elo: Int?) = _state.update { it.copy(elo = elo?.coerceIn(StockfishEngine.MIN_ELO, StockfishEngine.MAX_ELO)) }

    // ---- live mode ---------------------------------------------------------------------------

    fun startLive() {
        stopAnalysis()
        synchronized(tracker) { tracker.restart() }
        _state.update {
            it.copy(
                phase = Phase.LIVE, board = Board.start(), history = emptyList(), suggestion = null, message = null,
                liveStatus = "Point the camera at the board", liveLearned = false, livePaused = false, liveCandidate = null,
                liveSuggestions = emptyList(), pickPath = emptyList(), viewMode = ViewMode.CAMERA, liveQuality = null, liveHint = null,
            )
        }
    }

    /** Back from the settings to the game in progress, without touching the tracker. */
    fun resumeLive() {
        _state.update { it.copy(phase = Phase.LIVE, message = null) }
        maybeAnalyze()
    }

    fun setViewMode(mode: ViewMode) = _state.update { it.copy(viewMode = mode) }

    fun setDebugOverlay(on: Boolean) {
        _state.update { it.copy(showDebugOverlay = on) }
        prefs.edit().putBoolean("debugOverlay", on).apply()
    }

    /** The user says all pieces stand on their starting squares: learn from the next frames regardless. */
    fun confirmStart() {
        synchronized(tracker) { tracker.confirmStart() }
        _state.update { it.copy(liveStatus = "Learning your pieces from the starting position...") }
    }

    fun isLiveBusy(): Boolean = liveBusy || _state.value.livePaused

    /** The user tapped one of the offered explanations. */
    fun acceptLiveCandidate(c: Candidate) {
        // The offer may be older than the position (the tracker applied a move in between): a
        // sequence that is not playable from the current position is dropped, not applied.
        var b = _state.value.board
        for (m in c.moves) {
            if (!b.isLegal(m)) {
                _state.update { it.copy(liveSuggestions = emptyList(), pickPath = emptyList(), message = "${c.description} is no longer possible here.") }
                return
            }
            b = b.play(m)
        }
        synchronized(tracker) { if (tracker.board == _state.value.board) tracker.accept(c) else tracker.setBoard(b) }
        _state.update { it.copy(liveSuggestions = emptyList(), pickPath = emptyList(), liveCandidate = null) }
        for (m in c.moves) applyMove(m)
    }

    /**
     * A tap on a square of the board or the camera picture while moves are offered: it picks the
     * offered move whose piece went to that square. When several offered sequences start the
     * same way, the tap narrows them down and the next tap picks among their second moves.
     */
    fun pickSquare(square: Int) {
        val s = _state.value
        if (s.liveSuggestions.isEmpty()) return
        val path = s.pickPath + square
        val matching = s.liveSuggestions.filter { c -> path.indices.all { i -> i < c.moves.size && c.moves[i].to == path[i] } }
        val exact = matching.firstOrNull { it.moves.size == path.size }
        when {
            matching.isEmpty() -> _state.update { it.copy(pickPath = emptyList()) }
            matching.size == 1 -> acceptLiveCandidate(matching[0])
            exact != null -> acceptLiveCandidate(exact)
            else -> _state.update { it.copy(pickPath = path) }
        }
    }

    fun toggleLivePause() = _state.update { it.copy(livePaused = !it.livePaused) }

    /** Called from the camera thread with an upright grayscale frame. */
    fun onLiveFrame(frame: LumaImage) {
        if (liveBusy || _state.value.phase != Phase.LIVE) return
        liveBusy = true
        val now = System.currentTimeMillis()
        val fps = if (lastFrameAt > 0) 1000f / (now - lastFrameAt).coerceAtLeast(1) else 0f
        lastFrameAt = now
        viewModelScope.launch(trackerDispatcher) {
            try {
                val r = synchronized(tracker) { tracker.process(frame) }
                val corners = r.geometry?.corners ?: emptyList()
                _state.update {
                    // a hand over the board or a lost grid must not take the offered moves away
                    val keep = r.status == LiveTracker.Status.UNSTABLE || r.status == LiveTracker.Status.NO_BOARD
                    val offers = if (keep) it.liveSuggestions else r.suggestions
                    it.copy(
                        liveStatus = r.message, liveFrameWidth = frame.width, liveFrameHeight = frame.height, liveCorners = corners,
                        liveObservations = r.observations?.toList(), liveCandidate = r.candidate?.takeIf { c -> c.moves.isNotEmpty() }?.description,
                        liveFps = fps,
                        liveReading = r.reading,
                        liveQuality = r.quality?.score ?: it.liveQuality,
                        liveHint = r.quality?.hint ?: it.liveHint,
                        liveSuggestions = offers,
                        pickPath = if (offers == it.liveSuggestions) it.pickPath else emptyList(),
                    )
                }
                if (r.status == LiveTracker.Status.LEARNED) {
                    withContext(Dispatchers.Main) {
                        stopAnalysis()
                        _state.update { it.copy(board = Board.start(), history = emptyList(), suggestion = null, liveLearned = true) }
                        maybeAnalyze()
                    }
                }
                if (r.applied.isNotEmpty()) {
                    withContext(Dispatchers.Main) { for (m in r.applied) applyMove(m) }
                }
            } catch (e: Exception) {
                _state.update { it.copy(liveStatus = "Error: ${e.message}") }
            } finally {
                liveBusy = false
            }
        }
    }

    override fun onCleared() {
        trackerDispatcher.close()
        super.onCleared()
    }

    // ---- camera settings ---------------------------------------------------------------------

    fun onCamerasAvailable(options: List<CameraOption>, zoomMin: Float, zoomMax: Float) {
        _state.update { it.copy(cameras = options, zoomMin = zoomMin, zoomMax = zoomMax) }
    }

    fun setZoom(z: Float) {
        _state.update { it.copy(camera = it.camera.copy(zoom = z)) }
        prefs.edit().putFloat("zoom", z).apply()
    }

    fun setCameraId(id: String?) {
        _state.update { it.copy(camera = it.camera.copy(cameraId = id)) }
        prefs.edit().putString("cameraId", id).apply()
    }

    fun setTorch(on: Boolean) = _state.update { it.copy(camera = it.camera.copy(torch = on)) }

    // ---- game --------------------------------------------------------------------------------

    fun applyMove(move: Move) {
        val s = _state.value
        if (!s.board.isLegal(move)) {
            _state.update { it.copy(message = "${move.uci()} is not legal here.") }
            return
        }
        stopAnalysis()
        val san = s.board.san(move)
        val next = s.board.play(move)
        _state.update {
            it.copy(board = next, history = it.history + HistoryEntry(s.board, move, san), suggestion = null, message = resultMessage(next))
        }
        maybeAnalyze()
    }

    fun playSuggestion() {
        _state.value.suggestion?.bestMove?.let { applyMove(it) }
    }

    /** Applies one or more typed moves ("Nf3", "g1f3", or a sequence like "Nc6 Qg4 Bb4+"). */
    fun enterMove(text: String) {
        val tokens = text.trim().split(Regex("\\s+")).filter { it.isNotBlank() && !it.matches(Regex("\\d+\\.+")) }
        val moves = ArrayList<Move>()
        var b = _state.value.board
        for (t in tokens) {
            val m = b.parseMove(t)
            if (m == null) {
                _state.update { it.copy(message = "Could not read \"$t\". Use SAN like Nf3 or UCI like g1f3; several moves may be separated by spaces.") }
                return
            }
            moves += m
            b = b.play(m)
        }
        if (moves.isEmpty()) return
        for (m in moves) applyMove(m)
        _state.update { it.copy(liveSuggestions = emptyList(), pickPath = emptyList()) }
        synchronized(tracker) { tracker.setBoard(_state.value.board) }
    }

    fun undo() {
        val s = _state.value
        val last = s.history.lastOrNull() ?: return
        stopAnalysis()
        _state.update { it.copy(board = last.before, history = it.history.dropLast(1), suggestion = null, message = null, liveSuggestions = emptyList(), pickPath = emptyList()) }
        synchronized(tracker) { tracker.setBoard(last.before) }
        maybeAnalyze()
    }

    fun newGame() {
        stopAnalysis()
        startLive()
    }

    fun backToSetup() {
        stopAnalysis()
        _state.update { it.copy(phase = Phase.SETUP, message = null) }
    }

    fun clearMessage() = _state.update { it.copy(message = null) }

    private fun resultMessage(b: Board): String? = when (b.result()) {
        GameResult.WHITE_WINS -> "Checkmate, White wins."
        GameResult.BLACK_WINS -> "Checkmate, Black wins."
        GameResult.DRAW -> "Draw."
        GameResult.ONGOING -> if (b.inCheck()) "Check!" else null
    }

    // ---- engine ------------------------------------------------------------------------------

    private fun stopAnalysis() {
        analysisJob?.cancel()
        analysisJob = null
        engine.stop()
        _state.update { it.copy(thinking = false) }
    }

    private fun maybeAnalyze() {
        val s = _state.value
        if (!s.engineReady || s.phase != Phase.LIVE || !s.liveLearned) return
        if (!s.myTurn || s.board.result() != GameResult.ONGOING) return
        val board = s.board
        val fen = board.toFen()
        _state.update { it.copy(thinking = true, suggestion = null) }
        analysisJob = viewModelScope.launch {
            try {
                val result = engine.analyze(fen, (s.thinkSeconds * 1000).toInt(), s.elo) { lines ->
                    _state.update { it.copy(suggestion = toSuggestion(board, lines, done = false)) }
                }
                val best = result.bestMove?.let { Move.fromUci(it) }
                val suggestion = toSuggestion(board, result.lines, done = true).let { sug ->
                    if (best != null && board.isLegal(best)) sug.copy(bestMove = best, bestSan = board.san(best)) else sug
                }
                _state.update { if (it.board == board) it.copy(suggestion = suggestion, thinking = false) else it }
            } catch (e: CancellationException) {
                // a move was played while the engine was thinking: the search was stopped on purpose
                throw e
            } catch (e: Exception) {
                _state.update { it.copy(thinking = false, message = "Engine error: ${e.message}") }
            }
        }
    }

    private fun toSuggestion(board: Board, lines: List<EngineInfo>, done: Boolean): Suggestion {
        val first = lines.firstOrNull()?.pv?.firstOrNull()?.let { Move.fromUci(it) }
        val legal = first?.takeIf { board.isLegal(it) }
        return Suggestion(lines, legal, legal?.let { board.san(it) }, done)
    }

    /** SAN for the first move of a PV line, for display. */
    fun sanOf(board: Board, uci: String): String {
        val m = Move.fromUci(uci) ?: return uci
        return if (board.isLegal(m)) board.san(m) else uci
    }
}
