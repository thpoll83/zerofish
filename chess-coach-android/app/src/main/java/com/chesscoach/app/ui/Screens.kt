package com.chesscoach.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.ui.unit.dp
import com.chesscoach.app.CameraCapture
import com.chesscoach.app.GameViewModel
import com.chesscoach.app.Phase
import com.chesscoach.app.Purpose
import com.chesscoach.app.StockfishEngine
import com.chesscoach.app.UiState
import com.chesscoach.core.chess.Color
import com.chesscoach.core.chess.GameResult

@Composable
fun ChessCoachApp(vm: GameViewModel) {
    val state by vm.state.collectAsState()
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
        when (state.phase) {
            Phase.SETUP -> SetupScreen(state, vm)
            Phase.SCAN_START -> ScanStartScreen(state, vm)
            Phase.CONFIRM_START -> ConfirmStartScreen(state, vm)
            Phase.PICK_CORNERS -> PickCornersScreen(state, vm)
            Phase.PLAYING -> GameScreen(state, vm)
            Phase.SCANNING -> ScanningScreen(state, vm)
            Phase.CONFIRM_SCAN -> ConfirmScanScreen(state, vm)
        }
    }
}

@Composable
private fun Title(text: String) {
    Text(text, style = MaterialTheme.typography.headlineSmall, modifier = Modifier.padding(bottom = 8.dp))
}

@Composable
private fun Message(state: UiState) {
    state.message?.let {
        Card(Modifier.fillMaxWidth().padding(vertical = 8.dp)) { Text(it, Modifier.padding(12.dp)) }
    }
}

@Composable
private fun Busy(state: UiState) {
    if (state.busy) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(8.dp)) {
            CircularProgressIndicator(Modifier.padding(end = 12.dp))
            Text("Looking for the board...")
        }
    }
}

@Composable
private fun Legend() {
    Text(
        "Green grid: where the board was found. White and black dots: squares read as white or black pieces. " +
            "Small green dots: empty. Yellow rings: unsure.",
        style = MaterialTheme.typography.bodySmall,
    )
}

@Composable
private fun SetupScreen(state: UiState, vm: GameViewModel) {
    Title("Chess Coach")
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
    Text(
        "Set up the pieces for a new game and photograph the whole board, from above or from your seat. " +
            "The app finds the board by itself. After each of your opponent's moves, tap Scan and take another photo; " +
            "the phone does not need to stay in place.",
    )
    Spacer(Modifier.height(16.dp))
    Button(onClick = { vm.beginStartScan() }, modifier = Modifier.fillMaxWidth()) { Text("Scan the starting position") }
    if (state.calibrated) {
        TextButton(onClick = { vm.newGame() }) { Text("Continue with the current game") }
    }
    Message(state)
}

@Composable
private fun ScanStartScreen(state: UiState, vm: GameViewModel) {
    Title("Starting position")
    Text("All 32 pieces on their starting squares. Keep all four edges of the board in the picture and avoid hands or shadows over it.")
    Busy(state)
    CameraCapture(buttonLabel = "Photograph the board", enabled = !state.busy, onPhoto = { vm.onStartPhoto(it) })
    TextButton(onClick = { vm.backToSetup() }) { Text("Back") }
}

@Composable
private fun ConfirmStartScreen(state: UiState, vm: GameViewModel) {
    Title(if (state.detectionFailed) "Board not found" else "Check recognition")
    Message(state)
    if (!state.detectionFailed) Legend()
    state.photo?.let { PhotoOverlay(it, state.corners, state.observations, debugLines = state.debugLines) }
    Spacer(Modifier.height(8.dp))
    for (note in state.calibrationNotes) Text(note, style = MaterialTheme.typography.bodySmall)
    Spacer(Modifier.height(8.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        if (!state.detectionFailed) {
            Button(onClick = { vm.acceptStart() }) { Text(if (state.calibrationUsable) "Start game" else "Use anyway") }
        }
        OutlinedButton(onClick = { vm.beginStartScan() }) { Text("Rescan") }
        TextButton(onClick = { vm.pickCornersManually() }) { Text("Tap corners") }
    }
    if (state.detectionFailed) {
        Text("The red and orange lines show what the detector saw. If the board is in the picture, tap its four corners by hand.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun PickCornersScreen(state: UiState, vm: GameViewModel) {
    val names = listOf("a1 (White's left corner)", "h1 (White's right corner)", "h8 (Black's left corner)", "a8 (Black's right corner)")
    Title("Tap the corners")
    val n = state.corners.size
    Text(if (n < 4) "Tap corner ${n + 1} of 4: ${names[n]}" else "Check that the green grid sits on the squares.")
    Message(state)
    Busy(state)
    state.photo?.let { PhotoOverlay(it, state.corners, onTap = { p -> vm.addCorner(p) }) }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
        OutlinedButton(onClick = { vm.undoCorner() }, enabled = n > 0) { Text("Undo") }
        Button(onClick = { vm.cornersDone() }, enabled = n == 4 && !state.busy) {
            Text(if (state.cornerPurpose == Purpose.START) "Learn pieces" else "Read move")
        }
        TextButton(onClick = { vm.cancelCorners() }) { Text("Retake photo") }
    }
}

@Composable
private fun GameScreen(state: UiState, vm: GameViewModel) {
    var showEntry by remember { mutableStateOf(false) }
    var entry by remember { mutableStateOf("") }
    val result = state.board.result()
    val turnText = when {
        result != GameResult.ONGOING -> "Game over"
        state.myTurn -> "Your move"
        else -> "Your son's move. Tap Scan when he has played."
    }
    Text(turnText, style = MaterialTheme.typography.titleMedium)
    Message(state)
    BoardView(
        board = state.board,
        flipped = state.myColor == Color.BLACK,
        lastMove = state.lastMove,
        arrow = state.suggestion?.bestMove,
        modifier = Modifier.padding(vertical = 8.dp),
    )
    if (state.myTurn && result == GameResult.ONGOING) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp)) {
                val sug = state.suggestion
                if (sug == null || sug.lines.isEmpty()) {
                    Text(if (state.thinking) "Stockfish is thinking..." else if (state.engineReady) "No suggestion yet." else state.engineStatus)
                } else {
                    Text("Play ${sug.bestSan ?: "?"}", style = MaterialTheme.typography.headlineSmall)
                    sug.lines.forEachIndexed { i, line ->
                        val first = line.pv.firstOrNull()?.let { vm.sanOf(state.board, it) } ?: "?"
                        Text("${i + 1}. $first  ${line.scoreText()}  depth ${line.depth ?: "?"}", style = MaterialTheme.typography.bodySmall)
                    }
                    if (!sug.done) Text("still thinking...", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
    Spacer(Modifier.height(8.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(onClick = { vm.startScan() }, enabled = result == GameResult.ONGOING) { Text("Scan board") }
        state.suggestion?.bestSan?.let { san ->
            if (state.myTurn) Button(onClick = { vm.playSuggestion() }) { Text("I played $san") }
        }
    }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
        OutlinedButton(onClick = { showEntry = true }, enabled = result == GameResult.ONGOING) { Text("Type move") }
        OutlinedButton(onClick = { vm.undo() }, enabled = state.history.isNotEmpty()) { Text("Undo") }
        TextButton(onClick = { vm.newGame() }) { Text("New game") }
    }
    TextButton(onClick = { vm.backToSetup() }) { Text("Settings") }
    Text(state.moveListText(), style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 8.dp))

    if (showEntry) {
        AlertDialog(
            onDismissRequest = { showEntry = false },
            title = { Text("Enter the move played") },
            text = {
                OutlinedTextField(value = entry, onValueChange = { entry = it }, label = { Text("e.g. Nf3, exd5, O-O or g1f3") }, singleLine = true)
            },
            confirmButton = {
                TextButton(onClick = {
                    vm.enterMove(entry)
                    entry = ""
                    showEntry = false
                }) { Text("Apply") }
            },
            dismissButton = { TextButton(onClick = { showEntry = false }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun ScanningScreen(state: UiState, vm: GameViewModel) {
    Title("Scan the board")
    Text("Whole board in the picture, no hands over it. Any angle is fine.")
    Busy(state)
    CameraCapture(buttonLabel = "Scan", enabled = !state.busy, onPhoto = { vm.onScanPhoto(it) })
    TextButton(onClick = { vm.cancelScan() }) { Text("Cancel") }
}

@Composable
private fun ConfirmScanScreen(state: UiState, vm: GameViewModel) {
    val result = state.scanResult
    Title(if (state.detectionFailed) "Board not found" else "What was played?")
    Message(state)
    if (!state.detectionFailed) Legend()
    state.photo?.let { PhotoOverlay(it, state.corners, state.observations, debugLines = state.debugLines) }
    Spacer(Modifier.height(8.dp))
    val candidates = result?.candidates?.take(5).orEmpty()
    val best = candidates.firstOrNull()
    if (best != null && best.moves.isNotEmpty()) {
        var b = state.board
        for (m in best.moves) b = b.play(m)
        Text("Board after ${best.description}, with what the camera saw on each square:", style = MaterialTheme.typography.bodySmall)
        BoardView(board = b, flipped = state.myColor == Color.BLACK, lastMove = best.moves.last(), marks = state.observations)
    }
    Spacer(Modifier.height(8.dp))
    for ((i, c) in candidates.withIndex()) {
        val label = if (c.moves.isEmpty()) "Nothing was played" else c.description
        val content: @Composable () -> Unit = { Text("$label   (mismatch %.1f)".format(c.cost)) }
        if (i == 0) Button(onClick = { vm.acceptCandidate(c) }, modifier = Modifier.fillMaxWidth()) { content() }
        else OutlinedButton(onClick = { vm.acceptCandidate(c) }, modifier = Modifier.fillMaxWidth()) { content() }
    }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
        OutlinedButton(onClick = { vm.startScan() }) { Text("Rescan") }
        TextButton(onClick = { vm.pickCornersManually() }) { Text("Tap corners") }
        TextButton(onClick = { vm.cancelScan() }) { Text("Cancel") }
    }
}
