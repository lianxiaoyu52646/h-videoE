package com.videoenglish.app.novel;

import android.content.Context;
import android.util.Log;

import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.nl.translate.Translator;

import java.io.File;
import java.util.concurrent.TimeUnit;

/**
 * On-device novel translator.
 * Prefers Qwen GGUF via JNI when model+native are ready;
 * otherwise falls back to ML Kit so the claim/submit loop still works.
 */
public final class NovelTranslator {
    private static final String TAG = "NovelTranslator";

    private final NovelModelStore store;
    private volatile long nativeHandle = 0L;
    private volatile String engineName = "none";
    private volatile String modelName = NovelModelStore.DEFAULT_NAME;
    private Translator mlKitFallback;

    public NovelTranslator(Context context) {
        this.store = new NovelModelStore(context.getApplicationContext());
    }

    public void setMlKitFallback(Translator translator) {
        this.mlKitFallback = translator;
        refreshEngineName();
    }

    public String getEngineName() {
        return engineName;
    }

    public String getModelName() {
        return modelName;
    }

    public boolean isQwenReady() {
        return nativeHandle != 0L && store.isModelReady(modelName);
    }

    public boolean isReady() {
        return isQwenReady() || mlKitFallback != null;
    }

    public NovelModelStore getStore() {
        return store;
    }

    public synchronized void prepare(String preferredModelName) {
        if (preferredModelName != null && !preferredModelName.trim().isEmpty()) {
            modelName = preferredModelName.trim();
        }
        if (!store.isModelReady(modelName)) {
            store.ensureFromAssets("models/" + modelName, modelName);
        }
        tryLoadNative();
        refreshEngineName();
    }

    public synchronized void loadDownloadedModel() {
        tryLoadNative();
        refreshEngineName();
    }

    private void refreshEngineName() {
        if (isQwenReady()) {
            engineName = "qwen_local";
        } else if (mlKitFallback != null) {
            engineName = "mlkit_fallback";
        } else {
            engineName = "none";
        }
    }

    private void tryLoadNative() {
        if (!store.isModelReady(modelName)) {
            Log.i(TAG, "GGUF not ready: " + modelName);
            return;
        }
        if (!LlamaNative.ensureLoaded()) return;
        if (nativeHandle != 0L) return;
        File f = store.modelFile(modelName);
        try {
            nativeHandle = LlamaNative.loadModel(f.getAbsolutePath());
            if (nativeHandle != 0L) {
                Log.i(TAG, "Qwen model loaded: " + f.getName());
            }
        } catch (Throwable t) {
            Log.e(TAG, "nativeLoadModel failed", t);
            nativeHandle = 0L;
        }
    }

    /** Translate one novel paragraph. Blocking — call off UI thread. */
    public String translateParagraph(String english) {
        String en = english == null ? "" : english.trim();
        if (en.isEmpty()) {
            Log.w(TAG, "translateParagraph empty input");
            return "";
        }
        Log.i(TAG, "translate start engine=" + engineName
                + " qwenReady=" + isQwenReady()
                + " enLen=" + en.length()
                + " en=" + en.substring(0, Math.min(80, en.length())));

        if (isQwenReady()) {
            try {
                String prompt = NovelPrompt.buildUserPrompt(en);
                Log.i(TAG, "qwen promptLen=" + prompt.length());
                String raw = LlamaNative.generate(nativeHandle, prompt, 512);
                String zh = NovelPrompt.stripModelNoise(raw);
                Log.i(TAG, "qwen rawLen=" + (raw == null ? 0 : raw.length())
                        + " zhLen=" + zh.length()
                        + " zh=" + zh.substring(0, Math.min(60, zh.length())));
                if (zh.length() > 0) {
                    engineName = "qwen_local";
                    return zh;
                }
                Log.w(TAG, "qwen empty output, fallback");
            } catch (Throwable t) {
                Log.e(TAG, "Qwen generate failed, fallback", t);
            }
        }

        if (mlKitFallback != null) {
            try {
                String zh = Tasks.await(mlKitFallback.translate(en), 60, TimeUnit.SECONDS);
                engineName = "mlkit_fallback";
                String out = zh == null ? "" : zh.trim();
                Log.i(TAG, "mlkit zhLen=" + out.length()
                        + " zh=" + out.substring(0, Math.min(60, out.length())));
                return out;
            } catch (Exception e) {
                Log.e(TAG, "ML Kit fallback failed", e);
            }
        }
        Log.e(TAG, "translate failed: no engine output");
        return "";
    }

    public synchronized void release() {
        if (nativeHandle != 0L) {
            try {
                LlamaNative.unload(nativeHandle);
            } catch (Throwable ignored) {
            }
            nativeHandle = 0L;
        }
    }
}
