package com.videoenglish.app.novel;

import android.util.Log;

/**
 * Optional JNI bridge to libnovel_llama (llama.cpp + Qwen GGUF).
 * Safe when the .so is not packaged yet — all calls no-op / return 0.
 */
public final class LlamaNative {
    private static final String TAG = "LlamaNative";
    private static boolean attempted;
    private static boolean available;

    private LlamaNative() {}

    public static synchronized boolean ensureLoaded() {
        if (attempted) return available;
        attempted = true;
        try {
            System.loadLibrary("novel_llama");
            available = true;
            Log.i(TAG, "libnovel_llama ready");
        } catch (UnsatisfiedLinkError e) {
            available = false;
            Log.w(TAG, "Qwen native lib missing (expected until NDK build): " + e.getMessage());
        }
        return available;
    }

    public static boolean isAvailable() {
        return available;
    }

    public static long loadModel(String path) {
        if (!ensureLoaded()) return 0L;
        return nativeLoadModel(path);
    }

    public static String generate(long handle, String prompt, int maxTokens) {
        if (!available || handle == 0L) return "";
        return nativeGenerate(handle, prompt, maxTokens);
    }

    public static void unload(long handle) {
        if (!available || handle == 0L) return;
        nativeUnloadModel(handle);
    }

    private static native long nativeLoadModel(String modelPath);
    private static native String nativeGenerate(long handle, String prompt, int maxTokens);
    private static native void nativeUnloadModel(long handle);
}
