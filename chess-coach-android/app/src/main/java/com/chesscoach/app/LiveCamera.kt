package com.chesscoach.app

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Paint
import android.hardware.camera2.CameraCharacteristics
import android.util.Size
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.camera2.interop.Camera2CameraInfo
import androidx.camera.camera2.interop.ExperimentalCamera2Interop
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.AspectRatioStrategy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.chesscoach.app.ui.MoveArrow
import com.chesscoach.app.ui.drawMoveArrow
import com.chesscoach.core.chess.Square
import com.chesscoach.core.vision.ArrayLumaImage
import com.chesscoach.core.vision.BoardGeometry
import com.chesscoach.core.vision.Pt
import com.chesscoach.core.vision.SquareObservation
import java.util.concurrent.Executors
import kotlin.math.hypot

/** A back camera the phone exposes, with its focal length so the widest one can be named. */
data class CameraOption(val id: String, val label: String, val focalMm: Float)

data class CameraSettings(val cameraId: String? = null, val zoom: Float = 1f, val torch: Boolean = false)

/**
 * Live preview with the recognition overlay, plus a frame stream to [onFrame] (upright grayscale,
 * at most one frame per [minIntervalMs] and never while [isBusy]). The view is square: the 4:3
 * picture fills it and is cropped at the top and bottom (the analysis still sees the whole
 * frame). Preview and analysis share the aspect ratio, so an overlay point is the analysis-frame
 * point scaled and shifted by the crop. [arrows] are drawn between square centres on the board
 * as found, and a tap on the picture reports the nearest square to [onSquareTap].
 */
@OptIn(ExperimentalCamera2Interop::class)
@Composable
fun LiveCameraView(
    settings: CameraSettings,
    corners: List<Pt>,
    observations: List<SquareObservation>?,
    frameWidth: Int,
    frameHeight: Int,
    isBusy: () -> Boolean,
    onCameras: (List<CameraOption>, Float, Float) -> Unit,
    onFrame: (ArrayLumaImage) -> Unit,
    arrows: List<MoveArrow> = emptyList(),
    onSquareTap: ((Int) -> Unit)? = null,
    minIntervalMs: Long = 250,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var hasPermission by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { hasPermission = it }
    LaunchedEffect(Unit) { if (!hasPermission) launcher.launch(Manifest.permission.CAMERA) }
    if (!hasPermission) {
        Column(modifier) {
            Text("Camera permission is needed to watch the board.")
            Button(onClick = { launcher.launch(Manifest.permission.CAMERA) }) { Text("Grant permission") }
        }
        return
    }
    val executor = remember { Executors.newSingleThreadExecutor() }
    val previewView = remember { PreviewView(context).apply { scaleType = PreviewView.ScaleType.FILL_CENTER } }
    var camera by remember { mutableStateOf<Camera?>(null) }

    DisposableEffect(lifecycleOwner, settings.cameraId) {
        val providerFuture = ProcessCameraProvider.getInstance(context)
        var provider: ProcessCameraProvider? = null
        var lastFrame = 0L
        providerFuture.addListener({
            val p = providerFuture.get()
            provider = p
            // enumerate back cameras once
            val options = p.availableCameraInfos.mapNotNull { info ->
                val c2 = Camera2CameraInfo.from(info)
                val facing = c2.getCameraCharacteristic(CameraCharacteristics.LENS_FACING)
                if (facing != CameraCharacteristics.LENS_FACING_BACK) return@mapNotNull null
                val focal = c2.getCameraCharacteristic(CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS)?.minOrNull() ?: 0f
                CameraOption(c2.cameraId, "Camera ${c2.cameraId} (%.1f mm)".format(focal), focal)
            }.sortedBy { it.focalMm }
            val selector = settings.cameraId?.let { id ->
                CameraSelector.Builder().addCameraFilter { infos -> infos.filter { Camera2CameraInfo.from(it).cameraId == id } }.build()
            } ?: CameraSelector.DEFAULT_BACK_CAMERA
            val ratio43 = AspectRatioStrategy.RATIO_4_3_FALLBACK_AUTO_STRATEGY
            val preview = Preview.Builder()
                .setResolutionSelector(ResolutionSelector.Builder().setAspectRatioStrategy(ratio43).build())
                .build()
            preview.setSurfaceProvider(previewView.surfaceProvider)
            val analysis = ImageAnalysis.Builder()
                .setResolutionSelector(
                    ResolutionSelector.Builder()
                        .setAspectRatioStrategy(ratio43)
                        .setResolutionStrategy(ResolutionStrategy(Size(1280, 960), ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER))
                        .build(),
                )
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
                .build()
            analysis.setAnalyzer(executor) { image ->
                try {
                    val now = System.currentTimeMillis()
                    if (!isBusy() && now - lastFrame >= minIntervalMs) {
                        lastFrame = now
                        onFrame(FrameConverter.toUprightLuma(image))
                    }
                } finally {
                    image.close()
                }
            }
            p.unbindAll()
            val cam = try {
                p.bindToLifecycle(lifecycleOwner, selector, preview, analysis)
            } catch (e: Exception) {
                p.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
            }
            camera = cam
            val zs = cam.cameraInfo.zoomState.value
            onCameras(options, zs?.minZoomRatio ?: 1f, zs?.maxZoomRatio ?: 1f)
        }, ContextCompat.getMainExecutor(context))
        onDispose {
            provider?.unbindAll()
            camera = null
        }
    }
    DisposableEffect(Unit) { onDispose { executor.shutdown() } }
    LaunchedEffect(camera, settings.zoom, settings.torch) {
        val cam = camera ?: return@LaunchedEffect
        val zs = cam.cameraInfo.zoomState.value
        val z = settings.zoom.coerceIn(zs?.minZoomRatio ?: 1f, zs?.maxZoomRatio ?: 1f)
        cam.cameraControl.setZoomRatio(z)
        if (cam.cameraInfo.hasFlashUnit()) cam.cameraControl.enableTorch(settings.torch)
    }

    val geometry = remember(corners) { if (corners.size == 4) runCatching { BoardGeometry(corners) }.getOrNull() else null }
    Box(modifier.fillMaxWidth().aspectRatio(1f).clipToBounds()) {
        AndroidView(factory = { previewView }, modifier = Modifier.fillMaxSize())
        Canvas(
            Modifier.fillMaxSize().pointerInput(geometry, onSquareTap, frameWidth, frameHeight) {
                if (onSquareTap != null && geometry != null && frameWidth > 0) detectTapGestures { pos ->
                    // the picture fills the square: same scale on both axes, centred
                    val scale = maxOf(size.width.toFloat() / frameWidth, size.height.toFloat() / frameHeight)
                    val ox = (size.width - frameWidth * scale) / 2
                    val oy = (size.height - frameHeight * scale) / 2
                    val x = (pos.x - ox) / scale
                    val y = (pos.y - oy) / scale
                    var best = -1
                    var bestD = Double.MAX_VALUE
                    for (sq in 0 until 64) {
                        val c = geometry.toImage(Square.file(sq) + 0.5, Square.rank(sq) + 0.5)
                        val d = hypot(c.x - x, c.y - y)
                        if (d < bestD) { bestD = d; best = sq }
                    }
                    val a = geometry.toImage(0.5, 0.5); val b = geometry.toImage(1.5, 0.5)
                    if (best >= 0 && bestD <= 0.8 * hypot(a.x - b.x, a.y - b.y)) onSquareTap(best)
                }
            },
        ) {
            if (frameWidth <= 0) return@Canvas
            val scale = maxOf(size.width / frameWidth, size.height / frameHeight)
            val ox = (size.width - frameWidth * scale) / 2
            val oy = (size.height - frameHeight * scale) / 2
            fun o(p: Pt) = Offset((p.x * scale).toFloat() + ox, (p.y * scale).toFloat() + oy)
            if (geometry != null) {
                for (i in 0..8) {
                    drawLine(Color(0xFF00E676), o(geometry.toImage(i.toDouble(), 0.0)), o(geometry.toImage(i.toDouble(), 8.0)), strokeWidth = 3f)
                    drawLine(Color(0xFF00E676), o(geometry.toImage(0.0, i.toDouble())), o(geometry.toImage(8.0, i.toDouble())), strokeWidth = 3f)
                }
                val labelPaint = Paint().apply {
                    color = android.graphics.Color.YELLOW; textSize = size.width / 30; isAntiAlias = true
                    textAlign = Paint.Align.CENTER; setShadowLayer(3f, 0f, 0f, android.graphics.Color.BLACK)
                }
                val a1 = o(geometry.toImage(0.5, 0.5))
                drawContext.canvas.nativeCanvas.drawText("a1", a1.x, a1.y, labelPaint)
                val h8 = o(geometry.toImage(7.5, 7.5))
                drawContext.canvas.nativeCanvas.drawText("h8", h8.x, h8.y, labelPaint)
                observations?.let { obs ->
                    val r = size.width / 70
                    for (sq in 0 until 64) {
                        val w = geometry.sampleWindow(Square.file(sq), Square.rank(sq))
                        val c = o(geometry.toImage((w[0] + w[1]) / 2, (w[2] + w[3]) / 2))
                        val ob = obs[sq]
                        when (ob.label) {
                            1 -> drawCircle(Color.White, r, c)
                            2 -> drawCircle(Color.Black, r, c)
                            else -> drawCircle(Color(0xFF00C853), r * 0.4f, c)
                        }
                        if (ob.label != 0) drawCircle(Color(0xFF00C853), r, c, style = Stroke(width = 2f))
                        if (ob.unsure) drawCircle(Color.Yellow, r * 1.5f, c, style = Stroke(width = 3f))
                    }
                }
                val a = o(geometry.toImage(0.5, 0.5)); val b = o(geometry.toImage(1.5, 0.5))
                val unit = hypot((a.x - b.x).toDouble(), (a.y - b.y).toDouble()).toFloat().coerceAtLeast(size.width / 16)
                for (arrow in arrows) {
                    val from = o(geometry.toImage(Square.file(arrow.from) + 0.5, Square.rank(arrow.from) + 0.5))
                    val to = o(geometry.toImage(Square.file(arrow.to) + 0.5, Square.rank(arrow.to) + 0.5))
                    drawMoveArrow(arrow, from, to, unit)
                }
            }
        }
    }
}

object FrameConverter {
    /** Copies the Y plane of a YUV frame and rotates it so the picture is upright. */
    fun toUprightLuma(image: ImageProxy): ArrayLumaImage {
        val plane = image.planes[0]
        val buffer = plane.buffer
        val rowStride = plane.rowStride
        val pixelStride = plane.pixelStride
        val w = image.width
        val h = image.height
        val src = IntArray(w * h)
        val row = ByteArray(rowStride)
        buffer.rewind()
        for (y in 0 until h) {
            val toRead = minOf(rowStride, buffer.remaining())
            buffer.get(row, 0, toRead)
            var o = y * w
            var i = 0
            for (x in 0 until w) {
                src[o++] = row[i].toInt() and 0xFF
                i += pixelStride
            }
        }
        return when (image.imageInfo.rotationDegrees) {
            90 -> ArrayLumaImage(h, w, IntArray(w * h).also { out ->
                for (ny in 0 until w) for (nx in 0 until h) out[ny * h + nx] = src[(h - 1 - nx) * w + ny]
            })
            180 -> ArrayLumaImage(w, h, IntArray(w * h).also { out ->
                for (ny in 0 until h) for (nx in 0 until w) out[ny * w + nx] = src[(h - 1 - ny) * w + (w - 1 - nx)]
            })
            270 -> ArrayLumaImage(h, w, IntArray(w * h).also { out ->
                for (ny in 0 until w) for (nx in 0 until h) out[ny * h + nx] = src[nx * w + (w - 1 - ny)]
            })
            else -> ArrayLumaImage(w, h, src)
        }
    }
}
