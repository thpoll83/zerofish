package com.chesscoach.app

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtProvider
import ai.onnxruntime.OrtSession
import com.chesscoach.core.vision.Pt
import com.chesscoach.core.vision.YuvImage
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.nio.FloatBuffer
import java.security.MessageDigest
import kotlin.math.sqrt

/**
 * EXPERIMENT: how fast the phone runs a monocular depth model (Depth Anything V2 Small), the
 * candidate for reading which squares hold a piece from the board's shape instead of its
 * brightness. On the game videos, depth on every frame followed more moves by itself than the
 * luma reading; once a second it only tied. Whether it can run on every frame is what this
 * measures, on the CPU and with XNNPACK.
 *
 * No Android classes here, so the same code runs in a desktop test.
 */
class DepthBenchmark(private val modelFile: File) {

    class Config(val name: String, val setup: (OrtSession.SessionOptions) -> Unit)

    class Result(
        val config: String,
        /** Creating the session. */
        val loadMs: Long,
        val firstMs: Long,
        val medianMs: Long,
        val minMs: Long,
        val runs: Int,
        /** Correlation of this configuration's depth map with the first one's; near 1 means the same picture. */
        val agreement: Double?,
        val error: String?,
    ) {
        override fun toString(): String = if (error != null) "$config: failed, $error" else
            "$config: %d ms median, %d ms fastest of %d runs (first run %d ms, setup %d ms)%s".format(
                medianMs, minMs, runs, firstMs, loadMs, agreement?.let { ", agrees %.3f".format(it) } ?: "",
            )
    }

    /** The model's input for one frame, and where in the frame it came from. */
    class Prepared(val input: FloatArray, val cropX: Int, val cropY: Int, val cropW: Int, val cropH: Int, val side: Int, val millis: Long)

    /** A depth map of the cropped frame region, as gray pixels (ARGB), nearer is brighter. */
    class Preview(val width: Int, val height: Int, val argb: IntArray)

    fun modelReady(): Boolean = modelFile.exists() && modelFile.length() == MODEL_BYTES

    /** Downloads the model once (99 MB) and checks its SHA-256; [progress] gets the megabytes so far. */
    fun download(progress: (Double) -> Unit) {
        if (modelReady()) return
        modelFile.parentFile?.mkdirs()
        val part = File(modelFile.path + ".part")
        var url = URL(MODEL_URL)
        var conn: HttpURLConnection
        var hops = 0
        while (true) {
            conn = url.openConnection() as HttpURLConnection
            conn.instanceFollowRedirects = false
            conn.connectTimeout = 20_000
            conn.readTimeout = 60_000
            val code = conn.responseCode
            if (code in 300..399 && hops < 5) {
                url = URL(url, conn.getHeaderField("Location")); conn.disconnect(); hops++; continue
            }
            if (code != 200) throw IllegalStateException("download failed: HTTP $code")
            break
        }
        val md = MessageDigest.getInstance("SHA-256")
        conn.inputStream.use { input ->
            part.outputStream().use { out ->
                val buf = ByteArray(1 shl 16)
                var total = 0L
                var lastReport = 0L
                while (true) {
                    val n = input.read(buf)
                    if (n < 0) break
                    out.write(buf, 0, n); md.update(buf, 0, n); total += n
                    if (total - lastReport > 2_000_000) { progress(total / 1e6); lastReport = total }
                }
            }
        }
        val hash = md.digest().joinToString("") { "%02x".format(it) }
        if (hash != MODEL_SHA256) { part.delete(); throw IllegalStateException("downloaded model has the wrong checksum") }
        if (!part.renameTo(modelFile)) throw IllegalStateException("could not store the model")
    }

    /**
     * The frame region around the board (all of it when no board was found) as the model's
     * input: padded to a square at the bottom and right, scaled to 518 pixels, RGB normalised as
     * the model was trained. The region reaches above the board, where the far pieces stand.
     */
    fun prepare(frame: YuvImage, corners: List<Pt>): Prepared {
        val t0 = System.nanoTime()
        var x0 = 0; var y0 = 0; var x1 = frame.width; var y1 = frame.height
        if (corners.size == 4) {
            val minX = corners.minOf { it.x }; val maxX = corners.maxOf { it.x }
            val minY = corners.minOf { it.y }; val maxY = corners.maxOf { it.y }
            val bw = maxX - minX; val bh = maxY - minY
            x0 = (minX - 0.1 * bw).toInt().coerceIn(0, frame.width - 1)
            y0 = (minY - 0.35 * bh).toInt().coerceIn(0, frame.height - 1)
            x1 = (maxX + 0.1 * bw).toInt().coerceIn(x0 + 1, frame.width)
            y1 = (maxY + 0.1 * bh).toInt().coerceIn(y0 + 1, frame.height)
        }
        val w = x1 - x0; val h = y1 - y0
        val side = maxOf(w, h)
        val n = SIZE * SIZE
        val out = FloatArray(3 * n)
        val scale = side.toDouble() / SIZE
        for (oy in 0 until SIZE) {
            val sy = (oy + 0.5) * scale - 0.5
            for (ox in 0 until SIZE) {
                val sx = (ox + 0.5) * scale - 0.5
                var r = 0.0; var g = 0.0; var b = 0.0
                if (sx < w && sy < h) {
                    // bilinear over the four nearest frame pixels
                    val fx = sx.coerceIn(0.0, (w - 1).toDouble()); val fy = sy.coerceIn(0.0, (h - 1).toDouble())
                    val ix = fx.toInt(); val iy = fy.toInt()
                    val ax = fx - ix; val ay = fy - iy
                    val jx = minOf(ix + 1, w - 1); val jy = minOf(iy + 1, h - 1)
                    fun tap(px: Int, py: Int, wgt: Double) {
                        if (wgt == 0.0) return
                        val fxp = x0 + px; val fyp = y0 + py
                        val yy = frame.luma(fxp, fyp).toDouble(); val u = frame.u(fxp, fyp) - 128.0; val v = frame.v(fxp, fyp) - 128.0
                        r += wgt * (yy + 1.402 * v); g += wgt * (yy - 0.344136 * u - 0.714136 * v); b += wgt * (yy + 1.772 * u)
                    }
                    tap(ix, iy, (1 - ax) * (1 - ay)); tap(jx, iy, ax * (1 - ay)); tap(ix, jy, (1 - ax) * ay); tap(jx, jy, ax * ay)
                }
                val i = oy * SIZE + ox
                out[i] = ((r.coerceIn(0.0, 255.0) / 255.0 - 0.485) / 0.229).toFloat()
                out[n + i] = ((g.coerceIn(0.0, 255.0) / 255.0 - 0.456) / 0.224).toFloat()
                out[2 * n + i] = ((b.coerceIn(0.0, 255.0) / 255.0 - 0.406) / 0.225).toFloat()
            }
        }
        return Prepared(out, x0, y0, w, h, side, (System.nanoTime() - t0) / 1_000_000)
    }

    /**
     * Every configuration worth timing on this device: the CPU, and XNNPACK where present.
     * NNAPI is left out. On a Pixel 8 Pro (Tensor G3, Android 17) it ran the depth model in
     * 12.9 s per frame against 1.8 s on the CPU, and with half precision it never finished
     * preparing; the app was gone seconds after that setup had been abandoned.
     */
    fun configs(threads: Int = 4): List<Config> {
        val providers = OrtEnvironment.getAvailableProviders()
        val list = ArrayList<Config>()
        list += Config("CPU, $threads threads") { it.setIntraOpNumThreads(threads) }
        if (OrtProvider.XNNPACK in providers) list += Config("XNNPACK, $threads threads") {
            it.setIntraOpNumThreads(1); it.addXnnpack(mapOf("intra_op_num_threads" to threads.toString()))
        }
        return list
    }

    /**
     * Times each configuration on [prepared]: one untimed-for-the-median first run, then [runs]
     * timed runs. Returns the results and the first configuration's depth map for a look.
     */
    fun run(prepared: Prepared, configs: List<Config>, runs: Int = 5, onResult: (Result) -> Unit = {}, progress: (String) -> Unit = {}): Pair<List<Result>, FloatArray?> =
        time(modelFile.path, prepared.input, longArrayOf(1, 3, SIZE.toLong(), SIZE.toLong()), configs, runs, onResult = onResult, progress = progress)

    /**
     * Times any model at [modelPath] on one [input] of [shape] under each configuration: one
     * first run, then [runs] timed runs. Returns the results and the first configuration's
     * output, to which the others' outputs are compared; [onResult] gets each result as it is
     * known. Each configuration gets [limitMs]: on a Pixel 8 Pro, NNAPI with half precision
     * never finished preparing the depth model, and the benchmark showed "preparing" forever.
     * A configuration past its limit is reported; its thread cannot be stopped.
     */
    fun time(
        modelPath: String, input: FloatArray, shape: LongArray, configs: List<Config>, runs: Int = 5,
        limitMs: Long = 120_000, onResult: (Result) -> Unit = {}, progress: (String) -> Unit = {},
    ): Pair<List<Result>, FloatArray?> {
        val env = OrtEnvironment.getEnvironment()
        val results = ArrayList<Result>()
        var reference: FloatArray? = null
        for (c in configs) {
            progress("${c.name}: preparing")
            var outcome: Pair<Result, FloatArray?>? = null
            val worker = Thread({
                outcome = try {
                    timeOne(env, modelPath, input, shape, c, runs, reference, progress)
                } catch (e: Throwable) {
                    Result(c.name, 0, 0, 0, 0, 0, null, (e.message ?: e.javaClass.simpleName).lineSequence().first().take(160)) to null
                }
            }, "bench-${c.name}")
            worker.isDaemon = true
            worker.start()
            worker.join(limitMs)
            val done = outcome
            if (done == null) {
                results += Result(c.name, 0, 0, 0, 0, 0, null, "no answer after ${limitMs / 1000} s").also(onResult)
                continue
            }
            results += done.first.also(onResult)
            if (reference == null && done.first.error == null) reference = done.second
        }
        return results to reference
    }

    private fun timeOne(env: OrtEnvironment, modelPath: String, input: FloatArray, shape: LongArray, c: Config, runs: Int, reference: FloatArray?, progress: (String) -> Unit): Pair<Result, FloatArray?> {
        val t0 = System.nanoTime()
        OrtSession.SessionOptions().use { opts ->
            c.setup(opts)
            env.createSession(modelPath, opts).use { session ->
                val loadMs = (System.nanoTime() - t0) / 1_000_000
                val inputName = session.inputNames.first()
                val times = ArrayList<Long>()
                var output: FloatArray? = null
                var firstMs = 0L
                for (k in 0..runs) {
                    progress("${c.name}: run ${k + 1} of ${runs + 1}")
                    OnnxTensor.createTensor(env, FloatBuffer.wrap(input), shape).use { tensor ->
                        val s = System.nanoTime()
                        session.run(mapOf(inputName to tensor)).use { out ->
                            val ms = (System.nanoTime() - s) / 1_000_000
                            if (k == 0) {
                                firstMs = ms
                                val buf = (out.get(0) as OnnxTensor).floatBuffer
                                output = FloatArray(buf.remaining()).also { buf.get(it) }
                            } else times += ms
                        }
                    }
                }
                times.sort()
                val d = output
                val agreement = if (reference != null && d != null) correlation(reference, d) else null
                return Result(c.name, loadMs, firstMs, times[times.size / 2], times.first(), times.size, agreement, null) to d
            }
        }
    }

    /** The depth map of the cropped region, scaled to gray from its 2nd to 98th percentile. */
    fun preview(prepared: Prepared, depth: FloatArray): Preview {
        val sorted = depth.copyOf().also { it.sort() }
        val lo = sorted[(sorted.size * 0.02).toInt()]; val hi = sorted[(sorted.size * 0.98).toInt()]
        val w = (prepared.cropW.toDouble() / prepared.side * SIZE).toInt().coerceIn(1, SIZE)
        val h = (prepared.cropH.toDouble() / prepared.side * SIZE).toInt().coerceIn(1, SIZE)
        val px = IntArray(w * h)
        for (y in 0 until h) for (x in 0 until w) {
            val g = (((depth[y * SIZE + x] - lo) / (hi - lo + 1e-9f)).coerceIn(0f, 1f) * 255).toInt()
            px[y * w + x] = (0xFF shl 24) or (g shl 16) or (g shl 8) or g
        }
        return Preview(w, h, px)
    }

    private fun correlation(a: FloatArray, b: FloatArray): Double {
        if (a.size != b.size) return Double.NaN
        val ma = a.average(); val mb = b.average()
        var sab = 0.0; var saa = 0.0; var sbb = 0.0
        for (i in a.indices) { val da = a[i] - ma; val db = b[i] - mb; sab += da * db; saa += da * da; sbb += db * db }
        return sab / sqrt(saa * sbb + 1e-12)
    }

    companion object {
        const val SIZE = 518
        const val MODEL_URL = "https://github.com/fabio-sim/Depth-Anything-ONNX/releases/download/v2.0.0/depth_anything_v2_vits.onnx"
        const val MODEL_BYTES = 99_373_606L
        const val MODEL_SHA256 = "d2b11a11c1d4a12b47608fa65a17ee9a4c605b55ee1730c8e3b526304f2562be"
    }
}
