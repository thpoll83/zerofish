package com.chesscoach.core

import com.chesscoach.core.vision.YuvImage
import java.awt.image.BufferedImage
import java.io.File
import java.io.InputStream
import javax.imageio.ImageIO

/** Decodes test photos and video frames into the camera's format: luma at full size, chroma at half. */
object TestImages {
    fun load(file: File): YuvImage = toYuv(ImageIO.read(file))

    fun load(stream: InputStream): YuvImage = toYuv(ImageIO.read(stream))

    fun toYuv(bi: BufferedImage): YuvImage {
        val w = bi.width; val h = bi.height
        val cw = (w + 1) / 2; val ch = (h + 1) / 2
        val y = IntArray(w * h)
        val u = IntArray(cw * ch); val v = IntArray(cw * ch)
        val n = IntArray(cw * ch)
        for (yy in 0 until h) for (x in 0 until w) {
            val rgb = bi.getRGB(x, yy)
            val r = (rgb shr 16) and 255; val g = (rgb shr 8) and 255; val b = rgb and 255
            y[yy * w + x] = (r * 77 + g * 151 + b * 28) shr 8
            val ci = (yy shr 1) * cw + (x shr 1)
            u[ci] += (128 - 0.169 * r - 0.331 * g + 0.5 * b).toInt().coerceIn(0, 255)
            v[ci] += (128 + 0.5 * r - 0.419 * g - 0.081 * b).toInt().coerceIn(0, 255)
            n[ci]++
        }
        for (i in u.indices) if (n[i] > 0) { u[i] /= n[i]; v[i] /= n[i] }
        return YuvImage(w, h, y, u, v)
    }
}
