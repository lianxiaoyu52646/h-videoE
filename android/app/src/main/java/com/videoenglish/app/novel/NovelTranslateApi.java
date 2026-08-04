package com.videoenglish.app.novel;

import android.util.Log;
import android.webkit.CookieManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/** HTTP claim/submit for shared book translate, using WebView cookies. */
public final class NovelTranslateApi {
    private static final String TAG = "NovelTranslateApi";

    private final String origin;

    public NovelTranslateApi(String origin) {
        String o = origin == null ? "" : origin.trim();
        while (o.endsWith("/")) o = o.substring(0, o.length() - 1);
        this.origin = o;
    }

    public static final class ClaimItem {
        public int editionId;
        public int orderIndex;
        public String bookKey;
        public String title;
        public String enText;
    }

    public static final class ClaimResult {
        public boolean ok;
        public boolean done;
        public String message;
        public String bookKey;
        public String title;
        public int blockCount;
        public int translatedBlocks;
        public final List<ClaimItem> items = new ArrayList<>();
    }

    public static final class SubmitResult {
        public boolean ok;
        public int saved;
        public int skipped;
        public String title;
        public String translateStatus;
        public int translatedBlocks;
        public int blockCount;
        public int doneBooks;
        public int pendingBooks;
        public int totalBooks;
    }

    public ClaimResult claim(int limit) throws Exception {
        String path = "/api/jobs/book-translate/claim?limit=" + Math.max(1, Math.min(limit, 20))
                + "&ensure_catalog=true";
        JSONObject root = requestJson("POST", path, null);
        ClaimResult out = new ClaimResult();
        out.ok = root.optBoolean("ok", true);
        out.done = root.optBoolean("done", false);
        out.message = root.optString("message", "");
        out.bookKey = root.optString("book_key", "");
        out.title = root.optString("title", "");
        out.blockCount = root.optInt("block_count", 0);
        out.translatedBlocks = root.optInt("translated_blocks", 0);
        JSONArray arr = root.optJSONArray("items");
        if (arr != null) {
            for (int i = 0; i < arr.length(); i++) {
                JSONObject it = arr.getJSONObject(i);
                ClaimItem item = new ClaimItem();
                item.editionId = it.optInt("edition_id");
                item.orderIndex = it.optInt("order_index");
                item.bookKey = it.optString("book_key", out.bookKey);
                item.title = it.optString("title", out.title);
                item.enText = it.optString("en_text", "");
                out.items.add(item);
            }
        }
        return out;
    }

    public SubmitResult submit(List<ClaimItem> batch, List<String> zhList, String source) throws Exception {
        JSONObject body = new JSONObject();
        body.put("source", source == null ? "qwen_local" : source);
        JSONArray items = new JSONArray();
        for (int i = 0; i < batch.size(); i++) {
            ClaimItem c = batch.get(i);
            String zh = i < zhList.size() ? zhList.get(i) : "";
            if (zh == null || zh.trim().isEmpty()) continue;
            JSONObject it = new JSONObject();
            it.put("edition_id", c.editionId);
            it.put("order_index", c.orderIndex);
            it.put("en_text", c.enText == null ? "" : c.enText);
            it.put("zh_text", zh.trim());
            items.put(it);
        }
        body.put("items", items);
        JSONObject root = requestJson("POST", "/api/jobs/book-translate/submit", body.toString());
        SubmitResult out = new SubmitResult();
        out.ok = root.optBoolean("ok", true);
        out.saved = root.optInt("saved", 0);
        out.skipped = root.optInt("skipped", 0);
        out.title = root.optString("title", "");
        out.translateStatus = root.optString("translate_status", "");
        out.translatedBlocks = root.optInt("translated_blocks", 0);
        out.blockCount = root.optInt("block_count", 0);
        JSONObject scan = root.optJSONObject("scan");
        if (scan != null) {
            out.doneBooks = scan.optInt("done_books", 0);
            out.pendingBooks = scan.optInt("pending_books", 0);
            out.totalBooks = scan.optInt("total_books", 0);
        }
        return out;
    }

    private JSONObject requestJson(String method, String path, String jsonBody) throws Exception {
        URL url = new URL(origin + path);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        try {
            conn.setConnectTimeout(25000);
            conn.setReadTimeout(60000);
            conn.setInstanceFollowRedirects(true);
            conn.setRequestMethod(method);
            conn.setRequestProperty("Accept", "application/json");
            String cookie = CookieManager.getInstance().getCookie(origin);
            if (cookie != null && !cookie.isEmpty()) {
                conn.setRequestProperty("Cookie", cookie);
            }
            if (jsonBody != null) {
                byte[] bytes = jsonBody.getBytes(StandardCharsets.UTF_8);
                conn.setDoOutput(true);
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                conn.setRequestProperty("Content-Length", String.valueOf(bytes.length));
                OutputStream os = conn.getOutputStream();
                os.write(bytes);
                os.flush();
                os.close();
            }
            int code = conn.getResponseCode();
            InputStream stream = code >= 200 && code < 300 ? conn.getInputStream() : conn.getErrorStream();
            String text = readAll(stream);
            if (code < 200 || code >= 300) {
                Log.e(TAG, method + " " + path + " HTTP " + code + " " + text);
                throw new IOException("HTTP " + code + ": " + truncate(text, 200));
            }
            if (text == null || text.trim().isEmpty()) return new JSONObject();
            return new JSONObject(text);
        } finally {
            conn.disconnect();
        }
    }

    private static String readAll(InputStream in) throws Exception {
        if (in == null) return "";
        BufferedReader br = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = br.readLine()) != null) sb.append(line);
        br.close();
        return sb.toString();
    }

    private static String truncate(String s, int n) {
        if (s == null) return "";
        return s.length() <= n ? s : s.substring(0, n);
    }

    private static class IOException extends java.io.IOException {
        IOException(String m) { super(m); }
    }
}
