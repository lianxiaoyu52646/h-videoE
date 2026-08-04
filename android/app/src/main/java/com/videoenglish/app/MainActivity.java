package com.videoenglish.app;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.KeyEvent;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.util.Log;
import android.speech.tts.TextToSpeech;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.FileProvider;

import com.google.mlkit.nl.translate.Translation;
import com.google.mlkit.nl.translate.Translator;
import com.google.mlkit.nl.translate.TranslatorOptions;
import com.google.mlkit.nl.translate.TranslateLanguage;
import com.google.android.gms.tasks.OnSuccessListener;
import com.google.android.gms.tasks.OnFailureListener;

import com.videoenglish.app.novel.NovelModelStore;
import com.videoenglish.app.novel.NovelTranslator;

public class MainActivity extends AppCompatActivity {

    private static final String TAG = "MainActivity";
    private static final String APP_ENTRY_URL = "https://wordpop-xyh7.onrender.com/app";

    private WebView webView;
    private DictionaryDatabaseHelper dbHelper;
    private TextToSpeech tts;
    private boolean ttsReady = false;
    /** False until TextToSpeech.onInit finishes (success or failure). */
    private boolean ttsInitDone = false;
    private final java.util.ArrayDeque<String> pendingSpeak = new java.util.ArrayDeque<>();
    private Translator enToZhTranslator;
    private boolean translatorReady = false;
    private NovelTranslator novelTranslator;
    private final ExecutorService bg = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private volatile boolean apkDownloading = false;
    private volatile boolean modelDownloading = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        dbHelper = new DictionaryDatabaseHelper(this);
        Log.d(TAG, "Dictionary ready: " + dbHelper.isReady() + ", word count: " + dbHelper.getWordCount());

        novelTranslator = new NovelTranslator(this);
        novelTranslator.prepare(NovelModelStore.DEFAULT_NAME);
        initTranslator();

        webView = findViewById(R.id.webView);

        WebSettings webSettings = webView.getSettings();
        webSettings.setJavaScriptEnabled(true);
        webSettings.setDomStorageEnabled(true);
        webSettings.setDatabaseEnabled(true);
        webSettings.setAllowFileAccess(true);
        webSettings.setAllowContentAccess(true);
        webSettings.setLoadWithOverviewMode(true);
        webSettings.setUseWideViewPort(true);
        webSettings.setSupportZoom(true);
        webSettings.setBuiltInZoomControls(false);
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.JELLY_BEAN_MR1) {
            webSettings.setMediaPlaybackRequiresUserGesture(false);
        }

        webView.addJavascriptInterface(new DictionaryBridge(), "AndroidDictionary");

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                view.loadUrl(url);
                return true;
            }
        });

        webView.loadUrl(APP_ENTRY_URL);

        tts = new TextToSpeech(this, new TextToSpeech.OnInitListener() {
            @Override
            public void onInit(int status) {
                ttsInitDone = true;
                if (status == TextToSpeech.SUCCESS) {
                    int result = tts.setLanguage(Locale.US);
                    if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                        result = tts.setLanguage(Locale.ENGLISH);
                    }
                    if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                        ttsReady = false;
                        pendingSpeak.clear();
                        Log.e(TAG, "English TTS not supported");
                    } else {
                        ttsReady = true;
                        Log.d(TAG, "TTS initialized successfully");
                        flushPendingSpeak();
                    }
                } else {
                    ttsReady = false;
                    pendingSpeak.clear();
                    Log.e(TAG, "TTS initialization failed");
                }
            }
        });
    }

    private void speakNow(String word) {
        if (tts == null || word == null || word.isEmpty()) return;
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.LOLLIPOP) {
            tts.speak(word, TextToSpeech.QUEUE_FLUSH, null, "speak_" + System.currentTimeMillis());
        } else {
            tts.speak(word, TextToSpeech.QUEUE_FLUSH, null);
        }
    }

    private void flushPendingSpeak() {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                if (!ttsReady || tts == null) return;
                while (!pendingSpeak.isEmpty()) {
                    String next = pendingSpeak.pollFirst();
                    if (next != null && !next.isEmpty()) {
                        if (pendingSpeak.isEmpty()) {
                            speakNow(next);
                        }
                    }
                }
            }
        });
    }

    private void toastOnUi(final String msg) {
        mainHandler.post(new Runnable() {
            @Override
            public void run() {
                Toast.makeText(MainActivity.this, msg, Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void clearCacheAndReloadInternal() {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                try {
                    webView.clearCache(true);
                    webView.clearHistory();
                } catch (Exception e) {
                    Log.w(TAG, "clearCache failed: " + e.getMessage());
                }
                String url = APP_ENTRY_URL + (APP_ENTRY_URL.contains("?") ? "&" : "?") + "_=" + System.currentTimeMillis();
                webView.loadUrl(url);
            }
        });
    }

    private boolean canInstallPackages() {
        if (android.os.Build.VERSION.SDK_INT < android.os.Build.VERSION_CODES.O) {
            return true;
        }
        return getPackageManager().canRequestPackageInstalls();
    }

    private void openUnknownSourcesSettings() {
        try {
            Intent intent = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES);
            intent.setData(Uri.parse("package:" + getPackageName()));
            startActivity(intent);
        } catch (Exception e) {
            Intent intent = new Intent(Settings.ACTION_SECURITY_SETTINGS);
            startActivity(intent);
        }
    }

    private void installLocalApk(File apk) {
        if (apk == null || !apk.exists()) {
            toastOnUi("安装包不存在");
            return;
        }
        if (!canInstallPackages()) {
            toastOnUi("请先允许安装未知应用，然后再次点击更新");
            openUnknownSourcesSettings();
            return;
        }
        try {
            Uri uri = FileProvider.getUriForFile(
                    this,
                    getPackageName() + ".fileprovider",
                    apk
            );
            Intent intent = new Intent(Intent.ACTION_VIEW);
            intent.setDataAndType(uri, "application/vnd.android.package-archive");
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(intent);
        } catch (Exception e) {
            Log.e(TAG, "install apk failed", e);
            toastOnUi("无法打开安装页面");
        }
    }

    private void downloadAndInstallApk(final String apkUrl) {
        if (apkUrl == null || apkUrl.trim().isEmpty()) {
            toastOnUi("没有安装包地址");
            return;
        }
        if (apkDownloading) {
            toastOnUi("正在下载，请稍候");
            return;
        }
        apkDownloading = true;
        toastOnUi("正在下载更新…");
        bg.execute(new Runnable() {
            @Override
            public void run() {
                final File out = new File(getCacheDir(), "wordpop-update.apk");
                HttpURLConnection conn = null;
                try {
                    if (out.exists()) {
                        //noinspection ResultOfMethodCallIgnored
                        out.delete();
                    }
                    URL url = new URL(apkUrl.trim());
                    conn = (HttpURLConnection) url.openConnection();
                    conn.setConnectTimeout(20000);
                    conn.setReadTimeout(60000);
                    conn.setInstanceFollowRedirects(true);
                    conn.connect();
                    int code = conn.getResponseCode();
                    if (code < 200 || code >= 300) {
                        throw new IOException("HTTP " + code);
                    }
                    InputStream in = conn.getInputStream();
                    FileOutputStream fos = new FileOutputStream(out);
                    byte[] buf = new byte[8192];
                    int n;
                    while ((n = in.read(buf)) >= 0) {
                        fos.write(buf, 0, n);
                    }
                    fos.flush();
                    fos.close();
                    in.close();
                    mainHandler.post(new Runnable() {
                        @Override
                        public void run() {
                            apkDownloading = false;
                            toastOnUi("下载完成，请确认安装");
                            installLocalApk(out);
                        }
                    });
                } catch (Exception e) {
                    Log.e(TAG, "download apk failed", e);
                    apkDownloading = false;
                    toastOnUi("下载失败，请检查网络");
                } finally {
                    if (conn != null) conn.disconnect();
                }
            }
        });
    }

    private void initTranslator() {
        TranslatorOptions options = new TranslatorOptions.Builder()
                .setSourceLanguage(TranslateLanguage.ENGLISH)
                .setTargetLanguage(TranslateLanguage.CHINESE)
                .build();
        enToZhTranslator = Translation.getClient(options);

        enToZhTranslator.downloadModelIfNeeded()
                .addOnSuccessListener(new OnSuccessListener<Void>() {
                    @Override
                    public void onSuccess(Void aVoid) {
                        translatorReady = true;
                        Log.d(TAG, "ML Kit translator ready");
                        if (novelTranslator != null) {
                            novelTranslator.setMlKitFallback(enToZhTranslator);
                            novelTranslator.prepare(NovelModelStore.DEFAULT_NAME);
                        }
                        notifyTranslatorReady();
                    }
                })
                .addOnFailureListener(new OnFailureListener() {
                    @Override
                    public void onFailure(Exception e) {
                        Log.e(TAG, "ML Kit translator download failed: " + e.getMessage());
                    }
                });
    }

    private void notifyTranslatorReady() {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                webView.evaluateJavascript("if(window.onTranslatorReady)window.onTranslatorReady();", null);
            }
        });
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if ((keyCode == KeyEvent.KEYCODE_BACK) && webView.canGoBack()) {
            webView.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        bg.shutdownNow();
        if (dbHelper != null) {
            dbHelper.closeDatabase();
        }
        if (tts != null) {
            tts.stop();
            tts.shutdown();
        }
        if (novelTranslator != null) {
            novelTranslator.release();
        }
        if (enToZhTranslator != null) {
            enToZhTranslator.close();
        }
    }

    private void notifyNovelCallback(final String callbackId, final String resultJson) {
        if (callbackId == null || callbackId.isEmpty()) return;
        final String safeId = callbackId.replace("\\", "\\\\").replace("'", "\\'");
        final String payload = resultJson == null ? "null" : resultJson;
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                webView.evaluateJavascript(
                        "try{var cb=window.novelTranslateCallbacks&&window.novelTranslateCallbacks.get('"
                                + safeId + "');if(cb)cb(" + payload + ");}catch(e){}",
                        null
                );
            }
        });
    }

    private static String jsonEscape(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }

    public class DictionaryBridge {

        @JavascriptInterface
        public String lookupWord(String word) {
            return dbHelper.lookupWord(word);
        }

        @JavascriptInterface
        public String fuzzySearch(String keyword) {
            return dbHelper.fuzzySearch(keyword);
        }

        @JavascriptInterface
        public boolean isDictionaryReady() {
            return dbHelper.isReady();
        }

        @JavascriptInterface
        public int getWordCount() {
            return dbHelper.getWordCount();
        }

        @JavascriptInterface
        public int getVersionCode() {
            return BuildConfig.VERSION_CODE;
        }

        @JavascriptInterface
        public String getVersionName() {
            return BuildConfig.VERSION_NAME;
        }

        @JavascriptInterface
        public void clearCacheAndReload() {
            clearCacheAndReloadInternal();
        }

        @JavascriptInterface
        public void installApkFromUrl(String url) {
            downloadAndInstallApk(url);
        }

        @JavascriptInterface
        public void speak(String word) {
            if (word == null || word.isEmpty()) return;
            final String text = word.trim();
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    if (ttsReady && tts != null) {
                        pendingSpeak.clear();
                        speakNow(text);
                        return;
                    }
                    if (!ttsInitDone) {
                        pendingSpeak.clear();
                        pendingSpeak.addLast(text);
                        Log.w("DictionaryBridge", "TTS not ready, queued speak: " + text);
                        return;
                    }
                    // Native TTS failed permanently → fall back to same-origin /api/tts in JS.
                    Log.w("DictionaryBridge", "TTS unavailable, JS fallback: " + text);
                    String escaped = text
                            .replace("\\", "\\\\")
                            .replace("'", "\\'")
                            .replace("\n", " ")
                            .replace("\r", " ");
                    webView.evaluateJavascript(
                            "try{if(window.__wpSpeakFallback)window.__wpSpeakFallback('" + escaped + "');}catch(e){}",
                            null
                    );
                }
            });
        }

        @JavascriptInterface
        public boolean isTtsAvailable() {
            // Always true from JS perspective: speak() will queue or JS-fallback.
            return true;
        }

        @JavascriptInterface
        public String readAssetFile(String filePath) {
            try {
                InputStream is = getAssets().open(filePath);
                int size = is.available();
                byte[] buffer = new byte[size];
                is.read(buffer);
                is.close();
                return new String(buffer, "UTF-8");
            } catch (IOException e) {
                Log.e("DictionaryBridge", "Failed to read asset file: " + e.getMessage());
                return null;
            }
        }

        @JavascriptInterface
        public boolean isTranslatorReady() {
            return translatorReady;
        }

        @JavascriptInterface
        public void translateText(final String text, final String callbackId) {
            if (!translatorReady || enToZhTranslator == null) {
                notifyTranslationResult(callbackId, "");
                return;
            }

            enToZhTranslator.translate(text)
                    .addOnSuccessListener(new OnSuccessListener<String>() {
                        @Override
                        public void onSuccess(String translatedText) {
                            notifyTranslationResult(callbackId, translatedText);
                        }
                    })
                    .addOnFailureListener(new OnFailureListener() {
                        @Override
                        public void onFailure(Exception e) {
                            Log.e("DictionaryBridge", "Translate failed: " + e.getMessage());
                            notifyTranslationResult(callbackId, "");
                        }
                    });
        }

        /** Reading-module only: true if Qwen or ML Kit fallback can translate. */
        @JavascriptInterface
        public boolean isNovelTranslatorReady() {
            return novelTranslator != null && novelTranslator.isReady();
        }

        @JavascriptInterface
        public boolean isNovelQwenReady() {
            return novelTranslator != null && novelTranslator.isQwenReady();
        }

        @JavascriptInterface
        public String getNovelEngineName() {
            return novelTranslator == null ? "none" : novelTranslator.getEngineName();
        }

        @JavascriptInterface
        public boolean isNovelModelFileReady(String name) {
            if (novelTranslator == null) return false;
            String n = (name == null || name.isEmpty()) ? NovelModelStore.DEFAULT_NAME : name;
            return novelTranslator.getStore().isModelReady(n);
        }

        /**
         * Download Qwen GGUF then load. Callback JSON:
         * {ok, percent?, error?, engine?}
         */
        @JavascriptInterface
        public void downloadNovelModel(final String url, final String name, final String callbackId) {
            if (modelDownloading) {
                notifyNovelCallback(callbackId, "{\"ok\":false,\"error\":\"downloading\"}");
                return;
            }
            modelDownloading = true;
            bg.execute(new Runnable() {
                @Override
                public void run() {
                    try {
                        String n = (name == null || name.isEmpty()) ? NovelModelStore.DEFAULT_NAME : name;
                        if (url != null && url.trim().length() > 0) {
                            novelTranslator.getStore().download(url.trim(), n, new NovelModelStore.ProgressListener() {
                                @Override
                                public void onProgress(int percent) {
                                    notifyNovelCallback(callbackId,
                                            "{\"ok\":true,\"phase\":\"download\",\"percent\":" + percent + "}");
                                }
                            });
                        }
                        novelTranslator.prepare(n);
                        novelTranslator.loadDownloadedModel();
                        String engine = novelTranslator.getEngineName();
                        notifyNovelCallback(callbackId,
                                "{\"ok\":true,\"phase\":\"ready\",\"percent\":100,\"engine\":\""
                                        + jsonEscape(engine) + "\",\"qwen\":"
                                        + (novelTranslator.isQwenReady() ? "true" : "false") + "}");
                    } catch (Exception e) {
                        Log.e(TAG, "downloadNovelModel failed", e);
                        // Still try ML Kit path
                        if (novelTranslator != null) {
                            novelTranslator.prepare(name);
                        }
                        notifyNovelCallback(callbackId,
                                "{\"ok\":false,\"error\":\"" + jsonEscape(e.getMessage()) + "\",\"engine\":\""
                                        + jsonEscape(novelTranslator == null ? "none" : novelTranslator.getEngineName())
                                        + "\"}");
                    } finally {
                        modelDownloading = false;
                    }
                }
            });
        }

        /** Translate one novel paragraph (blocking on bg thread). */
        @JavascriptInterface
        public void translateNovel(final String text, final String callbackId) {
            bg.execute(new Runnable() {
                @Override
                public void run() {
                    try {
                        if (novelTranslator == null) {
                            notifyNovelCallback(callbackId, "{\"ok\":false,\"zh\":\"\",\"engine\":\"none\"}");
                            return;
                        }
                        String zh = novelTranslator.translateParagraph(text);
                        String engine = novelTranslator.getEngineName();
                        notifyNovelCallback(callbackId,
                                "{\"ok\":" + (zh != null && zh.length() > 0) + ",\"zh\":\""
                                        + jsonEscape(zh) + "\",\"engine\":\"" + jsonEscape(engine) + "\"}");
                    } catch (Exception e) {
                        Log.e(TAG, "translateNovel failed", e);
                        notifyNovelCallback(callbackId,
                                "{\"ok\":false,\"zh\":\"\",\"error\":\"" + jsonEscape(e.getMessage()) + "\"}");
                    }
                }
            });
        }
    }

    private void notifyTranslationResult(final String callbackId, final String result) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                String escaped = result.replace("\\", "\\\\")
                        .replace("'", "\\'")
                        .replace("\n", "\\n")
                        .replace("\r", "\\r");
                String js = "try { if(window.translationCallbacks && window.translationCallbacks.has('" + callbackId + "')) { window.translationCallbacks.get('" + callbackId + "')('" + escaped + "'); window.translationCallbacks.delete('" + callbackId + "'); } } catch(e) { console.error('Callback error:', e); }";
                webView.evaluateJavascript(js, null);
            }
        });
    }
}
