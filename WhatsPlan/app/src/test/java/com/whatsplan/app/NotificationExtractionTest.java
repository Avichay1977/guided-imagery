package com.whatsplan.app;

import android.app.Notification;
import android.app.Person;
import android.content.Context;
import android.os.Process;
import android.service.notification.StatusBarNotification;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;

/**
 * Verifies extraction of the real Android notification extras
 * (EXTRA_CONVERSATION_TITLE, EXTRA_MESSAGES, EXTRA_IS_GROUP_CONVERSATION)
 * and the stability of the shortcut-based conversation identity.
 */
@RunWith(RobolectricTestRunner.class)
@Config(sdk = 34)
public final class NotificationExtractionTest {

    private final WhatsNotificationExtractor extractor = new WhatsNotificationExtractor();

    @Test public void conversationTitleBecomesGroupName() {
        StatusBarNotification sbn = groupNotification(
                "Oy Division", "אבי", "סגרנו חזרה ביום רביעי ב-20:00", "wa_group_123");
        NotificationEnvelope envelope = extractor.extract(sbn);
        assertTrue(envelope.identity.group);
        assertEquals("Oy Division", envelope.identity.name);
    }

    @Test public void messagingStyleMessageSuppliesTextAndSender() {
        StatusBarNotification sbn = groupNotification(
                "Oy Division", "אבי", "סגרנו חזרה ביום רביעי ב-20:00", "wa_group_123");
        NotificationEnvelope envelope = extractor.extract(sbn);
        assertEquals("סגרנו חזרה ביום רביעי ב-20:00", envelope.text);
        assertEquals("אבי", envelope.identity.sender);
    }

    @Test public void isGroupConversationExtraIsRespected() {
        StatusBarNotification group = groupNotification(
                "Oy Division", "אבי", "היי", "wa_group_123");
        assertTrue(extractor.extract(group).identity.group);

        StatusBarNotification direct = privateNotification("נועם", "היי", "wa_private_noam");
        assertFalse(extractor.extract(direct).identity.group);
    }

    @Test public void shortcutIdSurvivesGroupRename() {
        StatusBarNotification before = groupNotification(
                "Oy Division", "אבי", "חזרה מחר ב-20:00", "wa_group_123");
        StatusBarNotification after = groupNotification(
                "Oy Division 2026", "רון", "החזרה נדחתה", "wa_group_123");
        assertEquals(extractor.extract(before).identity.id,
                extractor.extract(after).identity.id);
    }

    @Test public void privateConversationIsNotClassifiedAsGroup() {
        StatusBarNotification sbn = privateNotification(
                "נועם", "נפגשים מחר בשעה 10:00", "wa_private_noam");
        NotificationEnvelope envelope = extractor.extract(sbn);
        assertFalse(envelope.identity.group);
        assertEquals("נועם", envelope.identity.sender);
    }

    @Test public void twoGroupsWithSameSenderStaySeparate() {
        StatusBarNotification first = groupNotification(
                "Oy Division", "אבי", "חזרה ביום שני", "wa_group_123");
        StatusBarNotification second = groupNotification(
                "Freud Delay Team", "אבי", "חזרה ביום שני", "wa_group_456");
        NotificationEnvelope one = extractor.extract(first);
        NotificationEnvelope two = extractor.extract(second);
        assertNotEquals(one.identity.id, two.identity.id);
        assertEquals("אבי", one.identity.sender);
        assertEquals("אבי", two.identity.sender);
    }

    private StatusBarNotification groupNotification(
            String groupName, String sender, String message, String shortcutId) {
        Context context = RuntimeEnvironment.getApplication();
        Person me = new Person.Builder().setName("אני").build();
        Person from = new Person.Builder().setName(sender).build();
        Notification.MessagingStyle style = new Notification.MessagingStyle(me)
                .setConversationTitle(groupName)
                .setGroupConversation(true)
                .addMessage(message, 1721000000000L, from);
        Notification notification = new Notification.Builder(context, "test")
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle(groupName)
                .setContentText(sender + ": " + message)
                .setShortcutId(shortcutId)
                .setStyle(style)
                .build();
        return statusBar(notification, shortcutId);
    }

    private StatusBarNotification privateNotification(
            String contact, String message, String shortcutId) {
        Context context = RuntimeEnvironment.getApplication();
        Person me = new Person.Builder().setName("אני").build();
        Person from = new Person.Builder().setName(contact).build();
        Notification.MessagingStyle style = new Notification.MessagingStyle(me)
                .setGroupConversation(false)
                .addMessage(message, 1721000000000L, from);
        Notification notification = new Notification.Builder(context, "test")
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle(contact)
                .setContentText(message)
                .setShortcutId(shortcutId)
                .setStyle(style)
                .build();
        return statusBar(notification, shortcutId);
    }

    private StatusBarNotification statusBar(Notification notification, String tag) {
        return new StatusBarNotification("com.whatsapp", "com.whatsapp", 1, tag,
                10001, 0, 0, notification, Process.myUserHandle(),
                1721000000000L);
    }
}
