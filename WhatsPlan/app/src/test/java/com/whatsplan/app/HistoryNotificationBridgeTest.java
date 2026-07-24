package com.whatsplan.app;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;

import java.time.DayOfWeek;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

/**
 * Verifies that an update arriving from a live notification attaches to the
 * event that was previously imported from an exported chat file, instead of
 * creating a duplicate — even though the notification identity is based on a
 * shortcut ID that the export file never contained.
 */
@RunWith(RobolectricTestRunner.class)
@Config(sdk = 34)
public final class HistoryNotificationBridgeTest {

    private static final ZoneId ISRAEL = ZoneId.of("Asia/Jerusalem");

    @Test public void notificationUpdateMergesIntoImportedEvent() {
        WhatsAppParser parser = new WhatsAppParser();
        EventStore store = new EventStore(RuntimeEnvironment.getApplication());

        String history =
                "12.07.2026, 10:15 - רון: אפשר חזרה ביום רביעי בערב ב-20:00?\n" +
                "13.07.2026, 11:00 - אבי: סגרנו חזרה ביום רביעי ב-20:00 אצל אולפן קסם\n";
        List<EventCandidate> imported = parser.parseExport(history, "הלהקה");
        assertEquals(1, imported.size());
        store.upsertAll(imported);
        assertEquals(1, store.pending().size());

        ConversationIdentity liveIdentity = new ConversationIdentityResolver().resolve(
                "com.whatsapp", "הלהקה", "רון", "רון", "wa_group_777", "tag", true);
        List<EventCandidate> updates = parser.parseNotification(
                liveIdentity, "בסוף החזרה נדחתה ליום חמישי ב-21:00",
                ZonedDateTime.of(2026, 7, 14, 9, 0, 0, 0, ISRAEL));
        assertEquals(1, updates.size());
        store.upsertAll(updates);

        List<EventCandidate> pending = store.pending();
        assertEquals("update must merge into the imported event, not duplicate it",
                1, pending.size());
        EventCandidate merged = pending.get(0);
        assertEquals(DayOfWeek.THURSDAY, merged.start.getDayOfWeek());
        assertEquals(21, merged.start.getHour());
        assertTrue("evidence from both sources must be kept",
                merged.evidence.contains("אולפן קסם") && merged.evidence.contains("נדחתה"));
    }

    @Test public void cancellationFromNotificationDoesNotCreateSecondEvent() {
        WhatsAppParser parser = new WhatsAppParser();
        EventStore store = new EventStore(RuntimeEnvironment.getApplication());

        String history = "20.07.2026, 12:00 - דני: קבענו פגישה מחר בשעה 10:00\n";
        store.upsertAll(parser.parseExport(history, "דני"));
        assertEquals(1, store.pending().size());

        ConversationIdentity liveIdentity = new ConversationIdentityResolver().resolve(
                "com.whatsapp", "", "דני", "", "wa_private_dani", "tag", false);
        List<EventCandidate> updates = parser.parseNotification(
                liveIdentity, "הפגישה מחר מבוטלת",
                ZonedDateTime.of(2026, 7, 20, 18, 0, 0, 0, ISRAEL));
        store.upsertAll(updates);

        List<EventCandidate> pending = store.pending();
        assertEquals(1, pending.size());
        assertEquals(EventCandidate.Status.CANCELLED, pending.get(0).status);
    }
}
