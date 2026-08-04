package com.videoenglish.app.novel;

import android.content.Context;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Download / locate Qwen GGUF under app filesDir/models/.
 */
public final class NovelModelStore {
    private static final String TAG = "NovelModelStore";
    public static final String DEFAULT_NAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf";

    private final Context appContext;

    public NovelModelStore(Context context) {
        this.appContext = context.getApplicationContext();
    }

    public File modelsDir() {
        File dir = new File(appContext.getFilesDir(), "models");
        if (!dir.exists()) {
            //noinspection ResultOfMethodCallIgnored
            dir.mkdirs();
        }
        return dir;
    }

    public File modelFile(String name) {
        String n = (name == null || name.trim().isEmpty()) ? DEFAULT_NAME : name.trim();
        return new File(modelsDir(), n);
    }

    public boolean isModelReady(String name) {
        File f = modelFile(name);
        return f.isFile() && f.length() > 10_000_000L; // >10MB sanity
    }

    public File ensureFromAssets(String assetPath, String name) {
        File out = modelFile(name);
        if (out.isFile() && out.length() > 10_000_000L) return out;
        try {
            InputStream in = appContext.getAssets().open(assetPath);
            File tmp = new File(out.getAbsolutePath() + ".part");
            FileOutputStream fos = new FileOutputStream(tmp);
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) >= 0) {
                fos.write(buf, 0, n);
            }
            fos.close();
            in.close();
            if (out.exists()) {
                //noinspection ResultOfMethodCallIgnored
                out.delete();
            }
            if (!tmp.renameTo(out)) {
                throw new java.io.IOException("rename failed");
            }
            return out;
        } catch (Exception e) {
            Log.w(TAG, "assets model not available: " + assetPath + " — " + e.getMessage());
            return out;
        }
    }

    public File download(String url, String name, ProgressListener listener) throws Exception {
        if (url == null || url.trim().isEmpty()) {
            throw new IllegalArgumentException("模型下载地址为空");
        }
        File out = modelFile(name);
        if (isModelReady(name)) {
            if (listener != null) listener.onProgress(100);
            return out;
        }
        File tmp = new File(out.getAbsolutePath() + ".part");
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(url.trim()).openConnection();
            conn.setConnectTimeout(20000);
            conn.setReadTimeout(120000);
            conn.setInstanceFollowRedirects(true);
            conn.connect();
            int code = conn.getResponseCode();
            if (code < 200 || code >= 300) {
                throw new java.io.IOException("HTTP " + code);
            }
            long total = conn.getContentLengthLong();
            InputStream in = conn.getInputStream();
            FileOutputStream fos = new FileOutputStream(tmp);
            byte[] buf = new byte[8192];
            long got = 0;
            int n;
            int lastPct = -1;
            while ((n = in.read(buf)) >= 0) {
                fos.write(buf, 0, n);
                got += n;
                if (listener != null && total > 0) {
                    int pct = (int) Math.min(99, (got * 100) / total);
                    if (pct != lastPct) {
                        lastPct = pct;
                        listener.onProgress(pct);
                    }
                }
            }
            fos.flush();
            fos.close();
            in.close();
            if (out.exists()) {
                //noinspection ResultOfMethodCallIgnored
                out.delete();
            }
            if (!tmp.renameTo(out)) {
                throw new java.io.IOException("rename model failed");
            }
            if (listener != null) listener.onProgress(100);
            return out;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    public interface ProgressListener {
        void onProgress(int percent);
    }
}
