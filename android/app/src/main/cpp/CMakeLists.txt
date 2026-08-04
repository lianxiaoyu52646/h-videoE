cmake_minimum_required(VERSION 3.22.1)
project(novel_llama)

# Stub shared library so APK can optionally ship JNI symbols.
# Wire llama.cpp here later for real Qwen GGUF inference.
add_library(novel_llama SHARED novel_llama_jni.cpp)
find_library(log-lib log)
target_link_libraries(novel_llama ${log-lib})
