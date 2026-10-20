package com.chesscoach.app

import android.content.Context
import android.graphics.ImageFormat
import android.graphics.Rect
import android.os.Build
import com.chesscoach.core.vision.YuvImage
import java.io.BufferedWriter
import java.io.File
import java.io.FileOutputStream
import java.io.FileWriter
import java.io.IOException
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * A log of what the tracker saw and decided, with the camera frames behind each decision, kept
 * in the app's own files (no permission needed) and bundled into a zip to share. The log lines
 * follow the replay harness's format, so a bundle can be read like a replay; the frames are
 * saved as the tracker saw them (upright, at the analysis resolution), so they can be fed to it
 * again. At most [maxImages] frames are kept, the oldest going first.
 */
class DebugRecorder(private val context: Context) {
    private val dir = File(context.getExternalFilesDir(null) ?: context.filesDir, "debug")
    private val startedAt = System.currentTimeMillis()
    private var writer: BufferedWriter? = null
    private var images = -1
    private val maxImages = 400

    @Volatile var enabled = true

    private fun seconds() = (System.currentTimeMillis() - startedAt) / 1000.0

    @Synchronized fun log(line: String) {
        if (!enabled) return
        try {
            dir.mkdirs()
            val w = writer ?: BufferedWriter(FileWriter(File(dir, "log.txt"), true)).also {
                writer = it
                it.write("# Chess Coach debug log, ${java.util.Date()}, ${Build.MANUFACTURER} ${Build.MODEL}, Android ${Build.VERSION.RELEASE}, app ${BuildConfig.VERSION_NAME}\n")
            }
            w.write("%8.1fs %s\n".format(seconds(), line))
            w.flush()
        } catch (_: IOException) {
        }
    }

    /** Saves [image] as `fNNNN_tag.jpg` next to the log and returns the file name, or null when off or failed. */
    @Synchronized fun frame(frameNo: Int, tag: String, image: YuvImage): String? {
        if (!enabled) return null
        return try {
            dir.mkdirs()
            if (images < 0) images = dir.listFiles { f -> f.name.endsWith(".jpg") }?.size ?: 0
            if (images >= maxImages) {
                dir.listFiles { f -> f.name.endsWith(".jpg") }?.sortedBy { it.name }?.take(images - maxImages + 1)?.forEach { it.delete(); images-- }
            }
            val name = "f%05d_%s.jpg".format(frameNo, tag)
            FileOutputStream(File(dir, name)).use { out ->
                android.graphics.YuvImage(nv21(image), ImageFormat.NV21, image.width, image.height, null).compressToJpeg(Rect(0, 0, image.width, image.height), 82, out)
            }
            images++
            name
        } catch (e: Exception) {
            null
        }
    }

    /** The tracker's planes as NV21: the luma plane, then V and U interleaved at half resolution. */
    private fun nv21(image: YuvImage): ByteArray {
        val w = image.width
        val h = image.height
        val cw = image.chromaWidth
        val ch = image.chromaHeight
        val out = ByteArray(w * h + 2 * cw * ch)
        for (i in 0 until w * h) out[i] = image.y[i].toByte()
        var o = w * h
        for (i in 0 until cw * ch) {
            out[o++] = image.v[i].toByte()
            out[o++] = image.u[i].toByte()
        }
        return out
    }

    /** Lines and frames so far, for the settings screen. */
    @Synchronized fun summary(): String {
        val files = dir.listFiles() ?: return "empty"
        val bytes = files.sumOf { it.length() }
        return "%d frames, %.1f MB".format(files.count { it.name.endsWith(".jpg") }, bytes / 1e6)
    }

    /** Zips the log and the frames into the cache's share folder and returns the zip. */
    @Synchronized fun bundle(): File {
        writer?.flush()
        val share = File(context.cacheDir, "share").apply { mkdirs() }
        share.listFiles()?.forEach { it.delete() }
        val zip = File(share, "chess-coach-debug-%tY%<tm%<td-%<tH%<tM.zip".format(java.util.Date()))
        ZipOutputStream(FileOutputStream(zip).buffered()).use { out ->
            dir.listFiles()?.sortedBy { it.name }?.forEach { f ->
                out.putNextEntry(ZipEntry("debug/" + f.name))
                f.inputStream().use { it.copyTo(out) }
                out.closeEntry()
            }
        }
        return zip
    }

    @Synchronized fun clear() {
        writer?.close()
        writer = null
        dir.listFiles()?.forEach { it.delete() }
        images = 0
    }
}
