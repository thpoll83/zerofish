cmake_minimum_required(VERSION 3.22)
project(chesscoach LANGUAGES CXX)

# Official Stockfish sources, fetched at configure time. Change the tag to build another release;
# the NNUE file names in app/build.gradle.kts must then match that release's evaluate.h.
set(STOCKFISH_TAG "sf_17.1" CACHE STRING "Stockfish git tag to build")
option(STOCKFISH_DOTPROD "Use ARMv8.2 dot-product instructions (faster, needs a 2018+ SoC)" OFF)

include(FetchContent)
if(POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW)
endif()
FetchContent_Declare(
    stockfish
    URL "https://github.com/official-stockfish/Stockfish/archive/refs/tags/${STOCKFISH_TAG}.tar.gz"
)
FetchContent_MakeAvailable(stockfish)
set(SF_SRC "${stockfish_SOURCE_DIR}/src")

file(GLOB_RECURSE SF_SOURCES CONFIGURE_DEPENDS "${SF_SRC}/*.cpp")

add_library(stockfish_jni SHARED stockfish_jni.cpp ${SF_SOURCES})

target_include_directories(stockfish_jni PRIVATE "${SF_SRC}")
target_compile_features(stockfish_jni PRIVATE cxx_std_17)
target_compile_options(stockfish_jni PRIVATE -O3 -fno-exceptions -Wno-unused-parameter -Wno-deprecated-declarations)
# Same defines as `make ARCH=armv8 COMP=ndk`, minus the embedded nets: the app loads them from assets.
target_compile_definitions(stockfish_jni PRIVATE NDEBUG IS_64BIT USE_POPCNT USE_PTHREADS USE_NEON=8 NNUE_EMBEDDING_OFF)
if(STOCKFISH_DOTPROD)
    target_compile_options(stockfish_jni PRIVATE -march=armv8.2-a+dotprod)
    target_compile_definitions(stockfish_jni PRIVATE USE_NEON_DOTPROD)
endif()
# Stockfish's main() becomes stockfish_main() so the JNI bridge can run it on a thread.
set_source_files_properties("${SF_SRC}/main.cpp" PROPERTIES COMPILE_DEFINITIONS "main=stockfish_main")

find_library(log-lib log)
target_link_libraries(stockfish_jni ${log-lib})
