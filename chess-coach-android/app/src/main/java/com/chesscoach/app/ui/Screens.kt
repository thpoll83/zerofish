package com.chesscoach.app.ui

import android.content.Intent
import androidx.core.content.FileProvider
import androidx.compose.ui.platform.LocalContext
import androidx.compose.runtime.rememberCoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.chesscoach.app.GameViewModel
import com.chesscoach.app.LiveCameraView
import com.chesscoach.app.Phase
import com.chesscoach.app.StockfishEngine
import com.chesscoach.app.UiState
import com.chesscoach.app.ViewMode
import com.chesscoach.core.chess.Color
import com.chesscoach.core.chess.GameResult

/**
 * SAN with piece symbols instead of letters, for the compact move buttons: "Nf3" becomes "♘f3"
 * for White and "♞f3" for Black.
 */
private fun figurine(san: String, white: Boolean): String {
    val symbols = if (white) "KQRBN" to "♔♕♖♗♘" else "KQRBN" to "♚♛♜♝♞"
    val sb = StringBuilder()
    for ((i, ch) in san.withIndex()) {
        val k = symbols.first.indexOf(ch)
        // a piece letter at the start, or after "=" in a promotion
        sb.append(if (k >= 0 && (i == 0 || san[i - 1] == '=')) symbols.second[k] else ch)
    }
    return sb.toString()
}

/** The moves of an offered explanation as figurines, alternating colours from the side to move. */
private fun figurines(c: com.chesscoach.core.vision.Candidate, whiteFirst: Boolean): String =
    c.sans.mapIndexed { i, san -> figurine(san, if (i % 2 == 0) whiteFirst else !whiteFirst) }.joinToString(" ")

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ChessCoachApp(vm: GameViewModel) {
    val state by vm.state.collectAsState()
    Column(Modifier.fillMaxSize().navigationBarsPadding()) {
        when (state.phase) {
            Phase.SETUP -> {
                AppHeader("Settings")
                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) { SetupScreen(state, vm) }
            }
            Phase.LIVE -> LiveScreen(state, vm)
        }
    }
}

@Composable
private fun SetupScreen(state: UiState, vm: GameViewModel) {
    Text(state.engineStatus, style = MaterialTheme.typography.bodySmall)
    Spacer(Modifier.height(16.dp))
    Text("I play as", fontWeight = FontWeight.Bold)
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        FilterChip(selected = state.myColor == Color.WHITE, onClick = { vm.setMyColor(Color.WHITE) }, label = { Text("White") })
        FilterChip(selected = state.myColor == Color.BLACK, onClick = { vm.setMyColor(Color.BLACK) }, label = { Text("Black") })
    }
    Spacer(Modifier.height(16.dp))
    Text("Thinking time: %.1f s per move".format(state.thinkSeconds), fontWeight = FontWeight.Bold)
    Slider(value = state.thinkSeconds, onValueChange = { vm.setThinkSeconds(it) }, valueRange = 0.5f..10f)
    Spacer(Modifier.height(16.dp))
    Text("Strength of the advice", fontWeight = FontWeight.Bold)
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        FilterChip(selected = state.elo == null, onClick = { vm.setElo(null) }, label = { Text("Full strength") })
        FilterChip(selected = state.elo != null, onClick = { vm.setElo(state.elo ?: 1800) }, label = { Text("Limited Elo") })
    }
    state.elo?.let { elo ->
        Text("About $elo Elo. Stockfish then plays like a player of that rating, mistakes included.", style = MaterialTheme.typography.bodySmall)
        Slider(
            value = elo.toFloat(),
            onValueChange = { vm.setElo((it / 10).toInt() * 10) },
            valueRange = StockfishEngine.MIN_ELO.toFloat()..StockfishEngine.MAX_ELO.toFloat(),
        )
    }
    Spacer(Modifier.height(16.dp))
    Row(verticalAlignment = Alignment.CenterVertically) {
        Switch(checked = state.showDebugOverlay, onCheckedChange = { vm.setDebugOverlay(it) })
        Spacer(Modifier.width(12.dp))
        Column {
            Text("Show recognition markers during the game", fontWeight = FontWeight.Bold)
            Text("A dot per square with what the camera read (white, black, empty) and a yellow ring where it is unsure. Always shown until the pieces are learned.", style = MaterialTheme.typography.bodySmall)
        }
    }
    Spacer(Modifier.height(16.dp))
    Row(verticalAlignment = Alignment.CenterVertically) {
        Switch(checked = state.debugLog, onCheckedChange = { vm.setDebugLog(it) })
        Spacer(Modifier.width(12.dp))
        Column {
            Text("Debug log", fontWeight = FontWeight.Bold)
            Text(
                "Records what the camera read and decided, with the frame behind each decision (" + state.debugSummary.ifBlank { "empty" } + "). " +
                    "Share the bundle to have a problem looked at. The frames show your board and whatever is around it.",
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 6.dp)) {
        OutlinedButton(onClick = {
            scope.launch {
                val zip = withContext(Dispatchers.IO) { vm.buildDebugBundle() }
                val uri = FileProvider.getUriForFile(context, context.packageName + ".fileprovider", zip)
                val send = Intent(Intent.ACTION_SEND).apply {
                    type = "application/zip"
                    putExtra(Intent.EXTRA_STREAM, uri)
                    putExtra(Intent.EXTRA_SUBJECT, zip.name)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }
                context.startActivity(Intent.createChooser(send, "Share the debug bundle"))
            }
        }) { Text("Share debug bundle") }
        OutlinedButton(onClick = { vm.clearDebugLog() }) { Text("Clear") }
    }
    Spacer(Modifier.height(16.dp))
    Text("Square reader (experiment)", fontWeight = FontWeight.Bold)
    Text(state.cnnInfo, style = MaterialTheme.typography.bodySmall)
    if (state.cnnAvailable) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 6.dp)) {
            Switch(checked = state.cnnOn, onCheckedChange = { vm.setCnnOn(it) })
            Spacer(Modifier.width(12.dp))
            Column {
                Text("A neural network decides which squares hold a piece", fontWeight = FontWeight.Bold)
                Text(
                    "Chesscog's occupancy network, trained on rendered boards from many angles. Brightness and colour still tell " +
                        "white from black. On the test videos it followed every move by itself where the old reading needed taps.",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 6.dp)) {
            Switch(checked = state.cnnEverySquare, enabled = state.cnnOn, onCheckedChange = { vm.setCnnEverySquare(it) })
            Spacer(Modifier.width(12.dp))
            Column {
                Text("Read every square on every frame", fontWeight = FontWeight.Bold)
                Text(
                    "Off: only squares that changed are read again, plus a few in turn, and the whole board once the hand has left. " +
                        "On: about four times the work, slightly better on the videos. With the recognition markers on, the status line shows the time per frame.",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
    Spacer(Modifier.height(16.dp))
    Text("Depth benchmark", fontWeight = FontWeight.Bold)
    Text(
        "An experiment: times a depth model (Depth Anything V2 Small), and the square classifier on all 64 squares, on the last camera frame, on the processor and on the phone's " +
            "accelerators, to see whether it could read the board on every frame. The model, 99 MB, is downloaded once from GitHub. " +
            "Takes one to three minutes; the results also go into the debug log.",
        style = MaterialTheme.typography.bodySmall,
    )
    OutlinedButton(onClick = { vm.runDepthBenchmark() }, enabled = !state.depthBenchRunning, modifier = Modifier.padding(top = 6.dp)) {
        Text(if (state.depthBenchRunning) "Running..." else "Run depth benchmark")
    }
    if (state.depthBench.isNotBlank()) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 4.dp)) {
            if (state.depthBenchRunning) {
                CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                Spacer(Modifier.width(8.dp))
            }
            Text(state.depthBench, style = MaterialTheme.typography.bodySmall)
        }
    }
    state.depthPreview?.let { bmp ->
        Image(
            bitmap = bmp.asImageBitmap(),
            contentDescription = "Depth map of the last camera frame, nearer is brighter",
            modifier = Modifier.fillMaxWidth().aspectRatio(bmp.width.toFloat() / bmp.height).padding(top = 6.dp),
        )
    }
    Spacer(Modifier.height(24.dp))
    Button(onClick = { vm.resumeLive() }, modifier = Modifier.fillMaxWidth()) { Text("Back to the board") }
    Spacer(Modifier.height(8.dp))
    OutlinedButton(onClick = { vm.startLive() }, modifier = Modifier.fillMaxWidth()) { Text("New game") }
    Spacer(Modifier.height(8.dp))
    Text(
        "Set up the starting position and point the camera at the board, or put the phone on a stand. " +
            "The app learns your pieces from the first frames and then follows every move by itself.",
        style = MaterialTheme.typography.bodySmall,
    )
    state.message?.let { Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 8.dp)) }
}

/**
 * The playing screen: the headline with the state, a row of controls, a square viewport (camera
 * picture or digital board, by the toggle), and below it the status, the engine's advice and a
 * row of buttons. Nothing needs scrolling on a phone screen; the lower part scrolls only on a
 * very short one.
 */
@Composable
private fun LiveScreen(state: UiState, vm: GameViewModel) {
    var showEntry by remember { mutableStateOf(false) }
    var entry by remember { mutableStateOf("") }
    // The phone watches the game for minutes without a touch: the screen must not go dark.
    val view = LocalView.current
    DisposableEffect(view) {
        view.keepScreenOn = true
        onDispose { view.keepScreenOn = false }
    }
    val result = state.board.result()
    val flipped = state.myColor == Color.BLACK
    val choices = state.openChoices
    val nextPly = state.pickPath.size
    // One numbered arrow per offered move (its next move, when the first taps narrowed the
    // sequences); otherwise the engine's suggestion.
    val choiceArrows = choices.mapIndexedNotNull { i, c ->
        c.moves.getOrNull(nextPly)?.let { m -> MoveArrow(m.from, m.to, ArrowColors.choice(i), "${i + 1}") }
    }.distinctBy { it.from to it.to }
    // Otherwise the move just played stays on the picture as confirmation, with the engine's
    // suggestion next to it when it is the user's turn.
    val arrows = if (choiceArrows.isNotEmpty()) choiceArrows else listOfNotNull(
        state.lastMove?.let { MoveArrow(it.from, it.to, ArrowColors.lastMove) },
        state.suggestion?.bestMove?.takeIf { state.myTurn && result == GameResult.ONGOING }?.let { MoveArrow(it.from, it.to, ArrowColors.suggestion) },
    )
    val headline = when {
        !state.liveLearned -> state.liveStatus
        result != GameResult.ONGOING -> "Game over"
        state.myTurn -> "Your move: ${sideName(state)}"
        else -> "Opponent's move: ${sideName(state)}"
    }
    AppHeader(headline)
    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp, vertical = 6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth().padding(bottom = 6.dp)) {
            FilterChip(selected = state.viewMode == ViewMode.CAMERA, onClick = { vm.setViewMode(ViewMode.CAMERA) }, label = { Text("Camera") })
            Spacer(Modifier.width(6.dp))
            FilterChip(selected = state.viewMode == ViewMode.BOARD, onClick = { vm.setViewMode(ViewMode.BOARD) }, enabled = state.liveLearned, label = { Text("Board") })
            Spacer(Modifier.weight(1f))
            FilterChip(selected = state.camera.torch, onClick = { vm.setTorch(!state.camera.torch) }, label = { Text("Torch") })
            Spacer(Modifier.width(6.dp))
            TextButton(onClick = { vm.toggleLivePause() }, contentPadding = PaddingValues(horizontal = 6.dp)) { Text(if (state.livePaused) "Resume" else "Pause") }
        }
        // Before the game starts, the frame around the picture says how well this view will
        // work, red to green, with the score as a percentage: light, distance and zoom can be
        // adjusted until it is green.
        val quality = state.liveQuality?.takeIf { !state.liveLearned }
        val qualityColor = quality?.let { q ->
            if (q < 0.5) lerp(Palette.error, Palette.warn, (q / 0.5).toFloat()) else lerp(Palette.warn, Palette.accent, ((q - 0.5) / 0.5).toFloat())
        }
        Box(Modifier.fillMaxWidth().aspectRatio(1f).then(if (qualityColor != null) Modifier.border(4.dp, qualityColor) else Modifier)) {
            // The camera stays bound while the digital board is shown on top of it: the tracker
            // keeps following the game either way.
            LiveCameraView(
                settings = state.camera,
                corners = state.liveCorners,
                // the per-square markers are for setting up; during the game they only distract
                observations = state.liveObservations?.takeIf { !state.liveLearned || state.showDebugOverlay },
                frameWidth = state.liveFrameWidth,
                frameHeight = state.liveFrameHeight,
                isBusy = { vm.isLiveBusy() },
                onCameras = { options, zMin, zMax -> vm.onCamerasAvailable(options, zMin, zMax) },
                onFrame = { vm.onLiveFrame(it) },
                arrows = arrows,
                onSquareTap = { vm.pickSquare(it) },
                modifier = Modifier.fillMaxSize(),
            )
            if (state.viewMode == ViewMode.BOARD && state.liveLearned) {
                BoardView(
                    board = state.board, flipped = flipped, lastMove = state.lastMove, arrows = arrows,
                    onSquareTap = { vm.pickSquare(it) }, modifier = Modifier.fillMaxSize(),
                )
            }
            if (quality != null && qualityColor != null) {
                Text(
                    "%d%%".format((quality * 100).toInt()), color = qualityColor, fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(10.dp).background(Palette.header.copy(alpha = 0.7f), RoundedCornerShape(6.dp)).padding(horizontal = 8.dp, vertical = 2.dp),
                )
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            Text("Zoom", style = MaterialTheme.typography.bodySmall)
            Slider(
                value = state.camera.zoom.coerceIn(state.zoomMin, maxOf(state.zoomMax, state.zoomMin + 0.01f)),
                onValueChange = { vm.setZoom(it) },
                valueRange = state.zoomMin..maxOf(minOf(state.zoomMax, 4f), state.zoomMin + 0.01f),
                modifier = Modifier.weight(1f).padding(horizontal = 8.dp),
            )
            Text("%.1fx".format(state.camera.zoom), style = MaterialTheme.typography.bodySmall)
        }
        if (state.cameras.size > 1 && !state.liveLearned) {
            // the lens can be chosen before the pieces are learned; a change afterwards would
            // need them learned again
            Row(Modifier.horizontalScroll(rememberScrollState()).padding(bottom = 4.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                FilterChip(selected = state.camera.cameraId == null, onClick = { vm.setCameraId(null) }, label = { Text("Default lens") })
                state.cameras.forEachIndexed { i, c ->
                    val name = if (i == 0) "Widest (%.1f mm)".format(c.focalMm) else c.label
                    FilterChip(selected = state.camera.cameraId == c.id, onClick = { vm.setCameraId(c.id) }, label = { Text(name) })
                }
            }
        }
        if (state.liveLearned) {
            // The moves of the game in one row that scrolls sideways, the latest highlighted and
            // in view; it sits right under the picture, outside the scrolling part, so nothing
            // below can push it off the screen.
            val scroll = rememberScrollState()
            LaunchedEffect(state.history.size) { scroll.animateScrollTo(scroll.maxValue) }
            Row(
                Modifier.fillMaxWidth().horizontalScroll(scroll).padding(vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.CenterVertically,
            ) {
                if (state.history.isEmpty()) Text("No moves yet", style = MaterialTheme.typography.bodySmall, color = Palette.textDim)
                state.history.forEachIndexed { i, h ->
                    if (i % 2 == 0) Text("${i / 2 + 1}.", style = MaterialTheme.typography.bodySmall, color = Palette.textDim)
                    val last = i == state.history.size - 1
                    Text(
                        figurine(h.san, i % 2 == 0),
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (last) Palette.onAccent else Palette.text,
                        modifier = (if (last) Modifier.background(Palette.accent, RoundedCornerShape(4.dp)) else Modifier).padding(horizontal = 6.dp, vertical = 2.dp),
                    )
                }
            }
        }
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(top = 4.dp)) {
            // The move buttons come first, right under the moves, so that the status text (one
            // line or two) cannot push them about; they are compact rectangles framed in the
            // colour of their arrow, in as many rows as needed.
            if (choices.isNotEmpty()) {
                val whiteFirst = state.board.sideToMove == Color.WHITE
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    choices.forEachIndexed { i, c ->
                        Text(
                            figurines(c, whiteFirst),
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier
                                .border(2.dp, ArrowColors.choice(i), RoundedCornerShape(4.dp))
                                .clickable { vm.acceptLiveCandidate(c) }
                                .padding(horizontal = 10.dp, vertical = 6.dp),
                        )
                    }
                    Text(
                        "Other",
                        style = MaterialTheme.typography.bodyMedium, color = Palette.accentText,
                        modifier = Modifier.border(2.dp, Palette.cardLine, RoundedCornerShape(4.dp)).clickable { showEntry = true }.padding(horizontal = 10.dp, vertical = 6.dp),
                    )
                }
                Text(
                    when {
                        nextPly > 0 -> "And then? Tap the next square or move."
                        state.liveAsking -> "Not sure what was played: tap the move, or the square the piece went to."
                        else -> "Reading the move; tap it if you know it."
                    },
                    style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 2.dp),
                )
            }
            if (!state.liveLearned && state.liveCorners.size == 4) {
                // The app recognises the starting position by itself when the pieces read clearly.
                // When they do not (black pieces on dark squares of a glossy board), the user says
                // so, and the pieces are learned from where they are known to stand.
                Button(onClick = { vm.confirmStart() }, modifier = Modifier.fillMaxWidth().padding(top = 4.dp)) { Text("Pieces are set up (starting position)") }
            }
            Advice(state, vm)
            val status = if (state.liveLearned) state.liveStatus else
                (state.liveHint?.let { "$it. " } ?: "") + "Green grid: the board as found. Dots: pieces as read. Yellow ring: unsure square."
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (state.liveReading && choices.isEmpty()) {
                    // a move is being read: a spinner instead of buttons that would vanish again
                    CircularProgressIndicator(modifier = Modifier.size(14.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                }
                Text(
                    status + (state.liveCandidate?.let { "  seeing $it" } ?: "") + (if (state.showDebugOverlay && state.liveFps > 0) "  (%.1f fps)".format(state.liveFps) else "") +
                        (if (state.showDebugOverlay && state.liveCnn.isNotEmpty()) "  ${state.liveCnn}" else ""),
                    style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis,
                )
            }
            state.message?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
            Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth().padding(top = 2.dp)) {
                TextButton(onClick = { showEntry = true }, enabled = state.liveLearned && result == GameResult.ONGOING, contentPadding = PaddingValues(horizontal = 6.dp)) { Text("Type move") }
                TextButton(onClick = { vm.undo() }, enabled = state.history.isNotEmpty(), contentPadding = PaddingValues(horizontal = 6.dp)) { Text("Undo") }
                TextButton(onClick = { vm.newGame() }, contentPadding = PaddingValues(horizontal = 6.dp)) { Text("New game") }
                TextButton(onClick = { vm.backToSetup() }, contentPadding = PaddingValues(horizontal = 6.dp)) { Text("Settings") }
            }
        }
    }
    if (showEntry) {
        AlertDialog(
            onDismissRequest = { showEntry = false },
            title = { Text("Enter the move played") },
            text = { OutlinedTextField(value = entry, onValueChange = { entry = it }, label = { Text("e.g. Nf3, g1f3, or several: Nc6 Qf3 Bb4+") }, singleLine = true) },
            confirmButton = { TextButton(onClick = { vm.enterMove(entry); entry = ""; showEntry = false }) { Text("Apply") } },
            dismissButton = { TextButton(onClick = { showEntry = false }) { Text("Cancel") } },
        )
    }
}

private fun sideName(state: UiState) = if (state.board.sideToMove == Color.WHITE) "White" else "Black"

/** The engine's advice in two lines: the move to play, and the alternatives it considered. */
@Composable
private fun Advice(state: UiState, vm: GameViewModel) {
    if (!state.liveLearned || !state.myTurn || state.board.result() != GameResult.ONGOING) return
    val sug = state.suggestion
    if (sug == null || sug.lines.isEmpty()) {
        Text(if (state.thinking) "Stockfish is thinking..." else if (state.engineReady) "No suggestion yet." else state.engineStatus, modifier = Modifier.padding(top = 4.dp))
        return
    }
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 4.dp)) {
        Text("Play ${sug.bestSan ?: "?"}", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.width(12.dp))
        Text(sug.lines.first().scoreText() + (if (sug.done) "" else "  thinking..."), style = MaterialTheme.typography.bodyMedium)
    }
    val others = sug.lines.drop(1).joinToString("   ") { line ->
        val first = line.pv.firstOrNull()?.let { vm.sanOf(state.board, it) } ?: "?"
        "$first ${line.scoreText()}"
    }
    if (others.isNotEmpty()) Text("Also: $others", style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
}
