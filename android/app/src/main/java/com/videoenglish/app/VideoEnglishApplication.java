package com.videoenglish.app;

import android.app.Application;
import android.webkit.WebSettings;
import android.webkit.WebView;

/**
 * Keeps a single WebView for the process lifetime so switching back to the app
 * does not reload the remote PWA after Activity recreation.
 */
public class VideoEnglishApplication extends Application {

    private WebView persistentWebView;

    public WebView obtainWebView() {
        if (persistentWebView == null) {
            persistentWebView = new WebView(getApplicationContext());
            WebSettings webSettings = persistentWebView.getSettings();
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
        }
        return persistentWebView;
    }

    public boolean hasLoadedEntry() {
        if (persistentWebView == null) return false;
        String url = persistentWebView.getUrl();
        return url != null && !url.isEmpty() && !"about:blank".equals(url);
    }

    /** Called when user removes the app from recents — next launch should cold-start. */
    public void clearWebView() {
        if (persistentWebView == null) return;
        try {
            persistentWebView.loadUrl("about:blank");
            persistentWebView.stopLoading();
            persistentWebView.clearHistory();
            persistentWebView.removeAllViews();
            persistentWebView.destroy();
        } catch (Exception ignored) {
        }
        persistentWebView = null;
    }
}
