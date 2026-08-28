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
            // The platform reader for the message array only exists from API 30,
            // and Person only from API 28, so older devices read the documented
            // MessagingStyle bundle keys instead of losing the sender entirely.
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                List<Notification.MessagingStyle.Message> messages =
                        Notification.MessagingStyle.Message.getMessagesFromBundleArray(bundles);
                if (!messages.isEmpty()) {
                    Notification.MessagingStyle.Message last = messages.get(messages.size() - 1);
                    text = string(last.getText());
                    Person person = last.getSenderPerson();
                    sender = person == null ? string(last.getSender()) : string(person.getName());
                }
            } else {
                Bundle last = lastMessageBundle(bundles);
                if (last != null) {
                    text = string(last.getCharSequence("text"));
                    sender = string(last.getCharSequence("sender"));
                    if (sender.isEmpty() && Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                        Person person = last.getParcelable("sender_person");
                        if (person != null) sender = string(person.getName());
                    }
                }
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

    private Bundle lastMessageBundle(Parcelable[] bundles) {
        for (int i = bundles.length - 1; i >= 0; i--) {
            if (bundles[i] instanceof Bundle) return (Bundle) bundles[i];
        }
        return null;
    }

    private String string(CharSequence value) {
        return value == null ? "" : value.toString().trim();
    }
}
