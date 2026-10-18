package com.chesscoach.app

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.chesscoach.core.chess.Board
import com.chesscoach.core.chess.Color
import com.chesscoach.core.chess.GameResult
import com.chesscoach.core.chess.Move
import com.chesscoach.core.engine.EngineInfo
import com.chesscoach.core.vision.BoardGeometry
import com.chesscoach.core.vision.Calibration
import com.chesscoach.core.vision.Candidate
import com.chesscoach.core.vision.InferenceResult
import com.chesscoach.core.vision.MoveInference
import com.chesscoach.core.vision.Pt
import com.chesscoach.core.vision.SquareObservation
import com.chesscoach.core.vision.SquareSampler
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

enum class Phase { SETUP, CAPTURE_EMPTY, PICK_CORNERS, CAPTURE_START, CALIBRATION_RESULT, PLAYING, SCANNING, CONFIRM_SCAN }

data class HistoryEntry(val before: Board, val move: Move, val san: String)

data class Suggestion(val lines: List<EngineInfo>, val bestMove: Move?, val bestSan: String?, val done: Boolean)

data class UiState(
    val phase: Phase = Phase.SETUP,
    val myColor: Color = Color.WHITE,
    val thinkSeconds: Float = 2f,
    val engineStatus: String = "Starting Stockfish...",
    val engineReady: Boolean = false,
    val photo: Photo? = null,
    val corners: List<Pt> = emptyList(),
    val observations: List<SquareObservation>? = null,
    val calibrationNotes: List<String> = emptyList(),
    val calibrationUsable: Boolean = false,
    val board: Board = Board.start(),
    val history: List<HistoryEntry> = emptyList(),
    val suggestion: Suggestion? = null,
    val thinking: Boolean = false,
    val scanResult: InferenceResult? = null,
    val message: String? = null,
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
    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state

    private val engine = StockfishEngine(app)
    private var analysisJob: Job? = null

    private var emptySamples: Array<IntArray>? = null
    private var geometry: BoardGeometry? = null
    private var calibration: Calibration? = null

    init {
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

    fun beginCalibration() = _state.update { it.copy(phase = Phase.CAPTURE_EMPTY, message = null) }

    fun clearCorners() = _state.update { it.copy(corners = emptyList()) }

    // ---- calibration -------------------------------------------------------------------------

    fun onEmptyPhoto(photo: Photo) {
        val s = _state.value
        if (s.corners.size == 4) {
            _state.update { it.copy(photo = photo) }
            cornersDone()
        } else {
            _state.update { it.copy(photo = photo, corners = emptyList(), observations = null, phase = Phase.PICK_CORNERS) }
        }
    }

    fun addCorner(p: Pt) = _state.update { if (it.corners.size < 4) it.copy(corners = it.corners + p) else it }
    fun undoCorner() = _state.update { it.copy(corners = it.corners.dropLast(1)) }

    fun cornersDone() {
        val s = _state.value
        val photo = s.photo ?: return
        if (s.corners.size != 4) return
        viewModelScope.launch {
            val ok = withContext(Dispatchers.Default) {
                try {
                    val g = BoardGeometry(s.corners)
                    emptySamples = SquareSampler.sample(photo.luma, g)
                    geometry = g
                    true
                } catch (e: IllegalArgumentException) {
                    false
                }
            }
            if (ok) {
                _state.update { it.copy(phase = Phase.CAPTURE_START, message = "Camera side: ${geometry?.nearSide}") }
            } else {
                _state.update { it.copy(corners = emptyList(), message = "Those corners do not form a board. Tap them again.") }
            }
        }
    }

    fun onStartPhoto(photo: Photo) {
        val g = geometry ?: return
        val empty = emptySamples ?: return
        viewModelScope.launch {
            val (cal, obs) = withContext(Dispatchers.Default) {
                val start = SquareSampler.sample(photo.luma, g)
                val cal = Calibration.learn(empty, start)
                cal to cal.observe(start).toList()
            }
            calibration = cal
            _state.update {
                it.copy(
                    phase = Phase.CALIBRATION_RESULT,
                    photo = photo,
                    observations = obs,
                    calibrationNotes = cal.notes,
                    calibrationUsable = cal.isUsable,
                )
            }
        }
    }

    fun retakeStart() = _state.update { it.copy(phase = Phase.CAPTURE_START) }

    fun acceptCalibration() {
        _state.update { it.copy(phase = Phase.PLAYING, board = Board.start(), history = emptyList(), suggestion = null, scanResult = null, message = null) }
        maybeAnalyze()
    }

    fun recalibrate() {
        stopAnalysis()
        _state.update { it.copy(phase = Phase.CAPTURE_EMPTY, message = "Keep the phone where it is if only the lighting changed; pick corners again if it moved.") }
    }

    // ---- scanning ----------------------------------------------------------------------------

    fun startScan() = _state.update { it.copy(phase = Phase.SCANNING, message = null) }
    fun cancelScan() = _state.update { it.copy(phase = Phase.PLAYING, scanResult = null) }

    fun onScanPhoto(photo: Photo) {
        val g = geometry ?: return
        val cal = calibration ?: return
        val board = _state.value.board
        viewModelScope.launch {
            val (obs, result) = withContext(Dispatchers.Default) {
                val obs = cal.observe(SquareSampler.sample(photo.luma, g))
                obs.toList() to MoveInference.infer(board, obs, maxPlies = 2)
            }
            val best = result.best
            val msg = when {
                best == null -> "No legal explanation found."
                best.moves.isEmpty() -> "The board looks unchanged."
                result.margin >= 1.0 -> "Detected ${best.description}."
                else -> "Probably ${best.description}, but not sure. Check the alternatives."
            }
            _state.update { it.copy(phase = Phase.CONFIRM_SCAN, photo = photo, observations = obs, scanResult = result, message = msg) }
        }
    }

    fun acceptCandidate(c: Candidate) {
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
            applyMove(m)
        }
    }

    fun undo() {
        val s = _state.value
        val last = s.history.lastOrNull() ?: return
        stopAnalysis()
        _state.update { it.copy(board = last.before, history = it.history.dropLast(1), suggestion = null, message = null) }
        maybeAnalyze()
    }

    fun newGame() {
        stopAnalysis()
        _state.update {
            it.copy(
                phase = if (it.calibrated) Phase.PLAYING else Phase.SETUP,
                board = Board.start(), history = emptyList(), suggestion = null, scanResult = null, message = null,
            )
        }
        maybeAnalyze()
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
        if (!s.engineReady || s.phase != Phase.PLAYING && s.phase != Phase.CONFIRM_SCAN) return
        if (!s.myTurn || s.board.result() != GameResult.ONGOING) return
        val board = s.board
        val fen = board.toFen()
        _state.update { it.copy(thinking = true, suggestion = null) }
        analysisJob = viewModelScope.launch {
            try {
                val result = engine.analyze(fen, (s.thinkSeconds * 1000).toInt()) { lines ->
                    _state.update { it.copy(suggestion = toSuggestion(board, lines, done = false)) }
                }
                val lines = result.lines
                val best = result.bestMove?.let { Move.fromUci(it) }
                val suggestion = toSuggestion(board, lines, done = true).let { sug ->
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
