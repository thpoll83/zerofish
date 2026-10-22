package com.chesscoach.core.vision

/** Grayscale image with luminance values 0..255. */
interface LumaImage {
    val width: Int
    val height: Int
    fun luma(x: Int, y: Int): Int
}

/** Simple array-backed [LumaImage], used by tests and as the Android adapter target. */
class ArrayLumaImage(override val width: Int, override val height: Int, val data: IntArray) : LumaImage {
    init {
        require(data.size == width * height)
    }

    override fun luma(x: Int, y: Int): Int = data[y * width + x]
}

/** A rectangular window of another image, without copying. */
class CropLumaImage(private val source: LumaImage, val x0: Int, val y0: Int, override val width: Int, override val height: Int) : LumaImage {
    init {
        require(x0 >= 0 && y0 >= 0 && x0 + width <= source.width && y0 + height <= source.height)
    }

    override fun luma(x: Int, y: Int): Int = source.luma(x0 + x, y0 + y)
}
