package com.chesscoach.app

import android.Manifest
import android.content.pm.PackageManager
import android.util.Size
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.compose.foundation.layout.Column
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
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.chesscoach.core.vision.ArrayLumaImage
import java.util.concurrent.Executors

/**
 * Streams camera frames to [onFrame] as upright grayscale images, at most one every [minIntervalMs]
 * and never while the previous one is still being processed ([isBusy]). No preview surface: the
 * app shows its own annotated frames.
 */
@Composable
fun LiveCamera(isBusy: () -> Boolean, minIntervalMs: Long = 250, onFrame: (ArrayLumaImage) -> Unit) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var hasPermission by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { hasPermission = it }
    LaunchedEffect(Unit) { if (!hasPermission) launcher.launch(Manifest.permission.CAMERA) }
    if (!hasPermission) {
        Column {
            Text("Camera permission is needed to watch the board.")
            Button(onClick = { launcher.launch(Manifest.permission.CAMERA) }) { Text("Grant permission") }
        }
        return
    }
    val executor = remember { Executors.newSingleThreadExecutor() }
    DisposableEffect(lifecycleOwner) {
        val providerFuture = ProcessCameraProvider.getInstance(context)
        var provider: ProcessCameraProvider? = null
        var lastFrame = 0L
        providerFuture.addListener({
            val p = providerFuture.get()
            provider = p
            val analysis = ImageAnalysis.Builder()
                .setResolutionSelector(
                    ResolutionSelector.Builder()
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
            p.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, analysis)
        }, ContextCompat.getMainExecutor(context))
        onDispose {
            provider?.unbindAll()
            executor.shutdown()
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
            val remaining = buffer.remaining()
            val toRead = minOf(rowStride, remaining)
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
