package com.chesscoach.app

import android.content.Context
import com.chesscoach.core.engine.EngineInfo
import com.chesscoach.core.engine.UciParser
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File
import kotlin.concurrent.thread

/**
 * Talks UCI to the Stockfish build linked into libstockfish_jni.so.
 * One engine per process: the native side redirects stdin/stdout once.
 */
class StockfishEngine(private val context: Context) {
    companion object {
        init {
            System.loadLibrary("stockfish_jni")
        }

        const val NET_BIG = "nn-1c0000000000.nnue"
        const val NET_SMALL = "nn-37f18f62d772.nnue"
    }

    private external fun nativeStart(): Boolean
    private external fun nativeWrite(line: String)
    private external fun nativeReadLine(): String?

    private val lines = Channel<String>(Channel.UNLIMITED)
    private val commandLock = Mutex()

    @Volatile
    var started = false
        private set

    @Volatile
    var version: String = ""
        private set

    class Analysis(val bestMove: String?, val lines: List<EngineInfo>)

    /** Copies the nets out of the assets, boots the engine and applies the options. Safe to call twice. */
    suspend fun start(threads: Int) = commandLock.withLock {
        if (started) return@withLock
        withContext(Dispatchers.IO) {
            val big = ensureNet(NET_BIG)
            val small = ensureNet(NET_SMALL)
            check(nativeStart()) { "Could not start Stockfish" }
            thread(name = "stockfish-reader", isDaemon = true) {
                while (true) {
                    val l = nativeReadLine() ?: break
                    lines.trySend(l)
                }
                lines.close()
            }
            version = lines.receive()
            send("uci")
            waitFor { it == "uciok" }
            send("setoption name EvalFile value ${big.absolutePath}")
            send("setoption name EvalFileSmall value ${small.absolutePath}")
            send("setoption name Threads value ${threads.coerceIn(1, 8)}")
            send("setoption name Hash value 64")
            send("setoption name MultiPV value 3")
            send("isready")
            waitFor { it == "readyok" }
            started = true
        }
    }

    /**
     * Searches [fen] for [moveTimeMs]. [onProgress] receives the current best lines (index 0 = best)
     * as the engine reports them. Returns when the engine says "bestmove".
     */
    suspend fun analyze(fen: String, moveTimeMs: Int, onProgress: (List<EngineInfo>) -> Unit = {}): Analysis =
        commandLock.withLock {
            withContext(Dispatchers.IO) {
                check(started) { "Engine not started" }
                drain()
                send("ucinewgame")
                send("isready")
                waitFor { it == "readyok" }
                send("position fen $fen")
                send("go movetime $moveTimeMs")
                val byPv = sortedMapOf<Int, EngineInfo>()
                var best: String? = null
                while (true) {
                    val line = lines.receiveCatching().getOrNull() ?: break
                    UciParser.parseBestMove(line)?.let {
                        best = it
                        break
                    }
                    if (line.startsWith("bestmove")) break
                    val info = UciParser.parseInfo(line) ?: continue
                    if (info.pv.isEmpty()) continue
                    byPv[info.multipv] = info
                    onProgress(byPv.values.toList())
                }
                Analysis(best, byPv.values.toList())
            }
        }

    /** Interrupts a running search; [analyze] then returns with the best move found so far. */
    fun stop() {
        if (started) nativeWrite("stop")
    }

    private fun send(cmd: String) = nativeWrite(cmd)

    private suspend fun waitFor(pred: (String) -> Boolean) {
        while (true) {
            val l = lines.receiveCatching().getOrNull() ?: error("Stockfish exited")
            if (pred(l)) return
        }
    }

    private fun drain() {
        while (lines.tryReceive().isSuccess) { /* discard stale output */ }
    }

    private fun ensureNet(name: String): File {
        val dir = File(context.filesDir, "nnue").apply { mkdirs() }
        val f = File(dir, name)
        if (!f.exists() || f.length() == 0L) {
            context.assets.open(name).use { input -> f.outputStream().use { input.copyTo(it) } }
        }
        return f
    }
}
