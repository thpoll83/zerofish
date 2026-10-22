package com.chesscoach.core.chess

enum class Color {
    WHITE, BLACK;

    val opposite: Color get() = if (this == WHITE) BLACK else WHITE
}

/** Piece type codes. A board cell holds +type for White, -type for Black, 0 for empty. */
object Piece {
    const val NONE = 0
    const val PAWN = 1
    const val KNIGHT = 2
    const val BISHOP = 3
    const val ROOK = 4
    const val QUEEN = 5
    const val KING = 6

    fun letter(type: Int): Char = "?PNBRQK"[type]

    fun typeOf(cell: Int): Int = if (cell < 0) -cell else cell

    fun colorOf(cell: Int): Color? = when {
        cell > 0 -> Color.WHITE
        cell < 0 -> Color.BLACK
        else -> null
    }

    /** Unicode figurine for a cell value, or ' ' for empty. */
    fun glyph(cell: Int): Char = when (cell) {
        1 -> '♙'; 2 -> '♘'; 3 -> '♗'; 4 -> '♖'; 5 -> '♕'; 6 -> '♔'
        -1 -> '♟'; -2 -> '♞'; -3 -> '♝'; -4 -> '♜'; -5 -> '♛'; -6 -> '♚'
        else -> ' '
    }

    fun fenChar(cell: Int): Char {
        val c = letter(typeOf(cell))
        return if (cell < 0) c.lowercaseChar() else c
    }

    fun fromFenChar(c: Char): Int {
        val type = "PNBRQK".indexOf(c.uppercaseChar()) + 1
        require(type > 0) { "Bad piece char '$c'" }
        return if (c.isUpperCase()) type else -type
    }
}

/** Squares are indexed 0..63 with a1 = 0, b1 = 1, ..., h8 = 63. */
object Square {
    fun of(file: Int, rank: Int): Int = rank * 8 + file
    fun file(sq: Int): Int = sq and 7
    fun rank(sq: Int): Int = sq shr 3
    fun name(sq: Int): String = "${'a' + file(sq)}${rank(sq) + 1}"
    fun parse(name: String): Int {
        require(name.length == 2) { "Bad square '$name'" }
        val f = name[0] - 'a'
        val r = name[1] - '1'
        require(f in 0..7 && r in 0..7) { "Bad square '$name'" }
        return of(f, r)
    }

    /** True for light squares (b1, d1, a2, ...). a1 is dark. */
    fun isLight(sq: Int): Boolean = (file(sq) + rank(sq)) % 2 == 1
}

data class Move(val from: Int, val to: Int, val promotion: Int = Piece.NONE) {
    fun uci(): String {
        val promo = if (promotion != Piece.NONE) Piece.letter(promotion).lowercaseChar().toString() else ""
        return Square.name(from) + Square.name(to) + promo
    }

    companion object {
        fun fromUci(s: String): Move? {
            val t = s.trim()
            if (t.length != 4 && t.length != 5) return null
            return try {
                val promo = if (t.length == 5) Piece.typeOf(Piece.fromFenChar(t[4])) else Piece.NONE
                Move(Square.parse(t.substring(0, 2)), Square.parse(t.substring(2, 4)), promo)
            } catch (e: IllegalArgumentException) {
                null
            }
        }
    }
}

enum class GameResult { ONGOING, WHITE_WINS, BLACK_WINS, DRAW }

/**
 * Immutable chess position with full rules (castling, en passant, promotion).
 * [play] returns a new board. Fifty-move and repetition draws are reported through [result]
 * only for the fifty-move rule; repetition needs history and is left to the caller.
 */
class Board private constructor(
    private val cells: IntArray,
    val sideToMove: Color,
    val castling: Int,
    val epSquare: Int,
    val halfmoveClock: Int,
    val fullmoveNumber: Int,
) {
    companion object {
        const val WK = 1
        const val WQ = 2
        const val BK = 4
        const val BQ = 8

        const val START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

        fun start(): Board = fromFen(START_FEN)

        fun fromFen(fen: String): Board {
            val parts = fen.trim().split(Regex("\\s+"))
            require(parts.size >= 2) { "FEN needs at least placement and side: '$fen'" }
            val cells = IntArray(64)
            val ranks = parts[0].split('/')
            require(ranks.size == 8) { "FEN placement needs 8 ranks" }
            for ((i, rankStr) in ranks.withIndex()) {
                val rank = 7 - i
                var file = 0
                for (c in rankStr) {
                    if (c.isDigit()) {
                        file += c - '0'
                    } else {
                        require(file < 8) { "Too many pieces on rank ${rank + 1}" }
                        cells[Square.of(file, rank)] = Piece.fromFenChar(c)
                        file++
                    }
                }
                require(file == 8) { "Rank ${rank + 1} does not have 8 files" }
            }
            val side = if (parts[1] == "w") Color.WHITE else Color.BLACK
            var castling = 0
            if (parts.size > 2 && parts[2] != "-") {
                for (c in parts[2]) castling = castling or when (c) {
                    'K' -> WK; 'Q' -> WQ; 'k' -> BK; 'q' -> BQ; else -> 0
                }
            }
            val ep = if (parts.size > 3 && parts[3] != "-") Square.parse(parts[3]) else -1
            val half = if (parts.size > 4) parts[4].toIntOrNull() ?: 0 else 0
            val full = if (parts.size > 5) parts[5].toIntOrNull() ?: 1 else 1
            return Board(cells, side, castling, ep, half, full)
        }

        private val KNIGHT_DELTAS = arrayOf(1 to 2, 2 to 1, 2 to -1, 1 to -2, -1 to -2, -2 to -1, -2 to 1, -1 to 2)
        private val KING_DELTAS = arrayOf(1 to 0, 1 to 1, 0 to 1, -1 to 1, -1 to 0, -1 to -1, 0 to -1, 1 to -1)
        private val BISHOP_DIRS = arrayOf(1 to 1, -1 to 1, -1 to -1, 1 to -1)
        private val ROOK_DIRS = arrayOf(1 to 0, 0 to 1, -1 to 0, 0 to -1)
    }

    operator fun get(sq: Int): Int = cells[sq]

    fun cellsCopy(): IntArray = cells.copyOf()

    /** How tall the piece on each square is: 0 empty, 1 a pawn, 2 a knight, bishop or rook, 3 a queen or king. */
    fun heights(): IntArray = IntArray(64) { sq ->
        when (Piece.typeOf(cells[sq])) {
            Piece.NONE -> 0
            Piece.PAWN -> 1
            Piece.QUEEN, Piece.KING -> 3
            else -> 2
        }
    }

    /** 0 = empty, 1 = white piece, 2 = black piece, for each square. */
    fun occupancy(): IntArray = IntArray(64) { sq ->
        when {
            cells[sq] > 0 -> 1
            cells[sq] < 0 -> 2
            else -> 0
        }
    }

    fun toFen(): String {
        val sb = StringBuilder()
        for (rank in 7 downTo 0) {
            var empty = 0
            for (file in 0..7) {
                val cell = cells[Square.of(file, rank)]
                if (cell == 0) {
                    empty++
                } else {
                    if (empty > 0) {
                        sb.append(empty); empty = 0
                    }
                    sb.append(Piece.fenChar(cell))
                }
            }
            if (empty > 0) sb.append(empty)
            if (rank > 0) sb.append('/')
        }
        sb.append(' ').append(if (sideToMove == Color.WHITE) 'w' else 'b').append(' ')
        if (castling == 0) sb.append('-') else {
            if (castling and WK != 0) sb.append('K')
            if (castling and WQ != 0) sb.append('Q')
            if (castling and BK != 0) sb.append('k')
            if (castling and BQ != 0) sb.append('q')
        }
        sb.append(' ').append(if (epSquare >= 0) Square.name(epSquare) else "-")
        sb.append(' ').append(halfmoveClock).append(' ').append(fullmoveNumber)
        return sb.toString()
    }

    fun kingSquare(color: Color): Int {
        val king = if (color == Color.WHITE) Piece.KING else -Piece.KING
        return cells.indexOf(king)
    }

    fun isAttacked(sq: Int, by: Color): Boolean {
        val f = Square.file(sq)
        val r = Square.rank(sq)
        val sign = if (by == Color.WHITE) 1 else -1
        // Pawns: a white pawn attacks upward, so a square is attacked by a white pawn one rank below it.
        val pawnRank = r - sign
        if (pawnRank in 0..7) {
            if (f > 0 && cells[Square.of(f - 1, pawnRank)] == sign * Piece.PAWN) return true
            if (f < 7 && cells[Square.of(f + 1, pawnRank)] == sign * Piece.PAWN) return true
        }
        for ((df, dr) in KNIGHT_DELTAS) {
            val nf = f + df; val nr = r + dr
            if (nf in 0..7 && nr in 0..7 && cells[Square.of(nf, nr)] == sign * Piece.KNIGHT) return true
        }
        for ((df, dr) in KING_DELTAS) {
            val nf = f + df; val nr = r + dr
            if (nf in 0..7 && nr in 0..7 && cells[Square.of(nf, nr)] == sign * Piece.KING) return true
        }
        if (slides(f, r, BISHOP_DIRS, sign * Piece.BISHOP, sign * Piece.QUEEN)) return true
        if (slides(f, r, ROOK_DIRS, sign * Piece.ROOK, sign * Piece.QUEEN)) return true
        return false
    }

    private fun slides(f: Int, r: Int, dirs: Array<Pair<Int, Int>>, a: Int, b: Int): Boolean {
        for ((df, dr) in dirs) {
            var nf = f + df; var nr = r + dr
            while (nf in 0..7 && nr in 0..7) {
                val c = cells[Square.of(nf, nr)]
                if (c != 0) {
                    if (c == a || c == b) return true
                    break
                }
                nf += df; nr += dr
            }
        }
        return false
    }

    fun inCheck(): Boolean {
        val k = kingSquare(sideToMove)
        return k >= 0 && isAttacked(k, sideToMove.opposite)
    }

    fun pseudoLegalMoves(): List<Move> {
        val moves = ArrayList<Move>(64)
        val sign = if (sideToMove == Color.WHITE) 1 else -1
        for (sq in 0..63) {
            val cell = cells[sq]
            if (cell == 0 || (cell > 0) != (sign > 0)) continue
            val f = Square.file(sq)
            val r = Square.rank(sq)
            when (Piece.typeOf(cell)) {
                Piece.PAWN -> genPawn(moves, sq, f, r, sign)
                Piece.KNIGHT -> genSteps(moves, sq, f, r, KNIGHT_DELTAS, sign)
                Piece.KING -> {
                    genSteps(moves, sq, f, r, KING_DELTAS, sign)
                    genCastling(moves, sq, sign)
                }
                Piece.BISHOP -> genSlides(moves, sq, f, r, BISHOP_DIRS, sign)
                Piece.ROOK -> genSlides(moves, sq, f, r, ROOK_DIRS, sign)
                Piece.QUEEN -> {
                    genSlides(moves, sq, f, r, BISHOP_DIRS, sign)
                    genSlides(moves, sq, f, r, ROOK_DIRS, sign)
                }
            }
        }
        return moves
    }

    private fun addPawnMove(moves: MutableList<Move>, from: Int, to: Int) {
        val toRank = Square.rank(to)
        if (toRank == 0 || toRank == 7) {
            moves.add(Move(from, to, Piece.QUEEN))
            moves.add(Move(from, to, Piece.ROOK))
            moves.add(Move(from, to, Piece.BISHOP))
            moves.add(Move(from, to, Piece.KNIGHT))
        } else {
            moves.add(Move(from, to))
        }
    }

    private fun genPawn(moves: MutableList<Move>, sq: Int, f: Int, r: Int, sign: Int) {
        val startRank = if (sign > 0) 1 else 6
        val r1 = r + sign
        if (r1 !in 0..7) return
        val one = Square.of(f, r1)
        if (cells[one] == 0) {
            addPawnMove(moves, sq, one)
            if (r == startRank) {
                val two = Square.of(f, r + 2 * sign)
                if (cells[two] == 0) moves.add(Move(sq, two))
            }
        }
        for (df in intArrayOf(-1, 1)) {
            val nf = f + df
            if (nf !in 0..7) continue
            val to = Square.of(nf, r1)
            val target = cells[to]
            if (target != 0 && (target > 0) != (sign > 0)) {
                addPawnMove(moves, sq, to)
            } else if (to == epSquare && target == 0) {
                moves.add(Move(sq, to))
            }
        }
    }

    private fun genSteps(moves: MutableList<Move>, sq: Int, f: Int, r: Int, deltas: Array<Pair<Int, Int>>, sign: Int) {
        for ((df, dr) in deltas) {
            val nf = f + df; val nr = r + dr
            if (nf !in 0..7 || nr !in 0..7) continue
            val to = Square.of(nf, nr)
            val target = cells[to]
            if (target == 0 || (target > 0) != (sign > 0)) moves.add(Move(sq, to))
        }
    }

    private fun genSlides(moves: MutableList<Move>, sq: Int, f: Int, r: Int, dirs: Array<Pair<Int, Int>>, sign: Int) {
        for ((df, dr) in dirs) {
            var nf = f + df; var nr = r + dr
            while (nf in 0..7 && nr in 0..7) {
                val to = Square.of(nf, nr)
                val target = cells[to]
                if (target == 0) {
                    moves.add(Move(sq, to))
                } else {
                    if ((target > 0) != (sign > 0)) moves.add(Move(sq, to))
                    break
                }
                nf += df; nr += dr
            }
        }
    }

    private fun genCastling(moves: MutableList<Move>, sq: Int, sign: Int) {
        val home = if (sign > 0) Square.of(4, 0) else Square.of(4, 7)
        if (sq != home) return
        val enemy = sideToMove.opposite
        val rank = Square.rank(sq)
        val rook = sign * Piece.ROOK
        val kingSide = if (sign > 0) WK else BK
        val queenSide = if (sign > 0) WQ else BQ
        if (isAttacked(sq, enemy)) return
        if (castling and kingSide != 0 &&
            cells[Square.of(5, rank)] == 0 && cells[Square.of(6, rank)] == 0 &&
            cells[Square.of(7, rank)] == rook &&
            !isAttacked(Square.of(5, rank), enemy) && !isAttacked(Square.of(6, rank), enemy)
        ) {
            moves.add(Move(sq, Square.of(6, rank)))
        }
        if (castling and queenSide != 0 &&
            cells[Square.of(3, rank)] == 0 && cells[Square.of(2, rank)] == 0 && cells[Square.of(1, rank)] == 0 &&
            cells[Square.of(0, rank)] == rook &&
            !isAttacked(Square.of(3, rank), enemy) && !isAttacked(Square.of(2, rank), enemy)
        ) {
            moves.add(Move(sq, Square.of(2, rank)))
        }
    }

    fun legalMoves(): List<Move> {
        val us = sideToMove
        return pseudoLegalMoves().filter { m ->
            val next = play(m)
            val k = next.kingSquare(us)
            k < 0 || !next.isAttacked(k, us.opposite)
        }
    }

    fun isLegal(move: Move): Boolean = legalMoves().contains(move)

    /** Applies [move] without legality checks and returns the resulting position. */
    fun play(move: Move): Board {
        val c = cells.copyOf()
        val piece = c[move.from]
        val sign = if (piece > 0) 1 else -1
        val type = Piece.typeOf(piece)
        val captured = c[move.to]
        var newCastling = castling
        var newEp = -1
        var halfmove = halfmoveClock + 1

        c[move.from] = 0
        c[move.to] = piece

        if (type == Piece.PAWN) {
            halfmove = 0
            if (move.to == epSquare && captured == 0 && Square.file(move.from) != Square.file(move.to)) {
                c[Square.of(Square.file(move.to), Square.rank(move.from))] = 0
            }
            if (kotlin.math.abs(Square.rank(move.to) - Square.rank(move.from)) == 2) {
                newEp = Square.of(Square.file(move.from), (Square.rank(move.from) + Square.rank(move.to)) / 2)
            }
            if (move.promotion != Piece.NONE) c[move.to] = sign * move.promotion
        }
        if (captured != 0) halfmove = 0

        if (type == Piece.KING) {
            newCastling = newCastling and (if (sign > 0) (WK or WQ).inv() else (BK or BQ).inv())
            if (kotlin.math.abs(Square.file(move.to) - Square.file(move.from)) == 2) {
                val rank = Square.rank(move.from)
                if (Square.file(move.to) == 6) {
                    c[Square.of(5, rank)] = c[Square.of(7, rank)]
                    c[Square.of(7, rank)] = 0
                } else {
                    c[Square.of(3, rank)] = c[Square.of(0, rank)]
                    c[Square.of(0, rank)] = 0
                }
            }
        }
        // Rook moves or rook captures remove the matching castling right.
        for (sq in intArrayOf(move.from, move.to)) {
            newCastling = newCastling and when (sq) {
                Square.of(0, 0) -> WQ.inv()
                Square.of(7, 0) -> WK.inv()
                Square.of(0, 7) -> BQ.inv()
                Square.of(7, 7) -> BK.inv()
                else -> -1
            }
        }
        val fullmove = if (sideToMove == Color.BLACK) fullmoveNumber + 1 else fullmoveNumber
        return Board(c, sideToMove.opposite, newCastling, newEp, halfmove, fullmove)
    }

    fun result(): GameResult {
        if (legalMoves().isEmpty()) {
            return if (inCheck()) {
                if (sideToMove == Color.WHITE) GameResult.BLACK_WINS else GameResult.WHITE_WINS
            } else GameResult.DRAW
        }
        if (halfmoveClock >= 100) return GameResult.DRAW
        return GameResult.ONGOING
    }

    /** Standard algebraic notation for a legal [move] in this position. */
    fun san(move: Move): String {
        val piece = cells[move.from]
        val type = Piece.typeOf(piece)
        val sb = StringBuilder()
        if (type == Piece.KING && kotlin.math.abs(Square.file(move.to) - Square.file(move.from)) == 2) {
            sb.append(if (Square.file(move.to) == 6) "O-O" else "O-O-O")
        } else {
            val isCapture = cells[move.to] != 0 ||
                (type == Piece.PAWN && Square.file(move.from) != Square.file(move.to))
            if (type == Piece.PAWN) {
                if (isCapture) sb.append('a' + Square.file(move.from))
            } else {
                sb.append(Piece.letter(type))
                val others = legalMoves().filter {
                    it.to == move.to && it.from != move.from && Piece.typeOf(cells[it.from]) == type
                }
                if (others.isNotEmpty()) {
                    val sameFile = others.any { Square.file(it.from) == Square.file(move.from) }
                    val sameRank = others.any { Square.rank(it.from) == Square.rank(move.from) }
                    if (!sameFile) sb.append('a' + Square.file(move.from))
                    else if (!sameRank) sb.append('1' + Square.rank(move.from))
                    else sb.append(Square.name(move.from))
                }
            }
            if (isCapture) sb.append('x')
            sb.append(Square.name(move.to))
            if (move.promotion != Piece.NONE) sb.append('=').append(Piece.letter(move.promotion))
        }
        val next = play(move)
        if (next.inCheck()) sb.append(if (next.legalMoves().isEmpty()) '#' else '+')
        return sb.toString()
    }

    /** Finds the legal move written as SAN (with or without check marks) or as a UCI string. */
    fun parseMove(text: String): Move? {
        val t = text.trim().replace("+", "").replace("#", "").replace("x", "").replace("=", "")
        if (t.isEmpty()) return null
        Move.fromUci(text.trim())?.let { if (isLegal(it)) return it }
        val legal = legalMoves()
        val sb = StringBuilder()
        for (m in legal) {
            sb.setLength(0)
            val s = san(m).replace("+", "").replace("#", "").replace("x", "").replace("=", "")
            if (s == t || (t.startsWith("0-0") && s == t.replace('0', 'O'))) return m
        }
        return null
    }

    override fun equals(other: Any?): Boolean = other is Board && other.toFen() == toFen()
    override fun hashCode(): Int = toFen().hashCode()
    override fun toString(): String = toFen()
}
