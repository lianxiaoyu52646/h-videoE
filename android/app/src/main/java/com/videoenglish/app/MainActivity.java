package com.videoenglish.app;

import android.os.Bundle;
import android.view.KeyEvent;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.util.Log;
import android.speech.tts.TextToSpeech;
import java.util.Locale;
import java.io.InputStream;
import java.io.IOException;
import androidx.appcompat.app.AppCompatActivity;

import com.google.mlkit.nl.translate.Translation;
import com.google.mlkit.nl.translate.Translator;
import com.google.mlkit.nl.translate.TranslatorOptions;
import com.google.mlkit.nl.translate.TranslateLanguage;
import com.google.android.gms.tasks.OnSuccessListener;
import com.google.android.gms.tasks.OnFailureListener;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private DictionaryDatabaseHelper dbHelper;
    private TextToSpeech tts;
    private Translator enToZhTranslator;
    private boolean translatorReady = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        dbHelper = new DictionaryDatabaseHelper(this);
        Log.d("MainActivity", "Dictionary ready: " + dbHelper.isReady() + ", word count: " + dbHelper.getWordCount());

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

        webView.addJavascriptInterface(new DictionaryBridge(), "AndroidDictionary");

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                view.loadUrl(url);
                return true;
            }
        });

        webView.loadUrl("file:///android_asset/index.html");
        
        tts = new TextToSpeech(this, new TextToSpeech.OnInitListener() {
            @Override
            public void onInit(int status) {
                if (status == TextToSpeech.SUCCESS) {
                    int result = tts.setLanguage(Locale.US);
                    if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                        Log.e("MainActivity", "English TTS not supported");
                    } else {
                        Log.d("MainActivity", "TTS initialized successfully");
                    }
                } else {
                    Log.e("MainActivity", "TTS initialization failed");
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
                        Log.d("MainActivity", "ML Kit translator ready");
                        notifyTranslatorReady();
                    }
                })
                .addOnFailureListener(new OnFailureListener() {
                    @Override
                    public void onFailure(Exception e) {
                        Log.e("MainActivity", "ML Kit translator download failed: " + e.getMessage());
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
        if (dbHelper != null) {
            dbHelper.closeDatabase();
        }
        if (tts != null) {
            tts.stop();
            tts.shutdown();
        }
        if (enToZhTranslator != null) {
            enToZhTranslator.close();
        }
    }

    public class DictionaryBridge {

        @JavascriptInterface
        public String lookupWord(String word) {
            String result = dbHelper.lookupWord(word);
            return result;
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
        public void speak(String word) {
            if (tts != null && word != null && !word.isEmpty()) {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.LOLLIPOP) {
                            tts.speak(word, TextToSpeech.QUEUE_FLUSH, null, "speak_" + System.currentTimeMillis());
                        } else {
                            tts.speak(word, TextToSpeech.QUEUE_FLUSH, null);
                        }
                    }
                });
            }
        }
        
        @JavascriptInterface
        public boolean isTtsAvailable() {
            return tts != null;
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
