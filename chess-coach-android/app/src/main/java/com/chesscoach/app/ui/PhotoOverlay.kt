package com.chesscoach.app.ui

import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import com.chesscoach.app.Photo
import com.chesscoach.core.chess.Square
import com.chesscoach.core.vision.BoardGeometry
import com.chesscoach.core.vision.ImageLine
import com.chesscoach.core.vision.Pt
import com.chesscoach.core.vision.SquareObservation

/**
 * The photo with recognition overlay: tapped corners, the warped 8x8 grid, the patch each square is
 * read from, and one marker per square for what the scanner saw (white / black / empty / unsure).
 */
@Composable
fun PhotoOverlay(
    photo: Photo,
    corners: List<Pt>,
    observations: List<SquareObservation>? = null,
    debugLines: List<ImageLine> = emptyList(),
    onTap: ((Pt) -> Unit)? = null,
    modifier: Modifier = Modifier,
) {
    val bmp = photo.bitmap
    val image = remember(bmp) { bmp.asImageBitmap() }
    val geometry = remember(corners) { if (corners.size == 4) runCatching { BoardGeometry(corners) }.getOrNull() else null }
    Box(modifier.fillMaxWidth().aspectRatio(bmp.width.toFloat() / bmp.height)) {
        Image(image, contentDescription = "board photo", contentScale = ContentScale.Fit, modifier = Modifier.fillMaxSize())
        Canvas(
            Modifier.fillMaxSize().pointerInput(onTap) {
                if (onTap != null) detectTapGestures { pos ->
                    val scale = size.width.toFloat() / bmp.width
                    onTap(Pt(pos.x / scale.toDouble(), pos.y / scale.toDouble()))
                }
            },
        ) {
            val scale = size.width / bmp.width
            fun o(p: Pt) = Offset((p.x * scale).toFloat(), (p.y * scale).toFloat())
            val labelPaint = Paint().apply {
                color = android.graphics.Color.YELLOW
                textSize = 14f * scale * (bmp.width / 400f)
                isAntiAlias = true
                textAlign = Paint.Align.CENTER
                setShadowLayer(3f, 0f, 0f, android.graphics.Color.BLACK)
            }
            for (dl in debugLines) {
                val color = if (dl.family == 0) Color(0x80FF5252) else Color(0x80FFAB40)
                drawLine(color, Offset((dl.x1 * scale).toFloat(), (dl.y1 * scale).toFloat()), Offset((dl.x2 * scale).toFloat(), (dl.y2 * scale).toFloat()), strokeWidth = 1.5f * scale)
            }
            val cornerNames = listOf("a1", "h1", "h8", "a8")
            corners.forEachIndexed { i, c ->
                drawCircle(Color.Yellow, radius = 6f * scale * (bmp.width / 400f), center = o(c), style = Stroke(width = 2f * scale))
                drawContext.canvas.nativeCanvas.drawText(cornerNames[i], o(c).x, o(c).y - 10f * scale, labelPaint)
            }
            if (geometry != null) {
                drawGrid(geometry, ::o, scale)
                for (sq in 0 until 64) {
                    val poly = geometry.sampleWindowPolygon(Square.file(sq), Square.rank(sq)).map(::o)
                    drawPoly(poly, Color(0x6600E5FF), 1f * scale)
                }
                for (f in 0 until 8) {
                    val p = o(geometry.toImage(f + 0.5, -0.35))
                    drawContext.canvas.nativeCanvas.drawText(('a' + f).toString(), p.x, p.y, labelPaint)
                }
                for (r in 0 until 8) {
                    val p = o(geometry.toImage(-0.35, r + 0.5))
                    drawContext.canvas.nativeCanvas.drawText((r + 1).toString(), p.x, p.y, labelPaint)
                }
                observations?.let { obs ->
                    for (sq in 0 until 64) {
                        val w = geometry.sampleWindow(Square.file(sq), Square.rank(sq))
                        val centre = o(geometry.toImage((w[0] + w[1]) / 2, (w[2] + w[3]) / 2))
                        val ob = obs[sq]
                        val radius = 7f * scale * (bmp.width / 400f)
                        when (ob.label) {
                            1 -> drawCircle(Color.White, radius, centre)
                            2 -> drawCircle(Color.Black, radius, centre)
                            else -> drawCircle(Color(0xFF00C853), radius * 0.4f, centre)
                        }
                        if (ob.label != 0) drawCircle(Color(0xFF00C853), radius, centre, style = Stroke(width = 2f * scale))
                        if (ob.unsure) drawCircle(Color.Yellow, radius * 1.5f, centre, style = Stroke(width = 3f * scale))
                    }
                }
            }
        }
    }
}

private fun DrawScope.drawGrid(geometry: BoardGeometry, o: (Pt) -> Offset, scale: Float) {
    for (i in 0..8) {
        drawLine(Color(0xFF00E676), o(geometry.toImage(i.toDouble(), 0.0)), o(geometry.toImage(i.toDouble(), 8.0)), strokeWidth = 2f * scale)
        drawLine(Color(0xFF00E676), o(geometry.toImage(0.0, i.toDouble())), o(geometry.toImage(8.0, i.toDouble())), strokeWidth = 2f * scale)
    }
}

private fun DrawScope.drawPoly(points: List<Offset>, color: Color, width: Float) {
    val path = Path()
    points.forEachIndexed { i, p -> if (i == 0) path.moveTo(p.x, p.y) else path.lineTo(p.x, p.y) }
    path.close()
    drawPath(path, color, style = Stroke(width = width))
}
