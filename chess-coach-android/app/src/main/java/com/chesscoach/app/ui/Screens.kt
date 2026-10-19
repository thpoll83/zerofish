package com.chesscoach.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
    var showCamera by remember { mutableStateOf(false) }
    val result = state.board.result()
    val flipped = state.myColor == Color.BLACK
    val choices = state.openChoices
    val nextPly = state.pickPath.size
    // One numbered arrow per offered move (its next move, when the first taps narrowed the
    // sequences); otherwise the engine's suggestion.
    val choiceArrows = choices.mapIndexedNotNull { i, c ->
        c.moves.getOrNull(nextPly)?.let { m -> MoveArrow(m.from, m.to, ArrowColors.choice(i), "${i + 1}") }
    }.distinctBy { it.from to it.to }
    val arrows = if (choiceArrows.isNotEmpty()) choiceArrows else listOfNotNull(
        state.suggestion?.bestMove?.takeIf { state.myTurn && result == GameResult.ONGOING }?.let { MoveArrow(it.from, it.to, ArrowColors.suggestion) },
    )
    val headline = when {
        !state.liveLearned -> state.liveStatus
        result != GameResult.ONGOING -> "Game over"
        state.myTurn -> "Your move"
        else -> "Opponent's move"
    }
    AppHeader(headline)
    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp, vertical = 6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth().padding(bottom = 6.dp)) {
            FilterChip(selected = state.viewMode == ViewMode.CAMERA, onClick = { vm.setViewMode(ViewMode.CAMERA) }, label = { Text("Camera") })
            Spacer(Modifier.width(6.dp))
            FilterChip(selected = state.viewMode == ViewMode.BOARD, onClick = { vm.setViewMode(ViewMode.BOARD) }, enabled = state.liveLearned, label = { Text("Board") })
            Spacer(Modifier.weight(1f))
            TextButton(onClick = { showCamera = true }, contentPadding = PaddingValues(horizontal = 6.dp)) { Text("Zoom %.1fx".format(state.camera.zoom)) }
            TextButton(onClick = { vm.toggleLivePause() }, contentPadding = PaddingValues(horizontal = 6.dp)) { Text(if (state.livePaused) "Resume" else "Pause") }
        }
        Box(Modifier.fillMaxWidth().aspectRatio(1f)) {
            // The camera stays bound while the digital board is shown on top of it: the tracker
            // keeps following the game either way.
            LiveCameraView(
                settings = state.camera,
                corners = state.liveCorners,
                observations = state.liveObservations,
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
        }
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(top = 6.dp)) {
            val status = if (state.liveLearned) state.liveStatus else
                "Green grid: the board as found. White and black dots: pieces as read. Yellow ring: unsure square."
            Text(
                status + (state.liveCandidate?.let { "  seeing $it" } ?: "") + (if (state.liveFps > 0) "  (%.1f fps)".format(state.liveFps) else ""),
                style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis,
            )
            state.message?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
            if (choices.isNotEmpty()) {
                Text(
                    if (nextPly == 0) "Not sure what was played. Tap the square the piece went to, or a move:" else "And then? Tap the next square:",
                    style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 4.dp),
                )
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                    choices.forEachIndexed { i, c ->
                        OutlinedButton(onClick = { vm.acceptLiveCandidate(c) }, contentPadding = PaddingValues(horizontal = 10.dp, vertical = 2.dp)) {
                            Box(Modifier.size(10.dp).background(ArrowColors.choice(i), CircleShape))
                            Spacer(Modifier.width(6.dp))
                            Text("${i + 1} ${c.description}")
                        }
                    }
                    TextButton(onClick = { showEntry = true }, contentPadding = PaddingValues(horizontal = 6.dp)) { Text("Other") }
                }
            }
            Advice(state, vm)
            Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth().padding(top = 2.dp)) {
                TextButton(onClick = { showEntry = true }, enabled = state.liveLearned && result == GameResult.ONGOING, contentPadding = PaddingValues(horizontal = 6.dp)) { Text("Type move") }
                TextButton(onClick = { vm.undo() }, enabled = state.history.isNotEmpty(), contentPadding = PaddingValues(horizontal = 6.dp)) { Text("Undo") }
                TextButton(onClick = { vm.newGame() }, contentPadding = PaddingValues(horizontal = 6.dp)) { Text("New game") }
                TextButton(onClick = { vm.backToSetup() }, contentPadding = PaddingValues(horizontal = 6.dp)) { Text("Settings") }
            }
            if (state.history.isNotEmpty()) {
                Text(state.moveListText(), style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
            }
        }
    }
    if (showEntry) {
        AlertDialog(
            onDismissRequest = { showEntry = false },
            title = { Text("Enter the move played") },
            text = { OutlinedTextField(value = entry, onValueChange = { entry = it }, label = { Text("e.g. Nf3, g1f3, or several: Nc6 Qg4 Bb4+") }, singleLine = true) },
            confirmButton = { TextButton(onClick = { vm.enterMove(entry); entry = ""; showEntry = false }) { Text("Apply") } },
            dismissButton = { TextButton(onClick = { showEntry = false }) { Text("Cancel") } },
        )
    }
    if (showCamera) {
        AlertDialog(
            onDismissRequest = { showCamera = false },
            title = { Text("Camera") },
            text = {
                Column {
                    Text("Zoom %.1fx (below 1x switches to the wide-angle lens on phones that have one)".format(state.camera.zoom), style = MaterialTheme.typography.bodySmall)
                    Slider(
                        value = state.camera.zoom.coerceIn(state.zoomMin, maxOf(state.zoomMax, state.zoomMin + 0.01f)),
                        onValueChange = { vm.setZoom(it) },
                        valueRange = state.zoomMin..maxOf(minOf(state.zoomMax, 4f), state.zoomMin + 0.01f),
                    )
                    if (state.cameras.size > 1) {
                        Text("Lens", style = MaterialTheme.typography.bodySmall)
                        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            FilterChip(selected = state.camera.cameraId == null, onClick = { vm.setCameraId(null) }, label = { Text("Default") })
                            state.cameras.forEachIndexed { i, c ->
                                val name = if (i == 0) "Widest (%.1f mm)".format(c.focalMm) else c.label
                                FilterChip(selected = state.camera.cameraId == c.id, onClick = { vm.setCameraId(c.id) }, label = { Text(name) })
                            }
                        }
                    }
                    FilterChip(selected = state.camera.torch, onClick = { vm.setTorch(!state.camera.torch) }, label = { Text("Torch") })
                }
            },
            confirmButton = { TextButton(onClick = { showCamera = false }) { Text("Done") } },
        )
    }
}

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
