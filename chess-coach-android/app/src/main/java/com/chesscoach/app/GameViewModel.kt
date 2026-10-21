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
import com.chesscoach.core.vision.YuvImage
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
    /** Keep a log of the tracker's decisions with the frames behind them, for a shareable bundle. */
    val debugLog: Boolean = true,
    val debugSummary: String = "",
    /** Chesscog's occupancy network: in this build, switched on, reading every square each frame, and how it runs. */
    val cnnAvailable: Boolean = false,
    val cnnOn: Boolean = true,
    val cnnEverySquare: Boolean = false,
    val cnnInfo: String = "Loading the square classifier...",
    /** Squares the network read on the last frame and how long it took, for the status line. */
    val liveCnn: String = "",
    /** The depth benchmark: running, its progress or results, and the depth map it read. */
    val depthBenchRunning: Boolean = false,
    val depthBench: String = "",
    val depthPreview: android.graphics.Bitmap? = null,
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
    /** Offered while a move is being read; the tracker only appends to this list, so the buttons stay put. */
    val liveSuggestions: List<Candidate> = emptyList(),
    /** The tracker has given up reading the move by itself and asks for a tap. */
    val liveAsking: Boolean = false,
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

    /** The decisions and the frames behind them; see [DebugRecorder]. */
    private val recorder = DebugRecorder(app)

    /**
     * Chesscog's occupancy network, once loaded from the app's assets; null when not in this
     * build. Declared before the init block that starts loading it, so its initialiser cannot
     * run after the load.
     */
    @Volatile private var squareClassifier: ChesscogClassifier? = null
    private var frameNo = 0
    @Volatile private var lastFrame: YuvImage? = null
    private var lastOfferCount = 0
    private var wasAsking = false

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
                debugLog = prefs.getBoolean("debugLog", true),
                cnnOn = prefs.getBoolean("cnnOn", true),
                cnnEverySquare = prefs.getBoolean("cnnEverySquare", false),
            )
        }
        loadSquareClassifier()
        recorder.enabled = _state.value.debugLog
        recorder.log("APP started")
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

    fun setDebugLog(on: Boolean) {
        recorder.enabled = on
        _state.update { it.copy(debugLog = on) }
        prefs.edit().putBoolean("debugLog", on).apply()
        if (on) recorder.log("LOG on")
    }

    fun refreshDebugSummary() = _state.update { it.copy(debugSummary = recorder.summary()) }

    /** Zips the log and its frames for sharing; call off the main thread. */
    fun buildDebugBundle(): java.io.File {
        recorder.log("BUNDLE shared; game so far: ${_state.value.moveListText()}")
        return recorder.bundle()
    }

    fun clearDebugLog() {
        recorder.clear()
        recorder.log("LOG cleared")
        refreshDebugSummary()
    }

    private fun loadSquareClassifier() {
        viewModelScope.launch(Dispatchers.Default) {
            try {
                val bytes = getApplication<Application>().assets.open(ChesscogClassifier.ASSET).use { it.readBytes() }
                val t0 = System.currentTimeMillis()
                val cls = ChesscogClassifier(bytes)
                squareClassifier = cls
                _state.update { it.copy(cnnAvailable = true, cnnInfo = "Chesscog occupancy network, ${cls.provider}, loaded in ${System.currentTimeMillis() - t0} ms") }
                recorder.log("CNN loaded: ${cls.provider}")
                applySquareClassifier()
            } catch (e: java.io.FileNotFoundException) {
                _state.update { it.copy(cnnAvailable = false, cnnInfo = "Not included in this build: the squares are read from brightness and colour.") }
            } catch (e: Throwable) {
                recorder.log("CNN failed to load: ${e.message}")
                _state.update { it.copy(cnnAvailable = false, cnnInfo = "Could not load the square classifier: ${e.message}") }
            }
        }
    }

    private fun applySquareClassifier() {
        val s = _state.value
        synchronized(tracker) {
            tracker.squareClassifier = if (s.cnnOn) squareClassifier else null
            tracker.classifyEverySquare = s.cnnEverySquare
        }
    }

    fun setCnnOn(on: Boolean) {
        _state.update { it.copy(cnnOn = on) }
        prefs.edit().putBoolean("cnnOn", on).apply()
        recorder.log("CNN " + if (on) "on" else "off")
        applySquareClassifier()
    }

    fun setCnnEverySquare(on: Boolean) {
        _state.update { it.copy(cnnEverySquare = on) }
        prefs.edit().putBoolean("cnnEverySquare", on).apply()
        recorder.log("CNN every square " + if (on) "on" else "off")
        applySquareClassifier()
    }

    private val depthBenchmark by lazy { DepthBenchmark(java.io.File(getApplication<Application>().filesDir, "depth/depth_anything_v2_vits.onnx")) }

    /**
     * Times the depth model on the last camera frame on the CPU and on each accelerator, after
     * downloading the model once; the results go to the screen and the debug log, the depth map
     * and the frame into the debug bundle.
     */
    fun runDepthBenchmark() {
        if (_state.value.depthBenchRunning) return
        val frame = lastFrame
        if (frame == null) {
            _state.update { it.copy(depthBench = "No camera frame yet. Go back to the board for a moment so the camera sees it, then try again.") }
            return
        }
        val corners = _state.value.liveCorners
        _state.update { it.copy(depthBenchRunning = true, depthBench = "Starting", depthPreview = null) }
        viewModelScope.launch(Dispatchers.Default) {
            try {
                if (!depthBenchmark.modelReady()) {
                    depthBenchmark.download { mb -> _state.update { it.copy(depthBench = "Downloading the depth model: %.0f of 99 MB".format(mb)) } }
                }
                val prepared = depthBenchmark.prepare(frame, corners)
                val configs = depthBenchmark.configs()
                val (results, depth) = depthBenchmark.run(prepared, configs) { p -> _state.update { it.copy(depthBench = p) } }
                // Chesscog's network on all 64 squares of the same frame, as on the first still frame after a move
                val cnnResults = if (corners.size == 4) {
                    try {
                        val modelFile = java.io.File(getApplication<Application>().cacheDir, ChesscogClassifier.ASSET)
                        if (!modelFile.exists()) getApplication<Application>().assets.open(ChesscogClassifier.ASSET).use { input -> modelFile.outputStream().use { input.copyTo(it) } }
                        val t0 = System.nanoTime()
                        val crops = com.chesscoach.core.vision.ChesscogCrops.crop(frame, com.chesscoach.core.vision.BoardGeometry(corners), IntArray(64) { it })
                        val cropMs = (System.nanoTime() - t0) / 1_000_000
                        val shape = longArrayOf(64, 3, com.chesscoach.core.vision.ChesscogCrops.SIZE.toLong(), com.chesscoach.core.vision.ChesscogCrops.SIZE.toLong())
                        val (res, _) = depthBenchmark.time(modelFile.path, crops, shape, configs) { p -> _state.update { it.copy(depthBench = "Chesscog, 64 squares: $p") } }
                        listOf("Chesscog occupancy network, all 64 squares (crops made in $cropMs ms):") + res.map { "  $it" }
                    } catch (e: java.io.FileNotFoundException) {
                        listOf("Chesscog occupancy network: not in this build")
                    } catch (e: Throwable) {
                        listOf("Chesscog occupancy network: failed, ${e.message}")
                    }
                } else listOf("Chesscog occupancy network: needs the board found in the frame")
                val soc = if (android.os.Build.VERSION.SDK_INT >= 31) ", ${android.os.Build.SOC_MANUFACTURER} ${android.os.Build.SOC_MODEL}" else ""
                val text = buildString {
                    append("${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}$soc, ${Runtime.getRuntime().availableProcessors()} cores\n")
                    append("Frame ${frame.width}x${frame.height}, " + (if (corners.size == 4) "board region ${prepared.cropW}x${prepared.cropH}" else "no board found, whole frame") + ", prepared in ${prepared.millis} ms\n")
                    append("Depth Anything V2 Small:\n")
                    for (r in results) append("  ").append(r.toString()).append('\n')
                    for (line in cnnResults) append(line).append('\n')
                }.trimEnd()
                val bitmap = depth?.let { d ->
                    val p = depthBenchmark.preview(prepared, d)
                    android.graphics.Bitmap.createBitmap(p.argb, p.width, p.height, android.graphics.Bitmap.Config.ARGB_8888)
                }
                recorder.log("DEPTH BENCH " + text.replace("\n", " | "))
                recorder.frame(frameNo, "depthbench", frame)
                bitmap?.let { b ->
                    val out = java.io.ByteArrayOutputStream()
                    b.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, out)
                    recorder.file("f%05d_depth.png".format(frameNo), out.toByteArray())
                }
                _state.update { it.copy(depthBenchRunning = false, depthBench = text, depthPreview = bitmap) }
            } catch (e: Throwable) {
                recorder.log("DEPTH BENCH failed: ${e.message}")
                _state.update { it.copy(depthBenchRunning = false, depthBench = "Depth benchmark failed: ${e.message}") }
            }
        }
    }

    /** A user action worth a line and the frame it was taken on. */
    private fun note(tag: String, line: String) {
        recorder.log("$line | board ${_state.value.board.toFen()}")
        lastFrame?.let { recorder.frame(frameNo, tag, it) }
    }

    /** The user says all pieces stand on their starting squares: learn from the next frames regardless. */
    fun confirmStart() {
        note("confirm", "CONFIRM START by the user")
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
        note("tap", "TAP ${c.description} (%.1f) of ${_state.value.liveSuggestions.joinToString(" | ") { "${it.description} (%.1f)".format(it.cost) }}".format(c.cost))
        synchronized(tracker) { if (tracker.board == _state.value.board) tracker.accept(c) else tracker.setBoard(b) }
        _state.update { it.copy(liveSuggestions = emptyList(), pickPath = emptyList(), liveCandidate = null, liveAsking = false) }
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
                var cnnSquares = 0
                var cnnMs = 0L
                var cnnError: String? = null
                val r = synchronized(tracker) {
                    tracker.process(frame).also { cnnSquares = tracker.lastClassified; cnnMs = tracker.lastClassifyMs; cnnError = tracker.lastClassifyError }
                }
                val cnnText = when {
                    cnnError != null -> "network error: $cnnError"
                    cnnSquares > 0 -> "network $cnnSquares squares $cnnMs ms"
                    else -> ""
                }
                val corners = r.geometry?.corners ?: emptyList()
                (frame as? YuvImage)?.let { lastFrame = it }
                record(frame, r, corners, cnnText)
                _state.update {
                    // a hand over the board or a lost grid must not take the offered moves away
                    val keep = r.status == LiveTracker.Status.UNSTABLE || r.status == LiveTracker.Status.NO_BOARD
                    val offers = if (keep) it.liveSuggestions else r.suggestions
                    it.copy(
                        liveStatus = r.message, liveFrameWidth = frame.width, liveFrameHeight = frame.height, liveCorners = corners,
                        liveObservations = r.observations?.toList(), liveCandidate = r.candidate?.takeIf { c -> c.moves.isNotEmpty() }?.description,
                        liveFps = fps,
                        liveCnn = cnnText,
                        liveReading = r.reading,
                        liveQuality = r.quality?.score ?: it.liveQuality,
                        liveHint = r.quality?.hint ?: it.liveHint,
                        liveSuggestions = offers,
                        liveAsking = if (keep) it.liveAsking else r.status == LiveTracker.Status.AMBIGUOUS,
                        // the list only grows while the same move is read; a tap path survives that
                        pickPath = if (offers.size >= it.liveSuggestions.size && offers.take(it.liveSuggestions.size) == it.liveSuggestions) it.pickPath else emptyList(),
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

    /**
     * One log line per frame in the replay harness's format, and the frame itself whenever
     * something was decided: the pieces learned, a move applied, a question asked, an offer
     * added, the grid moved; plus every twentieth frame as a sample of the quiet times.
     */
    private fun record(frame: LumaImage, r: LiveTracker.FrameResult, corners: List<Pt>, cnn: String = "") {
        frameNo++
        if (!_state.value.debugLog) return
        val tag = when {
            r.status == LiveTracker.Status.LEARNED -> "learned"
            r.status == LiveTracker.Status.MOVE_PLAYED -> "played"
            r.status == LiveTracker.Status.AMBIGUOUS && !wasAsking -> "asked"
            r.suggestions.size > lastOfferCount -> "offer"
            r.status == LiveTracker.Status.UNSTABLE && r.message.contains("moved") -> "moved"
            frameNo % 20 == 0 -> "sample"
            else -> null
        }
        wasAsking = r.status == LiveTracker.Status.AMBIGUOUS
        lastOfferCount = r.suggestions.size
        val saved = if (tag != null) (frame as? YuvImage)?.let { recorder.frame(frameNo, tag, it) } else null
        val sb = StringBuilder("f%05d %s %s".format(frameNo, r.status, r.message))
        r.quality?.let { sb.append(" [quality %.2f: %s]".format(it.score, it.hint)) }
        if (r.status == LiveTracker.Status.LEARNED) {
            synchronized(tracker) { sb.append(" [colour shift: ${tracker.projection ?: "none, plain luma"}; ${tracker.calibration?.notes?.joinToString(" | ")}]") }
        }
        if (r.candidates.isNotEmpty()) sb.append(" | top: ").append(r.candidates.take(4).joinToString(" | ") { "${it.description} (%.2f)".format(it.cost) })
        if (r.suggestions.isNotEmpty()) sb.append(" | offers: ").append(r.suggestions.joinToString(" | ") { "${it.description} (%.1f)".format(it.cost) })
        r.observations?.let { obs -> sb.append(" | unsure ${obs.count { it.unsure }}") }
        if (cnn.isNotEmpty()) sb.append(" | ").append(cnn)
        if (corners.size == 4) sb.append(" | grid ").append(corners.joinToString(" ") { "%.0f,%.0f".format(it.x, it.y) })
        if (saved != null) sb.append(" | image $saved")
        recorder.log(sb.toString())
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

    /** Applies one or more typed moves ("Nf3", "g1f3", or a sequence like "Nc6 Qf3 Bb4+"). */
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
        note("typed", "TYPED ${text.trim()} while offered ${_state.value.liveSuggestions.joinToString(" | ") { it.description }}")
        for (m in moves) applyMove(m)
        _state.update { it.copy(liveSuggestions = emptyList(), pickPath = emptyList()) }
        synchronized(tracker) { tracker.setBoard(_state.value.board) }
    }

    fun undo() {
        val s = _state.value
        val last = s.history.lastOrNull() ?: return
        note("undo", "UNDO ${last.san}")
        stopAnalysis()
        _state.update { it.copy(board = last.before, history = it.history.dropLast(1), suggestion = null, message = null, liveSuggestions = emptyList(), pickPath = emptyList()) }
        synchronized(tracker) { tracker.setBoard(last.before) }
        maybeAnalyze()
    }

    fun newGame() {
        recorder.log("NEW GAME by the user; game so far: ${_state.value.moveListText()}")
        stopAnalysis()
        startLive()
    }

    fun backToSetup() {
        stopAnalysis()
        _state.update { it.copy(phase = Phase.SETUP, message = null, debugSummary = recorder.summary()) }
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
