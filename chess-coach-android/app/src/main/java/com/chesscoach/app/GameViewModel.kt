package com.chesscoach.app

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.chesscoach.core.chess.Board
import com.chesscoach.core.chess.Color
import com.chesscoach.core.chess.GameResult
import com.chesscoach.core.chess.Move
import com.chesscoach.core.engine.EngineInfo
import com.chesscoach.core.vision.BoardLocator
import com.chesscoach.core.vision.Calibration
import com.chesscoach.core.vision.Candidate
import com.chesscoach.core.vision.ChangeDetector
import com.chesscoach.core.vision.GridDetector
import com.chesscoach.core.vision.ImageLine
import com.chesscoach.core.vision.InferenceResult
import com.chesscoach.core.vision.LiveTracker
import com.chesscoach.core.vision.LumaImage
import com.chesscoach.core.vision.MoveInference
import com.chesscoach.core.vision.Pt
import com.chesscoach.core.vision.SquareObservation
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

enum class Phase { SETUP, LIVE, SCAN_START, CONFIRM_START, PICK_CORNERS, PLAYING, SCANNING, CONFIRM_SCAN }

enum class Purpose { START, MOVE }

data class HistoryEntry(val before: Board, val move: Move, val san: String)

data class Suggestion(val lines: List<EngineInfo>, val bestMove: Move?, val bestSan: String?, val done: Boolean)

data class UiState(
    val phase: Phase = Phase.SETUP,
    val myColor: Color = Color.WHITE,
    val thinkSeconds: Float = 2f,
    /** Playing strength for the advice, or null for full strength. */
    val elo: Int? = null,
    val engineStatus: String = "Starting Stockfish...",
    val engineReady: Boolean = false,
    val photo: Photo? = null,
    val corners: List<Pt> = emptyList(),
    val observations: List<SquareObservation>? = null,
    val debugLines: List<ImageLine> = emptyList(),
    val detectionFailed: Boolean = false,
    val cornerPurpose: Purpose = Purpose.START,
    val calibrationNotes: List<String> = emptyList(),
    val calibrationUsable: Boolean = false,
    val busy: Boolean = false,
    val board: Board = Board.start(),
    val history: List<HistoryEntry> = emptyList(),
    val suggestion: Suggestion? = null,
    val thinking: Boolean = false,
    val scanResult: InferenceResult? = null,
    val message: String? = null,
    // live mode
    val liveStatus: String = "Starting camera...",
    val liveFrameWidth: Int = 0,
    val liveFrameHeight: Int = 0,
    val liveCorners: List<Pt> = emptyList(),
    val liveObservations: List<SquareObservation>? = null,
    val liveCandidate: String? = null,
    val livePaused: Boolean = false,
    val liveLearned: Boolean = false,
    val liveFps: Float = 0f,
    val camera: CameraSettings = CameraSettings(),
    val cameras: List<CameraOption> = emptyList(),
    val zoomMin: Float = 1f,
    val zoomMax: Float = 1f,
) {
    val lastMove: Move? get() = history.lastOrNull()?.move
    val myTurn: Boolean get() = board.sideToMove == myColor
    val calibrated: Boolean get() = calibrationNotes.isNotEmpty()

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

    private var calibration: Calibration = Calibration.default()
    private var rotation: Int? = null
    private var previousPatches: Array<IntArray>? = null
    private var pendingPatches: Array<IntArray>? = null
    private var pendingRotation: Int? = null

    private val tracker = LiveTracker(framesToConfirm = 3, framesToLearn = 3)
    @Volatile private var liveBusy = false
    private var lastFrameAt = 0L

    init {
        _state.update {
            it.copy(camera = CameraSettings(cameraId = prefs.getString("cameraId", null), zoom = prefs.getFloat("zoom", 1f)))
        }
        viewModelScope.launch {
            try {
                val threads = Runtime.getRuntime().availableProcessors().coerceIn(1, 4)
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

    fun beginStartScan() = _state.update { it.copy(phase = Phase.SCAN_START, message = null, detectionFailed = false) }

    // ---- live mode ---------------------------------------------------------------------------

    fun startLive() {
        stopAnalysis()
        tracker.restart()
        _state.update {
            it.copy(
                phase = Phase.LIVE, board = Board.start(), history = emptyList(), suggestion = null, message = null,
                liveStatus = "Point the camera at the board", liveLearned = false, livePaused = false, liveCandidate = null,
            )
        }
    }

    fun isLiveBusy(): Boolean = liveBusy || _state.value.livePaused

    fun toggleLivePause() = _state.update { it.copy(livePaused = !it.livePaused) }

    /** Called from the camera thread with an upright grayscale frame. */
    fun onLiveFrame(frame: LumaImage) {
        if (liveBusy || _state.value.phase != Phase.LIVE) return
        liveBusy = true
        val now = System.currentTimeMillis()
        val fps = if (lastFrameAt > 0) 1000f / (now - lastFrameAt).coerceAtLeast(1) else 0f
        lastFrameAt = now
        viewModelScope.launch(Dispatchers.Default) {
            try {
                val r = tracker.process(frame)
                val corners = r.geometry?.corners ?: emptyList()
                _state.update {
                    it.copy(
                        liveStatus = r.message, liveFrameWidth = frame.width, liveFrameHeight = frame.height, liveCorners = corners,
                        liveObservations = r.observations?.toList(), liveCandidate = r.candidate?.takeIf { c -> c.moves.isNotEmpty() }?.description,
                        liveFps = fps,
                    )
                }
                if (r.status == LiveTracker.Status.LEARNED) {
                    withContext(Dispatchers.Main) {
                        stopAnalysis()
                        _state.update { it.copy(board = Board.start(), history = emptyList(), suggestion = null, liveLearned = true, calibrationNotes = tracker.calibration?.notes ?: emptyList()) }
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

    // ---- starting position -------------------------------------------------------------------

    fun onStartPhoto(photo: Photo) = processStart(photo, null)

    private fun processStart(photo: Photo, manualCorners: List<Pt>?) {
        _state.update { it.copy(busy = true, photo = photo) }
        viewModelScope.launch {
            val outcome = withContext(Dispatchers.Default) {
                runCatching {
                    val grid = if (manualCorners == null) GridDetector.detect(photo.luma) else null
                    val corners = manualCorners ?: grid?.corners
                    if (corners == null) return@runCatching null to (grid?.lines ?: emptyList())
                    val located = BoardLocator.locate(
                        photo.luma, corners, Calibration.default(), Board.start().occupancy(), rotation,
                        allowRotation = manualCorners == null,
                    )
                    val cal = Calibration.learn(located.features)
                    Triple(located, cal, cal.observe(located.features)) to (grid?.lines ?: emptyList())
                }
            }
            val (found, lines) = outcome.getOrElse { null to emptyList() }
            if (found == null) {
                _state.update {
                    it.copy(
                        phase = Phase.CONFIRM_START, busy = false, corners = emptyList(), observations = null,
                        debugLines = lines, detectionFailed = true, calibrationNotes = emptyList(),
                        message = outcome.exceptionOrNull()?.let { e -> "Error: ${e.message}" }
                            ?: "Could not find the board. Make sure all four edges are in the picture and try again, or tap the corners yourself.",
                    )
                }
                return@launch
            }
            val (located, cal, obs) = found
            calibration = cal
            pendingPatches = located.patches
            pendingRotation = located.rotation
            _state.update {
                it.copy(
                    phase = Phase.CONFIRM_START, busy = false, corners = located.geometry.corners,
                    observations = obs.toList(), debugLines = emptyList(), detectionFailed = false,
                    calibrationNotes = cal.notes, calibrationUsable = cal.isUsable,
                    message = if (cal.isUsable) null else "Recognition is weak in this light or angle. You can still try.",
                )
            }
        }
    }

    fun acceptStart() {
        previousPatches = pendingPatches
        rotation = pendingRotation
        _state.update {
            it.copy(phase = Phase.PLAYING, board = Board.start(), history = emptyList(), suggestion = null, scanResult = null, message = null)
        }
        maybeAnalyze()
    }

    // ---- manual corners (fallback) -----------------------------------------------------------

    fun pickCornersManually() {
        val purpose = if (_state.value.phase == Phase.CONFIRM_SCAN) Purpose.MOVE else Purpose.START
        _state.update { it.copy(phase = Phase.PICK_CORNERS, corners = emptyList(), observations = null, cornerPurpose = purpose, message = null) }
    }

    fun addCorner(p: Pt) = _state.update { if (it.corners.size < 4) it.copy(corners = it.corners + p) else it }
    fun undoCorner() = _state.update { it.copy(corners = it.corners.dropLast(1)) }

    fun cornersDone() {
        val s = _state.value
        val photo = s.photo ?: return
        if (s.corners.size != 4) return
        when (s.cornerPurpose) {
            Purpose.START -> processStart(photo, s.corners)
            Purpose.MOVE -> processScan(photo, s.corners)
        }
    }

    fun cancelCorners() {
        val target = if (_state.value.cornerPurpose == Purpose.MOVE) Phase.SCANNING else Phase.SCAN_START
        _state.update { it.copy(phase = target, corners = emptyList()) }
    }

    // ---- scanning a move ---------------------------------------------------------------------

    fun startScan() = _state.update { it.copy(phase = Phase.SCANNING, message = null, detectionFailed = false) }
    fun cancelScan() = _state.update { it.copy(phase = Phase.PLAYING, scanResult = null) }

    fun onScanPhoto(photo: Photo) = processScan(photo, null)

    private fun processScan(photo: Photo, manualCorners: List<Pt>?) {
        val board = _state.value.board
        _state.update { it.copy(busy = true, photo = photo) }
        viewModelScope.launch {
            val outcome = withContext(Dispatchers.Default) {
                runCatching {
                    val grid = if (manualCorners == null) GridDetector.detect(photo.luma) else null
                    val corners = manualCorners ?: grid?.corners
                    if (corners == null) return@runCatching null to (grid?.lines ?: emptyList())
                    val located = BoardLocator.locate(
                        photo.luma, corners, calibration, board.occupancy(), rotation,
                        allowRotation = manualCorners == null,
                    )
                    val change = previousPatches?.let { ChangeDetector.scores(it, located.patches) }
                    val result = MoveInference.infer(board, located.observations, change, maxPlies = 2, nearSide = located.geometry.nearSide)
                    Pair(located, result) to (grid?.lines ?: emptyList())
                }
            }
            val (found, lines) = outcome.getOrElse { null to emptyList() }
            if (found == null) {
                _state.update {
                    it.copy(
                        phase = Phase.CONFIRM_SCAN, busy = false, corners = emptyList(), observations = null,
                        debugLines = lines, detectionFailed = true, scanResult = null,
                        message = outcome.exceptionOrNull()?.let { e -> "Error: ${e.message}" }
                            ?: "Could not find the board in this photo. Rescan with all four edges visible, or tap the corners.",
                    )
                }
                return@launch
            }
            val (located, result) = found
            pendingPatches = located.patches
            pendingRotation = located.rotation
            val best = result.best
            val msg = when {
                best == null -> "No legal explanation found."
                best.moves.isEmpty() -> "The board looks unchanged."
                result.margin >= 1.0 -> "Detected ${best.description}."
                else -> "Probably ${best.description}, but not sure. Check the alternatives."
            }
            _state.update {
                it.copy(
                    phase = Phase.CONFIRM_SCAN, busy = false, corners = located.geometry.corners,
                    observations = located.observations.toList(), debugLines = emptyList(), detectionFailed = false,
                    scanResult = result, message = msg,
                )
            }
        }
    }

    fun acceptCandidate(c: Candidate) {
        previousPatches = pendingPatches
        rotation = pendingRotation
        _state.update { it.copy(phase = Phase.PLAYING, scanResult = null, message = null) }
        for (m in c.moves) applyMove(m)
    }

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

    fun enterMove(text: String) {
        val m = _state.value.board.parseMove(text)
        if (m == null) {
            _state.update { it.copy(message = "Could not read \"$text\". Use SAN like Nf3 or UCI like g1f3.") }
        } else {
            previousPatches = null // the last photo no longer matches the position
            applyMove(m)
            tracker.setBoard(_state.value.board)
        }
    }

    fun undo() {
        val s = _state.value
        val last = s.history.lastOrNull() ?: return
        stopAnalysis()
        previousPatches = null
        _state.update { it.copy(board = last.before, history = it.history.dropLast(1), suggestion = null, message = null) }
        tracker.setBoard(last.before)
        maybeAnalyze()
    }

    fun newGame() {
        stopAnalysis()
        previousPatches = null
        if (_state.value.phase == Phase.LIVE) {
            startLive(); return
        }
        _state.update {
            it.copy(
                phase = if (it.calibrated) Phase.PLAYING else Phase.SETUP,
                board = Board.start(), history = emptyList(), suggestion = null, scanResult = null, message = null,
            )
        }
        maybeAnalyze()
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
        if (!s.engineReady || (s.phase != Phase.PLAYING && s.phase != Phase.LIVE)) return
        if (s.phase == Phase.LIVE && !s.liveLearned) return
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
