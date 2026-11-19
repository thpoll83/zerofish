package com.chesscoach.app

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtProvider
import ai.onnxruntime.OrtSession
import com.chesscoach.core.vision.ChesscogCrops
import com.chesscoach.core.vision.SquareClassifier
import java.nio.FloatBuffer

/**
 * Chesscog's occupancy network (Georg Wölflein, MIT licence) through ONNX Runtime: crops in,
 * the probability of a piece per crop out. The model is converted at build time by
 * tools/chesscog_to_onnx.py. XNNPACK is used where ONNX Runtime has it, else the plain CPU
 * kernels; [provider] says which. No Android classes, so the replay tests run the same code.
 */
class ChesscogClassifier(model: ByteArray, threads: Int = 4) : SquareClassifier, AutoCloseable {
    private val env = OrtEnvironment.getEnvironment()
    private val session: OrtSession
    val provider: String

    init {
        var s: OrtSession? = null
        var p = "CPU, $threads threads"
        if (OrtProvider.XNNPACK in OrtEnvironment.getAvailableProviders()) {
            try {
                val opts = OrtSession.SessionOptions()
                opts.setIntraOpNumThreads(1)
                opts.addXnnpack(mapOf("intra_op_num_threads" to threads.toString()))
                s = env.createSession(model, opts)
                p = "XNNPACK, $threads threads"
            } catch (_: Exception) {
                s = null
            }
        }
        if (s == null) {
            val opts = OrtSession.SessionOptions()
            opts.setIntraOpNumThreads(threads)
            s = env.createSession(model, opts)
        }
        session = s
        provider = p
    }

    override fun occupied(crops: FloatArray, count: Int): FloatArray {
        val shape = longArrayOf(count.toLong(), 3, ChesscogCrops.SIZE.toLong(), ChesscogCrops.SIZE.toLong())
        OnnxTensor.createTensor(env, FloatBuffer.wrap(crops), shape).use { tensor ->
            session.run(mapOf(INPUT to tensor)).use { out ->
                val buf = (out.get(0) as OnnxTensor).floatBuffer
                return FloatArray(buf.remaining()).also { buf.get(it) }
            }
        }
    }

    override fun close() = session.close()

    companion object {
        const val INPUT = "crops"
        const val ASSET = "chesscog_occupancy.onnx"
    }
}
