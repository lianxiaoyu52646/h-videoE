package com.videoenglish.app;

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
import android.util.Log;

import androidx.core.app.NotificationCompat;

import com.videoenglish.app.novel.NovelTranslateService;

/**
 * Keeps the app process alive while the user switched away without removing the task.
 * Stopped when the user returns, or when the task is swiped away from recents.
 */
public class AppKeepAliveService extends Service {

    private static final String TAG = "AppKeepAliveService";
    private static final String CHANNEL_ID = "app_keep_alive";
    private static final int NOTI_ID = 42018;

    private static volatile boolean running = false;

    public static boolean isRunning() {
        return running;
    }

    public static void start(Context ctx) {
        if (running || NovelTranslateService.isRunning()) return;
        Intent i = new Intent(ctx, AppKeepAliveService.class);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                ctx.startForegroundService(i);
            } else {
                ctx.startService(i);
            }
        } catch (Exception e) {
            Log.w(TAG, "start failed", e);
        }
    }

    public static void stop(Context ctx) {
        if (!running) return;
        try {
            ctx.stopService(new Intent(ctx, AppKeepAliveService.class));
        } catch (Exception e) {
            Log.w(TAG, "stop failed", e);
        }
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (running) return START_NOT_STICKY;
        running = true;
        ensureChannel();
        Notification noti = buildNotification();
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTI_ID, noti, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        } else {
            startForeground(NOTI_ID, noti);
        }
        Log.d(TAG, "keep-alive started");
        return START_NOT_STICKY;
    }

    @Override
    public void onTaskRemoved(Intent rootIntent) {
        Log.d(TAG, "task removed — allow cold start next launch");
        clearSession();
        stopForeground(true);
        stopSelf();
    }

    @Override
    public void onDestroy() {
        running = false;
        super.onDestroy();
        Log.d(TAG, "keep-alive stopped");
    }

    private void clearSession() {
        if (getApplication() instanceof VideoEnglishApplication) {
            ((VideoEnglishApplication) getApplication()).clearWebView();
        }
    }

    private void ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        NotificationChannel ch = new NotificationChannel(
                CHANNEL_ID, "后台保持", NotificationManager.IMPORTANCE_LOW);
        ch.setDescription("切换其他应用时保持页面，划掉多任务后自动停止");
        nm.createNotificationChannel(ch);
    }

    private Notification buildNotification() {
        Intent open = new Intent(this, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(
                this, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0)
        );
        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("WordPop 在后台")
                .setContentText("点击返回，上次页面会保留")
                .setSmallIcon(android.R.drawable.stat_notify_sync)
                .setContentIntent(pi)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .build();
    }
}
