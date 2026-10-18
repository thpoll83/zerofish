// JNI bridge: runs the unmodified Stockfish UCI loop on a background thread and talks to it
// over two pipes that replace the process's stdin and stdout. The app never uses stdio itself.
#include <jni.h>
#include <unistd.h>
#include <android/log.h>

#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>

int stockfish_main(int argc, char* argv[]);

namespace {

int gToEngine[2] = {-1, -1};    // app writes [1], engine reads [0] as stdin
int gFromEngine[2] = {-1, -1};  // engine writes [1] as stdout, app reads [0]
FILE* gReader = nullptr;
std::mutex gWriteMutex;
bool gStarted = false;

void logw(const char* msg) { __android_log_print(ANDROID_LOG_WARN, "StockfishJNI", "%s", msg); }

}  // namespace

extern "C" JNIEXPORT jboolean JNICALL
Java_com_chesscoach_app_StockfishEngine_nativeStart(JNIEnv*, jobject) {
    if (gStarted) return JNI_TRUE;
    if (pipe(gToEngine) != 0 || pipe(gFromEngine) != 0) {
        logw("pipe() failed");
        return JNI_FALSE;
    }
    if (dup2(gToEngine[0], STDIN_FILENO) < 0 || dup2(gFromEngine[1], STDOUT_FILENO) < 0) {
        logw("dup2() failed");
        return JNI_FALSE;
    }
    close(gToEngine[0]);
    close(gFromEngine[1]);
    setvbuf(stdout, nullptr, _IOLBF, 0);
    gReader = fdopen(gFromEngine[0], "r");
    if (!gReader) {
        logw("fdopen() failed");
        return JNI_FALSE;
    }
    std::thread([] {
        char name[] = "stockfish";
        char* argv[] = {name, nullptr};
        stockfish_main(1, argv);
        fflush(stdout);
        close(STDOUT_FILENO);  // lets the reader see EOF after "quit"
    }).detach();
    gStarted = true;
    return JNI_TRUE;
}

extern "C" JNIEXPORT void JNICALL
Java_com_chesscoach_app_StockfishEngine_nativeWrite(JNIEnv* env, jobject, jstring line) {
    if (!gStarted) return;
    const char* chars = env->GetStringUTFChars(line, nullptr);
    std::string buf(chars);
    env->ReleaseStringUTFChars(line, chars);
    buf.push_back('\n');
    std::lock_guard<std::mutex> lock(gWriteMutex);
    size_t off = 0;
    while (off < buf.size()) {
        ssize_t n = write(gToEngine[1], buf.data() + off, buf.size() - off);
        if (n <= 0) {
            logw("write() to engine failed");
            return;
        }
        off += static_cast<size_t>(n);
    }
}

// Blocks until a full line is available. Returns null at EOF.
extern "C" JNIEXPORT jstring JNICALL
Java_com_chesscoach_app_StockfishEngine_nativeReadLine(JNIEnv* env, jobject) {
    if (!gReader) return nullptr;
    char* line = nullptr;
    size_t cap = 0;
    ssize_t n = getline(&line, &cap, gReader);
    if (n < 0) {
        free(line);
        return nullptr;
    }
    while (n > 0 && (line[n - 1] == '\n' || line[n - 1] == '\r')) line[--n] = '\0';
    jstring result = env->NewStringUTF(line);
    free(line);
    return result;
}
