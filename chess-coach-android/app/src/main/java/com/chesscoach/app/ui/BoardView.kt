package com.chesscoach.app.ui

import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import com.chesscoach.core.chess.Board
import com.chesscoach.core.chess.Move
import com.chesscoach.core.chess.Piece
import com.chesscoach.core.chess.Square
import com.chesscoach.core.vision.SquareObservation
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin

/**
 * Digital board. Highlights [lastMove], draws [arrow] for the engine suggestion and, when [marks]
 * is given, a dot per square with what the camera saw so it can be compared with the pieces.
 */
@Composable
fun BoardView(
    board: Board,
    flipped: Boolean,
    lastMove: Move? = null,
    arrow: Move? = null,
    marks: List<SquareObservation>? = null,
    modifier: Modifier = Modifier,
) {
    Canvas(modifier.fillMaxWidth().aspectRatio(1f)) {
        val sq = size.width / 8
        fun col(square: Int) = if (flipped) 7 - Square.file(square) else Square.file(square)
        fun row(square: Int) = if (flipped) Square.rank(square) else 7 - Square.rank(square)
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
        marks?.let { obs ->
            for (s in 0 until 64) {
                val ob = obs[s]
                val c = centre(s) + Offset(sq * 0.3f, sq * 0.3f)
                val r = sq * 0.11f
                when (ob.label) {
                    1 -> drawCircle(Color.White, r, c)
                    2 -> drawCircle(Color.Black, r, c)
                    else -> drawCircle(Color(0xFF00C853), r * 0.4f, c)
                }
                if (ob.label != 0) drawCircle(Color(0xFF00C853), r, c, style = Stroke(width = 2f))
                if (ob.unsure) drawCircle(Color(0xFFFFC107), r * 1.5f, c, style = Stroke(width = 3f))
            }
        }
        arrow?.let { m ->
            val from = centre(m.from)
            val to = centre(m.to)
            val color = Color(0xCC1565C0)
            val angle = atan2(to.y - from.y, to.x - from.x)
            val head = sq * 0.35f
            val tip = to
            val shaftEnd = Offset(to.x - cos(angle) * head * 0.8f, to.y - sin(angle) * head * 0.8f)
            drawLine(color, from, shaftEnd, strokeWidth = sq * 0.16f, cap = StrokeCap.Round)
            val path = Path().apply {
                moveTo(tip.x, tip.y)
                lineTo(tip.x - cos(angle - 0.5f) * head, tip.y - sin(angle - 0.5f) * head)
                lineTo(tip.x - cos(angle + 0.5f) * head, tip.y - sin(angle + 0.5f) * head)
                close()
            }
            drawPath(path, color)
        }
    }
}
