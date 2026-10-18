package com.chesscoach.core

import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * Replays a committed passage of a real game video (see src/test/resources/video/NOTICE.md)
 * through the live tracker with a simulated user. Every known move must end up on the board,
 * either followed by the tracker itself or offered as a button the user can tap, and the tracker
 * must never apply a move that was not played.
 */
class VideoPassageTest {
    private fun passage(name: String): Triple<List<String>, Map<String, List<String>>, Double> {
        val lines = javaClass.getResourceAsStream("/video/$name/frames.txt")!!.bufferedReader().readLines()
            .map { it.trim() }.filter { it.isNotEmpty() && !it.startsWith("#") }
        val meta = HashMap<String, List<String>>()
        val frames = ArrayList<String>()
        for (l in lines) {
            val parts = l.split(" ")
            when (parts[0]) {
                "fps", "jump", "truth" -> meta[parts[0]] = parts.drop(1)
                else -> frames += l
            }
        }
        return Triple(frames, meta, meta["fps"]!![0].toDouble())
    }

    @Test
    fun passage1FollowsOrOffersEveryMove() {
        val (names, meta, fps) = passage("passage1")
        val frames = names.map { n -> n to { ReplayHarness.load(javaClass.getResourceAsStream("/video/passage1/$n")!!) } }
        val truth = meta["truth"]!!
        val stats = ReplayHarness.run(frames, fps, jump = meta["jump"], truth = truth) { println(it) }
        assertEquals(0, stats.wrong, "moves applied that were not played")
        assertEquals(truth.size, stats.reached, "known moves neither followed nor offered: ${truth.drop(stats.reached)}")
        // the tracker should follow at least some of the moves by itself; the rest may need a tap
        println("passage1: followed ${stats.autoFollowed} plies by itself, ${stats.taps} taps")
    }
}
