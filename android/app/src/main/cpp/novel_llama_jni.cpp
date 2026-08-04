#include <jni.h>
#include <string>

/*
 * Stub JNI for libnovel_llama.
 * Replace with real llama.cpp load/generate when NDK module is enabled.
 * Until then the Java side uses ML Kit fallback for the reading persist loop.
 */

extern "C" {

JNIEXPORT jlong JNICALL
Java_com_videoenglish_app_novel_LlamaNative_nativeLoadModel(JNIEnv *, jclass, jstring) {
    return 0; // 0 = not loaded (stub)
}

JNIEXPORT jstring JNICALL
Java_com_videoenglish_app_novel_LlamaNative_nativeGenerate(JNIEnv *env, jclass, jlong, jstring, jint) {
    return env->NewStringUTF("");
}

JNIEXPORT void JNICALL
Java_com_videoenglish_app_novel_LlamaNative_nativeUnloadModel(JNIEnv *, jclass, jlong) {
}

}
