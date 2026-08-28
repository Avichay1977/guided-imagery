package com.whatsplan.app;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;

import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

/**
 * What the user decided about an event has to survive: a scheduled event must
 * stay visible somewhere, and a later cancellation must find it again.
 */
@RunWith(RobolectricTestRunner.class)
@Config(sdk = 34)
public final class EventStateTest {

    private final WhatsAppParser parser = new WhatsAppParser();

    @Test public void aScheduledEventLeavesReviewButStaysVisible() {
        EventStore store = new EventStore(RuntimeEnvironment.getApplication());
        store.upsertAll(parser.parseExport(
                "12.07.2026, 10:15 - אבי: קבענו חזרה מחר ב-20:00\n", "הלהקה"));
        EventCandidate event = store.pending().get(0);

        store.setState(event.id, EventStore.SCHEDULED);

        assertTrue("a scheduled event must leave the review list",
                store.byState(EventStore.PENDING).isEmpty());
        List<EventCandidate> scheduled = store.byState(EventStore.SCHEDULED);
        assertEquals("it must be visible under what was scheduled", 1, scheduled.size());
        assertEquals(event.id, scheduled.get(0).id);
    }

    @Test public void dismissedEventsCanBeBroughtBack() {
        EventStore store = new EventStore(RuntimeEnvironment.getApplication());
        store.upsertAll(parser.parseExport(
                "12.07.2026, 10:15 - אבי: קבענו חזרה מחר ב-20:00\n", "הלהקה"));
        EventCandidate event = store.pending().get(0);

        store.setState(event.id, EventStore.DISMISSED);
        assertEquals(1, store.byState(EventStore.DISMISSED).size());

        store.setState(event.id, EventStore.PENDING);
        assertEquals(1, store.pending().size());
    }

    @Test public void cancellingAnAlreadyScheduledEventReturnsItForReview() {
        EventStore store = new EventStore(RuntimeEnvironment.getApplication());
        store.upsertAll(parser.parseExport(
                "12.07.2026, 10:15 - אבי: קבענו חזרה מחר ב-20:00\n", "הלהקה"));
        EventCandidate event = store.pending().get(0);
        store.setState(event.id, EventStore.SCHEDULED);

        ConversationIdentity identity = new ConversationIdentityResolver().resolve(
                "com.whatsapp", "הלהקה", "אבי", "אבי", "wa_group_1", "tag", true);
        store.upsertAll(parser.parseNotification(identity, "החזרה מחר מבוטלת",
                ZonedDateTime.of(2026, 7, 12, 18, 0, 0, 0, ZoneId.of("Asia/Jerusalem"))));

        List<EventCandidate> pending = store.pending();
        assertEquals("the cancellation must resurface the scheduled event", 1, pending.size());
        assertEquals(EventCandidate.Status.CANCELLED, pending.get(0).status);
        assertTrue(store.byState(EventStore.SCHEDULED).isEmpty());
    }

    @Test public void anUnchangedUpdateDoesNotDisturbAScheduledEvent() {
        EventStore store = new EventStore(RuntimeEnvironment.getApplication());
        store.upsertAll(parser.parseExport(
                "12.07.2026, 10:15 - אבי: קבענו חזרה מחר ב-20:00 אצל אולפן קסם\n", "הלהקה"));
        EventCandidate event = store.pending().get(0);
        store.setState(event.id, EventStore.SCHEDULED);

        ConversationIdentity identity = new ConversationIdentityResolver().resolve(
                "com.whatsapp", "הלהקה", "רון", "רון", "wa_group_1", "tag", true);
        store.upsertAll(parser.parseNotification(identity, "מזכיר, החזרה מחר ב-20:00",
                ZonedDateTime.of(2026, 7, 12, 19, 0, 0, 0, ZoneId.of("Asia/Jerusalem"))));

        assertEquals("a reminder about the same time must not reopen it",
                1, store.byState(EventStore.SCHEDULED).size());
        assertTrue(store.pending().isEmpty());
    }
}
