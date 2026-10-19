package com.chesscoach.app.ui

import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.input.pointer.pointerInput
import com.chesscoach.core.chess.Board
import com.chesscoach.core.chess.Move
import com.chesscoach.core.chess.Piece
import com.chesscoach.core.chess.Square

/**
 * Digital board. Highlights [lastMove], draws [arrows] (the engine's suggestion, or the moves
 * offered for a tap) and reports a tapped square to [onSquareTap].
 */
@Composable
fun BoardView(
    board: Board,
    flipped: Boolean,
    lastMove: Move? = null,
    arrows: List<MoveArrow> = emptyList(),
    onSquareTap: ((Int) -> Unit)? = null,
    modifier: Modifier = Modifier,
) {
    fun col(square: Int) = if (flipped) 7 - Square.file(square) else Square.file(square)
    fun row(square: Int) = if (flipped) Square.rank(square) else 7 - Square.rank(square)
    Canvas(
        modifier.fillMaxWidth().aspectRatio(1f).pointerInput(onSquareTap, flipped) {
            if (onSquareTap != null) detectTapGestures { pos ->
                val sq = size.width / 8f
                val c = (pos.x / sq).toInt().coerceIn(0, 7)
                val r = (pos.y / sq).toInt().coerceIn(0, 7)
                val file = if (flipped) 7 - c else c
                val rank = if (flipped) r else 7 - r
                onSquareTap(Square.of(file, rank))
            }
        },
    ) {
        val sq = size.width / 8
        fun centre(square: Int) = Offset(col(square) * sq + sq / 2, row(square) * sq + sq / 2)

        for (s in 0 until 64) {
            val light = Square.isLight(s)
            val base = if (light) Color(0xFFEEEED2) else Color(0xFF769656)
            drawRect(base, Offset(col(s) * sq, row(s) * sq), Size(sq, sq))
            if (lastMove != null && (s == lastMove.from || s == lastMove.to)) {
                drawRect(Color(0x80FFEB3B), Offset(col(s) * sq, row(s) * sq), Size(sq, sq))
            }
        }
        val piecePaint = Paint().apply {
            textSize = sq * 0.78f
            textAlign = Paint.Align.CENTER
            isAntiAlias = true
        }
        val coordPaint = Paint().apply {
            textSize = sq * 0.2f
            isAntiAlias = true
            color = android.graphics.Color.DKGRAY
        }
        for (s in 0 until 64) {
            val cell = board[s]
            if (cell != 0) {
                piecePaint.color = android.graphics.Color.BLACK
                val c = centre(s)
                val baseline = c.y - (piecePaint.descent() + piecePaint.ascent()) / 2
                drawContext.canvas.nativeCanvas.drawText(Piece.glyph(cell).toString(), c.x, baseline, piecePaint)
            }
        }
        for (i in 0 until 8) {
            val fileSquare = if (flipped) Square.of(7 - i, 7) else Square.of(i, 0)
            val rankSquare = if (flipped) Square.of(7, i) else Square.of(0, 7 - i)
            drawContext.canvas.nativeCanvas.drawText(('a' + Square.file(fileSquare)).toString(), i * sq + sq * 0.05f, 8 * sq - sq * 0.06f, coordPaint)
            drawContext.canvas.nativeCanvas.drawText((Square.rank(rankSquare) + 1).toString(), sq * 0.05f, i * sq + sq * 0.25f, coordPaint)
        }
        for (a in arrows) drawMoveArrow(a, centre(a.from), centre(a.to), sq)
    }
}
