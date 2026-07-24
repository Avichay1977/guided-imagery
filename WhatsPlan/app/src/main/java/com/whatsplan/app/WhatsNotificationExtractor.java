package com.whatsplan.app;

import android.app.Notification;
import android.app.Person;
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
        if (text.isEmpty()) text = string(extras.getCharSequence(Notification.EXTRA_TEXT));

        String sender = "";
        Parcelable[] bundles = extras.getParcelableArray(Notification.EXTRA_MESSAGES);
        if (bundles != null && bundles.length > 0) {
            String[] lastMessage = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P
                    ? readWithPlatform(bundles) : readFromBundles(bundles);
            if (lastMessage != null) {
                text = lastMessage[0];
                sender = lastMessage[1];
            }
        }

        boolean isGroup = extras.getBoolean(Notification.EXTRA_IS_GROUP_CONVERSATION,
                !conversationTitle.isEmpty());
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

    private String[] readWithPlatform(Parcelable[] bundles) {
        List<Notification.MessagingStyle.Message> messages =
                Notification.MessagingStyle.Message.getMessagesFromBundleArray(bundles);
        if (messages.isEmpty()) return null;
        Notification.MessagingStyle.Message last = messages.get(messages.size() - 1);
        Person person = last.getSenderPerson();
        return new String[]{
                string(last.getText()),
                person == null ? string(last.getSender()) : string(person.getName())};
    }

    /**
     * Android 8.x has no public reader for the MessagingStyle bundle array, so
     * the documented extras are read directly instead of losing the sender.
     */
    private String[] readFromBundles(Parcelable[] bundles) {
        for (int i = bundles.length - 1; i >= 0; i--) {
            if (!(bundles[i] instanceof Bundle)) continue;
            Bundle message = (Bundle) bundles[i];
            String sender = string(message.getCharSequence("sender"));
            return new String[]{string(message.getCharSequence("text")), sender};
        }
        return null;
    }

    private String string(CharSequence value) {
        return value == null ? "" : value.toString().trim();
    }
}
