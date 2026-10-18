package com.chesscoach.core.engine

/** One parsed "info" line from a UCI engine. Scores are from the side to move's point of view. */
data class EngineInfo(
    val depth: Int? = null,
    val multipv: Int = 1,
    val scoreCp: Int? = null,
    val scoreMate: Int? = null,
    val pv: List<String> = emptyList(),
) {
    /** Human text such as "+1.3" or "mate in 3", from the side to move's view. */
    fun scoreText(): String = when {
        scoreMate != null -> if (scoreMate > 0) "mate in $scoreMate" else "gets mated in ${-scoreMate}"
        scoreCp != null -> String.format("%+.2f", scoreCp / 100.0)
        else -> "?"
    }
}

object UciParser {
    /** Returns null for lines that carry no score or pv (for example "info string ..."). */
    fun parseInfo(line: String): EngineInfo? {
        val t = line.trim().split(Regex("\\s+"))
        if (t.isEmpty() || t[0] != "info") return null
        var depth: Int? = null
        var multipv = 1
        var cp: Int? = null
        var mate: Int? = null
        var pv: List<String> = emptyList()
        var i = 1
        while (i < t.size) {
            when (t[i]) {
                "depth" -> depth = t.getOrNull(i + 1)?.toIntOrNull().also { i++ }
                "multipv" -> multipv = t.getOrNull(i + 1)?.toIntOrNull()?.also { i++ } ?: 1
                "score" -> {
                    val kind = t.getOrNull(i + 1)
                    val value = t.getOrNull(i + 2)?.toIntOrNull()
                    if (kind == "cp") cp = value else if (kind == "mate") mate = value
                    i += 2
                }
                "pv" -> {
                    pv = t.subList(i + 1, t.size)
                    i = t.size
                }
                "string" -> return null
            }
            i++
        }
        if (cp == null && mate == null && pv.isEmpty()) return null
        return EngineInfo(depth, multipv, cp, mate, pv)
    }

    /** Returns the move of a "bestmove e2e4 ponder e7e5" line, or null. "(none)" yields null. */
    fun parseBestMove(line: String): String? {
        val t = line.trim().split(Regex("\\s+"))
        if (t.size < 2 || t[0] != "bestmove") return null
        return t[1].takeIf { it != "(none)" }
    }
}
