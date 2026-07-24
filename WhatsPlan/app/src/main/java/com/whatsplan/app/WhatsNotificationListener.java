package com.whatsplan.app;

import android.app.*;
import android.content.*;
import android.service.notification.*;

import java.time.ZonedDateTime;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class WhatsNotificationListener extends NotificationListenerService {
    private static final String WHATSAPP = "com.whatsapp";
    private static final String WHATSAPP_BUSINESS = "com.whatsapp.w4b";
    private static final String CHANNEL_ID = "event_candidates";

    // Callbacks arrive on the main thread; parsing and SQLite must not run there.
    private final ExecutorService worker = Executors.newSingleThreadExecutor();

    @Override public void onNotificationPosted(StatusBarNotification sbn) {
        String packageName = sbn.getPackageName();
        if (!WHATSAPP.equals(packageName) && !WHATSAPP_BUSINESS.equals(packageName)) return;

        NotificationEnvelope envelope = new WhatsNotificationExtractor().extract(sbn);
        if (envelope.text.trim().isEmpty()) return;
        ZonedDateTime receivedAt = ZonedDateTime.now();

        worker.execute(() -> {
            List<EventCandidate> candidates =
                    new WhatsAppParser().parseNotification(envelope.identity, envelope.text, receivedAt);
            if (candidates.isEmpty()) return;
            new EventStore(this).upsertAll(candidates);
            showReviewNotification(candidates.get(0));
        });
    }

    @Override public void onDestroy() {
        worker.shutdown();
        super.onDestroy();
    }

    private void showReviewNotification(EventCandidate event) {
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel(
                CHANNEL_ID, "אירועים שנמצאו", NotificationManager.IMPORTANCE_HIGH));
        Intent intent = new Intent(this, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pendingIntent = PendingIntent.getActivity(this, 7, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = new Notification.Builder(this, CHANNEL_ID);
        builder.setSmallIcon(android.R.drawable.ic_menu_my_calendar)
                .setContentTitle("WhatsPlan מצא אירוע")
                .setContentText(event.title + " — בדיקה לפני הוספה ליומן")
                .setContentIntent(pendingIntent)
                .setAutoCancel(true);
        manager.notify(event.id.hashCode(), builder.build());
    }
}
