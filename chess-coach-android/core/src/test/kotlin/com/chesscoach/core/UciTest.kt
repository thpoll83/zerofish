package com.chesscoach.core

import com.chesscoach.core.engine.UciParser
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class UciTest {
    @Test
    fun parsesInfoLines() {
        val info = UciParser.parseInfo("info depth 18 seldepth 25 multipv 1 score cp 34 nodes 1 nps 2 hashfull 3 tbhits 0 time 500 pv e2e4 e7e5 g1f3")!!
        assertEquals(18, info.depth)
        assertEquals(34, info.scoreCp)
        assertEquals(listOf("e2e4", "e7e5", "g1f3"), info.pv)
        assertEquals("+0.34", info.scoreText())
        val mate = UciParser.parseInfo("info depth 5 score mate -2 pv a1a2")!!
        assertEquals(-2, mate.scoreMate)
        assertNull(UciParser.parseInfo("info string NNUE evaluation using nn-1c0000000000.nnue"))
        assertNull(UciParser.parseInfo("info depth 1 currmove e2e4 currmovenumber 1"))
    }

    @Test
    fun parsesBestMove() {
        assertEquals("e2e4", UciParser.parseBestMove("bestmove e2e4 ponder e7e5"))
        assertNull(UciParser.parseBestMove("bestmove (none)"))
        assertNull(UciParser.parseBestMove("readyok"))
    }
}
