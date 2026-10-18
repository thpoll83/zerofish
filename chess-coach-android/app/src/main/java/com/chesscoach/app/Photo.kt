package com.chesscoach.app

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import androidx.camera.core.ImageProxy
import com.chesscoach.core.vision.LumaImage

/** A captured photo plus its grayscale copy for the scanner. */
class Photo(val bitmap: Bitmap) {
    val luma: LumaImage by lazy { BitmapLuma(bitmap) }

    companion object {
        const val MAX_SIDE = 1280

        /** Decodes a JPEG [ImageProxy], applies the sensor rotation and limits the longer side to [MAX_SIDE]. */
        fun fromImageProxy(image: ImageProxy): Photo {
            val buffer = image.planes[0].buffer
            val bytes = ByteArray(buffer.remaining())
            buffer.get(bytes)
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
            var sample = 1
            while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= MAX_SIDE) sample *= 2
            val opts = BitmapFactory.Options().apply { inSampleSize = sample }
            var bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opts)
            val rotation = image.imageInfo.rotationDegrees
            if (rotation != 0) {
                val m = Matrix().apply { postRotate(rotation.toFloat()) }
                bmp = Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height, m, true)
            }
            return Photo(bmp)
        }
    }
}

class BitmapLuma(bitmap: Bitmap) : LumaImage {
    override val width = bitmap.width
    override val height = bitmap.height
    private val data = IntArray(width * height)

    init {
        bitmap.getPixels(data, 0, width, 0, 0, width, height)
        for (i in data.indices) {
            val p = data[i]
            val r = (p shr 16) and 0xFF
            val g = (p shr 8) and 0xFF
            val b = p and 0xFF
            data[i] = (r * 77 + g * 151 + b * 28) shr 8
        }
    }

    override fun luma(x: Int, y: Int): Int = data[y * width + x]
}
