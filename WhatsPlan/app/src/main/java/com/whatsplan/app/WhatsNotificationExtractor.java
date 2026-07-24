package com.whatsplan.app;

import android.app.Notification;
import android.os.Build;
import android.os.Bundle;
import android.os.Parcelable;
import android.service.notification.StatusBarNotification;

import java.util.List;

public final class WhatsNotificationExtractor {
    private final ConversationIdentityResolver resolver =
            new ConversationIdentityResolver();

    public NotificationEnvelope extract(StatusBarNotification sbn) {
        Notification notification = sbn.getNotification();
        Bundle extras = notification.extras;
        String title = string(extras.getCharSequence(Notification.EXTRA_TITLE));
        String conversationTitle = string(
                extras.getCharSequence(Notification.EXTRA_CONVERSATION_TITLE));
        String text = string(extras.getCharSequence(Notification.EXTRA_BIG_TEXT));
        if (text.isBlank()) text = string(extras.getCharSequence(Notification.EXTRA_TEXT));

        String sender = "";
        Parcelable[] bundles = extras.getParcelableArray(Notification.EXTRA_MESSAGES);
        if (bundles != null && bundles.length > 0) {
            List<Notification.MessagingStyle.Message> messages =
                    Notification.MessagingStyle.Message.getMessagesFromBundleArray(bundles);
            if (!messages.isEmpty()) {
                Notification.MessagingStyle.Message last = messages.get(messages.size() - 1);
                text = string(last.getText());
                if (Build.VERSION.SDK_INT >= 28 && last.getSenderPerson() != null) {
                    sender = string(last.getSenderPerson().getName());
                } else {
                    sender = string(last.getSender());
                }
            }
        }

        boolean isGroup = extras.getBoolean(Notification.EXTRA_IS_GROUP_CONVERSATION,
                !conversationTitle.isBlank());
        ConversationIdentity identity = resolver.resolve(
                sbn.getPackageName(),
                conversationTitle,
                title,
                sender,
                notification.getShortcutId(),
                sbn.getTag(),
                isGroup);
        return new NotificationEnvelope(identity, text);
    }

    private String string(CharSequence value) {
        return value == null ? "" : value.toString().trim();
    }
}
