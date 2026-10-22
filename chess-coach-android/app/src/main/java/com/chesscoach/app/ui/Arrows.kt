package com.chesscoach.app.ui

import android.graphics.Paint
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.nativeCanvas
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin

/**
 * An arrow from one square to another, drawn on the digital board and over the camera picture:
 * the engine's suggestion (no label), or one of the moves offered when the camera cannot tell
 * which move was played (numbered, in its own colour).
 */
data class MoveArrow(val from: Int, val to: Int, val color: Color, val label: String? = null)

object ArrowColors {
    val suggestion = Color(0xCC1565C0)

    /** The move just played, shown as confirmation until the next one. */
    val lastMove = Color(0xCC16A34A)

    /** One colour per offered move, in the order they are listed. */
    private val choices = listOf(
        Color(0xDDFF6D00), Color(0xDDAA00FF), Color(0xDD00B8D4), Color(0xDDD50000), Color(0xDD64DD17), Color(0xDDFFD600),
    )

    fun choice(i: Int): Color = choices[i % choices.size]
}

/** Draws [arrow] between the two centres; [unit] is about one square's width in drawing pixels. */
fun DrawScope.drawMoveArrow(arrow: MoveArrow, from: Offset, to: Offset, unit: Float) {
    val angle = atan2(to.y - from.y, to.x - from.x)
    val head = unit * 0.35f
    val shaftEnd = Offset(to.x - cos(angle) * head * 0.8f, to.y - sin(angle) * head * 0.8f)
    drawLine(arrow.color, from, shaftEnd, strokeWidth = unit * 0.16f, cap = StrokeCap.Round)
    val path = Path().apply {
        moveTo(to.x, to.y)
        lineTo(to.x - cos(angle - 0.5f) * head, to.y - sin(angle - 0.5f) * head)
        lineTo(to.x - cos(angle + 0.5f) * head, to.y - sin(angle + 0.5f) * head)
        close()
    }
    drawPath(path, arrow.color)
    val label = arrow.label ?: return
    // numbered badge at the arrow's tip, so the number can be read against any background
    val r = unit * 0.22f
    drawCircle(arrow.color, r, to)
    drawCircle(Color.White, r, to, style = androidx.compose.ui.graphics.drawscope.Stroke(width = unit * 0.03f))
    val paint = Paint().apply {
        color = android.graphics.Color.WHITE
        textSize = r * 1.4f
        isAntiAlias = true
        textAlign = Paint.Align.CENTER
        isFakeBoldText = true
    }
    val baseline = to.y - (paint.descent() + paint.ascent()) / 2
    drawContext.canvas.nativeCanvas.drawText(label, to.x, baseline, paint)
}
