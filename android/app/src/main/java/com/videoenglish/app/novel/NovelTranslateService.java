package com.videoenglish.app.novel;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.util.Log;

import androidx.core.app.NotificationCompat;

import com.google.mlkit.nl.translate.TranslateLanguage;
import com.google.mlkit.nl.translate.Translation;
import com.google.mlkit.nl.translate.Translator;
import com.google.mlkit.nl.translate.TranslatorOptions;
import com.videoenglish.app.MainActivity;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Foreground novel translation worker — keeps running when screen off / app backgrounded.
 */
public class NovelTranslateService extends Service {
    private static final String TAG = "NovelTranslateService";
    public static final String ACTION_START = "com.videoenglish.app.novel.START";
    public static final String ACTION_STOP = "com.videoenglish.app.novel.STOP";
    public static final String EXTRA_ORIGIN = "origin";
    public static final String EXTRA_MODEL_URL = "model_url";
    public static final String EXTRA_MODEL_NAME = "model_name";
    public static final String EXTRA_CLAIM_LIMIT = "claim_limit";

    private static final String CHANNEL_ID = "novel_translate";
    private static final int NOTI_ID = 42017;

    private static final AtomicBoolean RUNNING = new AtomicBoolean(false);
    private static volatile EventSink eventSink;

    private final AtomicBoolean stopRequested = new AtomicBoolean(false);
    private Thread worker;
    private PowerManager.WakeLock wakeLock;
    private Translator mlKit;
    private NovelTranslator novelTranslator;

    public interface EventSink {
        void onNovelTranslateEvent(String json);
    }

    public static void setEventSink(EventSink sink) {
        eventSink = sink;
    }

    public static boolean isRunning() {
        return RUNNING.get();
    }

    public static void start(Context ctx, String origin, String modelUrl, String modelName, int claimLimit) {
        Intent i = new Intent(ctx, NovelTranslateService.class);
        i.setAction(ACTION_START);
        i.putExtra(EXTRA_ORIGIN, origin);
        i.putExtra(EXTRA_MODEL_URL, modelUrl == null ? "" : modelUrl);
        i.putExtra(EXTRA_MODEL_NAME, modelName == null ? NovelModelStore.DEFAULT_NAME : modelName);
        i.putExtra(EXTRA_CLAIM_LIMIT, claimLimit <= 0 ? 8 : claimLimit);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            ctx.startForegroundService(i);
        } else {
            ctx.startService(i);
        }
    }

    public static void stop(Context ctx) {
        Intent i = new Intent(ctx, NovelTranslateService.class);
        i.setAction(ACTION_STOP);
        ctx.startService(i);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopRequested.set(true);
            emit("I", "service.stop_requested", null);
            return START_NOT_STICKY;
        }
        if (!RUNNING.compareAndSet(false, true)) {
            emit("W", "service.already_running", null);
            return START_STICKY;
        }
        stopRequested.set(false);
        ensureChannel();
        Notification noti = buildNotification("小说翻译进行中", "正在准备本地翻译引擎…");
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTI_ID, noti, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        } else {
            startForeground(NOTI_ID, noti);
        }
        acquireWakeLock();

        final String origin = intent != null ? intent.getStringExtra(EXTRA_ORIGIN) : null;
        final String modelUrl = intent != null ? intent.getStringExtra(EXTRA_MODEL_URL) : "";
        final String modelName = intent != null ? intent.getStringExtra(EXTRA_MODEL_NAME) : NovelModelStore.DEFAULT_NAME;
        final int claimLimit = intent != null ? intent.getIntExtra(EXTRA_CLAIM_LIMIT, 8) : 8;
        final String apiOrigin = (origin == null || origin.isEmpty())
                ? "https://wordpop-xyh7.onrender.com"
                : origin;

        worker = new Thread(() -> runLoop(apiOrigin, modelUrl, modelName, claimLimit), "novel-translate");
        worker.start();
        return START_STICKY;
    }

    private void runLoop(String origin, String modelUrl, String modelName, int claimLimit) {
        emit("I", "service.loop_start", obj("origin", origin, "claimLimit", claimLimit));
        try {
            novelTranslator = new NovelTranslator(this);
            initMlKitBlocking();
            novelTranslator.setMlKitFallback(mlKit);
            prepareModel(modelUrl, modelName);
            NovelTranslateApi api = new NovelTranslateApi(origin);
            int emptyStreak = 0;
            int failStreak = 0;
            int round = 0;

            while (!stopRequested.get()) {
                round++;
                NovelTranslateApi.ClaimResult claim;
                try {
                    updateNotification("小说翻译进行中", "领取待译段落…");
                    emit("I", "claim.request", obj("round", round, "limit", claimLimit));
                    claim = api.claim(claimLimit);
                    failStreak = 0;
                } catch (Exception e) {
                    failStreak++;
                    emit("E", "claim.error", obj("err", String.valueOf(e.getMessage()), "failStreak", failStreak));
                    if (failStreak >= 12) break;
                    sleep(Math.min(8000, 600 * failStreak));
                    continue;
                }

                emit("I", "claim.result", obj(
                        "done", claim.done,
                        "items", claim.items.size(),
                        "book", claim.bookKey,
                        "title", claim.title,
                        "progress", claim.translatedBlocks + "/" + claim.blockCount,
                        "message", claim.message
                ));

                if (claim.done) {
                    emit("I", "service.done", obj("message", claim.message));
                    updateNotification("小说翻译完成", claim.message == null ? "全部完成" : claim.message);
                    break;
                }
                if (claim.items.isEmpty()) {
                    emptyStreak++;
                    emit("W", "claim.empty", obj("streak", emptyStreak));
                    if (emptyStreak >= 10) break;
                    sleep(700);
                    continue;
                }
                emptyStreak = 0;

                List<NovelTranslateApi.ClaimItem> okItems = new ArrayList<>();
                List<String> zhList = new ArrayList<>();
                for (NovelTranslateApi.ClaimItem item : claim.items) {
                    if (stopRequested.get()) break;
                    updateNotification(
                            "正在翻译",
                            (item.title == null || item.title.isEmpty() ? item.bookKey : item.title)
                                    + " · 段 #" + item.orderIndex
                    );
                    emit("I", "para.start", obj(
                            "order", item.orderIndex,
                            "book", item.bookKey,
                            "enLen", item.enText == null ? 0 : item.enText.length()
                    ));
                    String zh = novelTranslator.translateParagraph(item.enText);
                    if (zh != null && !zh.trim().isEmpty()) {
                        okItems.add(item);
                        zhList.add(zh.trim());
                        emit("I", "para.ok", obj(
                                "order", item.orderIndex,
                                "zhLen", zh.trim().length(),
                                "engine", novelTranslator.getEngineName()
                        ));
                    } else {
                        emit("W", "para.empty", obj("order", item.orderIndex, "engine", novelTranslator.getEngineName()));
                    }
                }
                if (stopRequested.get()) break;
                if (okItems.isEmpty()) {
                    sleep(800);
                    continue;
                }
                try {
                    String source = "qwen_local".equals(novelTranslator.getEngineName())
                            ? "qwen_local" : novelTranslator.getEngineName();
                    NovelTranslateApi.SubmitResult submitted = api.submit(okItems, zhList, source);
                    emit("I", "submit.ok", obj(
                            "saved", submitted.saved,
                            "skipped", submitted.skipped,
                            "progress", submitted.translatedBlocks + "/" + submitted.blockCount,
                            "doneBooks", submitted.doneBooks,
                            "pendingBooks", submitted.pendingBooks,
                            "totalBooks", submitted.totalBooks,
                            "title", submitted.title
                    ));
                    updateNotification(
                            "小说翻译进行中",
                            "已完成 " + submitted.doneBooks + "/" + submitted.totalBooks
                                    + " 本 · +" + submitted.saved + " 段"
                    );
                } catch (Exception e) {
                    failStreak++;
                    emit("E", "submit.error", obj("err", String.valueOf(e.getMessage()), "failStreak", failStreak));
                    if (failStreak >= 12) break;
                    sleep(1000);
                }
                sleep(200);
            }
        } catch (Exception e) {
            Log.e(TAG, "loop fatal", e);
            emit("E", "service.fatal", obj("err", String.valueOf(e.getMessage())));
        } finally {
            emit("I", "service.loop_end", obj("stopped", stopRequested.get()));
            cleanup();
            RUNNING.set(false);
            stopForeground(true);
            stopSelf();
        }
    }

    private void prepareModel(String modelUrl, String modelName) {
        String name = (modelName == null || modelName.isEmpty()) ? NovelModelStore.DEFAULT_NAME : modelName;
        updateNotification("准备模型", "检查/下载小说翻译模型…");
        emit("I", "model.prepare", obj("name", name, "hasUrl", modelUrl != null && !modelUrl.isEmpty()));
        NovelModelStore store = novelTranslator.getStore();
        if (!store.isModelReady(name) && modelUrl != null && !modelUrl.trim().isEmpty()) {
            try {
                store.download(modelUrl.trim(), name, percent -> {
                    updateNotification("下载模型", "小说翻译模型 " + percent + "%");
                    if (percent % 10 == 0) emit("I", "model.download", obj("percent", percent));
                });
            } catch (Exception e) {
                emit("W", "model.download_fail", obj("err", String.valueOf(e.getMessage())));
            }
        }
        novelTranslator.prepare(name);
        novelTranslator.loadDownloadedModel();
        emit("I", "model.ready", obj("engine", novelTranslator.getEngineName(), "qwen", novelTranslator.isQwenReady()));
    }

    private void initMlKitBlocking() {
        try {
            TranslatorOptions options = new TranslatorOptions.Builder()
                    .setSourceLanguage(TranslateLanguage.ENGLISH)
                    .setTargetLanguage(TranslateLanguage.CHINESE)
                    .build();
            mlKit = Translation.getClient(options);
            com.google.android.gms.tasks.Tasks.await(mlKit.downloadModelIfNeeded());
            emit("I", "mlkit.ready", null);
        } catch (Exception e) {
            emit("W", "mlkit.fail", obj("err", String.valueOf(e.getMessage())));
            mlKit = null;
        }
    }

    private void cleanup() {
        releaseWakeLock();
        if (novelTranslator != null) {
            try { novelTranslator.release(); } catch (Exception ignored) {}
            novelTranslator = null;
        }
        if (mlKit != null) {
            try { mlKit.close(); } catch (Exception ignored) {}
            mlKit = null;
        }
    }

    private void acquireWakeLock() {
        try {
            PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "wordpop:novel_translate");
            wakeLock.setReferenceCounted(false);
            wakeLock.acquire(12 * 60 * 60 * 1000L); // up to 12h
        } catch (Exception e) {
            Log.w(TAG, "wakeLock failed", e);
        }
    }

    private void releaseWakeLock() {
        try {
            if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        } catch (Exception ignored) {}
        wakeLock = null;
    }

    private void ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        NotificationChannel ch = new NotificationChannel(
                CHANNEL_ID, "小说离线翻译", NotificationManager.IMPORTANCE_LOW);
        ch.setDescription("后台持续翻译经典书库");
        nm.createNotificationChannel(ch);
    }

    private Notification buildNotification(String title, String text) {
        Intent open = new Intent(this, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(
                this, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0)
        );
        Intent stop = new Intent(this, NovelTranslateService.class);
        stop.setAction(ACTION_STOP);
        PendingIntent stopPi = PendingIntent.getService(
                this, 1, stop,
                PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0)
        );
        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle(title)
                .setContentText(text)
                .setSmallIcon(android.R.drawable.stat_notify_sync)
                .setContentIntent(pi)
                .setOngoing(true)
                .addAction(0, "停止", stopPi)
                .setOnlyAlertOnce(true)
                .build();
    }

    private void updateNotification(String title, String text) {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        nm.notify(NOTI_ID, buildNotification(title, text));
    }

    private void emit(String level, String event, JSONObject detail) {
        try {
            JSONObject o = new JSONObject();
            o.put("level", level);
            o.put("event", event);
            o.put("ts", System.currentTimeMillis());
            if (detail != null) o.put("detail", detail);
            String json = o.toString();
            Log.i(TAG, level + " " + event + " " + (detail == null ? "" : detail));
            EventSink sink = eventSink;
            if (sink != null) sink.onNovelTranslateEvent(json);
        } catch (Exception e) {
            Log.w(TAG, "emit failed", e);
        }
    }

    private static JSONObject obj(Object... kv) {
        JSONObject o = new JSONObject();
        try {
            for (int i = 0; i + 1 < kv.length; i += 2) {
                o.put(String.valueOf(kv[i]), kv[i + 1]);
            }
        } catch (Exception ignored) {}
        return o;
    }

    private static void sleep(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException ignored) {}
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        stopRequested.set(true);
        RUNNING.set(false);
        cleanup();
        super.onDestroy();
    }
}
