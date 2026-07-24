package com.whatsplan.app;

import android.app.*;
import android.content.*;
import android.os.Build;
import android.service.notification.*;

import java.time.ZonedDateTime;
import java.util.List;

public final class WhatsNotificationListener extends NotificationListenerService {
    private static final String WHATSAPP = "com.whatsapp";
    private static final String WHATSAPP_BUSINESS = "com.whatsapp.w4b";
    private static final String CHANNEL_ID = "event_candidates";

    @Override public void onNotificationPosted(StatusBarNotification sbn) {
        String packageName = sbn.getPackageName();
        if (!WHATSAPP.equals(packageName) && !WHATSAPP_BUSINESS.equals(packageName)) return;

        NotificationEnvelope envelope = new WhatsNotificationExtractor().extract(sbn);
        if (envelope.text.isBlank()) return;

        WhatsAppParser parser = new WhatsAppParser();
        List<EventCandidate> candidates = parser.parseNotification(
                envelope.identity, envelope.text, ZonedDateTime.now());
        if (candidates.isEmpty()) return;

        new EventStore(this).upsertAll(candidates);
        showReviewNotification(candidates.get(0));
    }

    private void showReviewNotification(EventCandidate event) {
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(new NotificationChannel(
                    CHANNEL_ID, "אירועים שנמצאו", NotificationManager.IMPORTANCE_HIGH));
        }
        Intent intent = new Intent(this, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pendingIntent = PendingIntent.getActivity(this, 7, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID) : new Notification.Builder(this);
        builder.setSmallIcon(android.R.drawable.ic_menu_my_calendar)
                .setContentTitle("WhatsPlan מצא אירוע")
                .setContentText(event.title + " — בדיקה לפני הוספה ליומן")
                .setContentIntent(pendingIntent)
                .setAutoCancel(true);
        manager.notify(event.id.hashCode(), builder.build());
    }
}
