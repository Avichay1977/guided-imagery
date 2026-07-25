package com.whatsplan.app;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

/**
 * Importing a chat again is normal — the conversation keeps growing. What the
 * user already decided about the old messages has to survive it.
 */
@RunWith(RobolectricTestRunner.class)
@Config(sdk = 34)
public final class MemoryOfDecisionsTest {

    private static final String CHAT =
            "01.06.2026, 10:31 - אבי: סגרנו חזרה ביום רביעי ב-20:00\n";
    private static final String LONGER_CHAT = CHAT +
            "05.06.2026, 09:00 - אבי: יש לנו הופעה ב-22.07 בשעה 19:30\n";

    private final WhatsAppParser parser = new WhatsAppParser();

    @Test public void dismissingSurvivesAReimport() {
        EventStore store = new EventStore(RuntimeEnvironment.getApplication());
        store.upsertAll(parser.parseExport(CHAT, "הלהקה"));
        String id = store.pending().get(0).id;
        store.setState(id, EventStore.DISMISSED);

        store.upsertAll(parser.parseExport(CHAT, "הלהקה"));

        assertTrue("a dismissed event must not come back", store.pending().isEmpty());
        assertEquals(1, store.byState(EventStore.DISMISSED).size());
    }

    @Test public void schedulingSurvivesAReimport() {
        EventStore store = new EventStore(RuntimeEnvironment.getApplication());
        store.upsertAll(parser.parseExport(CHAT, "הלהקה"));
        store.setState(store.pending().get(0).id, EventStore.SCHEDULED);

        store.upsertAll(parser.parseExport(CHAT, "הלהקה"));

        assertEquals(1, store.byState(EventStore.SCHEDULED).size());
        assertTrue(store.pending().isEmpty());
    }

    @Test public void newMessagesStillArriveWhenOldOnesWereDismissed() {
        EventStore store = new EventStore(RuntimeEnvironment.getApplication());
        store.upsertAll(parser.parseExport(CHAT, "הלהקה"));
        store.setState(store.pending().get(0).id, EventStore.DISMISSED);

        store.upsertAll(parser.parseExport(LONGER_CHAT, "הלהקה"));

        assertEquals("the new concert is the only thing left to review",
                1, store.pending().size());
        assertTrue(store.pending().get(0).title.startsWith("הופעה"));
    }
}
