package com.chesscoach.core

import com.chesscoach.core.chess.Board
import com.chesscoach.core.chess.Move
import com.chesscoach.core.chess.GameResult
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class ChessTest {
    private fun perft(b: Board, depth: Int): Long {
        if (depth == 0) return 1
        val moves = b.legalMoves()
        if (depth == 1) return moves.size.toLong()
        var n = 0L
        for (m in moves) n += perft(b.play(m), depth - 1)
        return n
    }

    @Test
    fun perftStartPosition() {
        val b = Board.start()
        assertEquals(20, perft(b, 1))
        assertEquals(400, perft(b, 2))
        assertEquals(8902, perft(b, 3))
        assertEquals(197281, perft(b, 4))
    }

    @Test
    fun perftKiwipete() {
        val b = Board.fromFen("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
        assertEquals(48, perft(b, 1))
        assertEquals(2039, perft(b, 2))
        assertEquals(97862, perft(b, 3))
    }

    @Test
    fun perftPosition3EnPassantAndChecks() {
        val b = Board.fromFen("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1")
        assertEquals(14, perft(b, 1))
        assertEquals(191, perft(b, 2))
        assertEquals(2812, perft(b, 3))
        assertEquals(43238, perft(b, 4))
    }

    @Test
    fun perftPosition4Promotions() {
        val b = Board.fromFen("r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1")
        assertEquals(6, perft(b, 1))
        assertEquals(264, perft(b, 2))
        assertEquals(9467, perft(b, 3))
    }

    @Test
    fun fenRoundTrip() {
        val fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
        assertEquals(fen, Board.fromFen(fen).toFen())
        assertEquals(Board.START_FEN, Board.start().toFen())
    }

    @Test
    fun sanAndParse() {
        var b = Board.start()
        val e4 = b.parseMove("e4")!!
        assertEquals("e2e4", e4.uci())
        b = b.play(e4)
        b = b.play(b.parseMove("e5")!!)
        val nf3 = b.parseMove("Nf3")!!
        assertEquals("Nf3", b.san(nf3))
        b = b.play(nf3)
        b = b.play(b.parseMove("Nc6")!!)
        b = b.play(b.parseMove("Bc4")!!)
        b = b.play(b.parseMove("Nf6")!!)
        val castle = b.parseMove("O-O")!!
        assertEquals("e1g1", castle.uci())
        assertEquals("O-O", b.san(castle))
        b = b.play(castle)
        assertEquals(4, b[5]) // rook on f1 after castling
        assertEquals(6, b[6]) // king on g1
    }

    @Test
    fun scholarsMateIsCheckmate() {
        var b = Board.start()
        for (m in listOf("e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#")) {
            val mv = b.parseMove(m)
            assertNotNull(mv, "move $m")
            if (m == "Qxf7#") assertEquals("Qxf7#", b.san(mv))
            b = b.play(mv)
        }
        assertEquals(GameResult.WHITE_WINS, b.result())
    }

    @Test
    fun disambiguationAndPromotion() {
        val b = Board.fromFen("4k3/1P6/8/8/8/8/4K3/R6R w - - 0 1")
        assertEquals("Rad1", b.san(Move.fromUci("a1d1")!!))
        assertEquals("Rhd1", b.san(Move.fromUci("h1d1")!!))
        assertEquals("b8=Q+", b.san(Move.fromUci("b7b8q")!!))
        val c = Board.fromFen("4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1")
        assertTrue(c.isLegal(Move.fromUci("e1c1")!!))
        assertEquals("O-O-O", c.san(Move.fromUci("e1c1")!!))
        assertEquals("O-O", c.san(Move.fromUci("e1g1")!!))
    }
}
