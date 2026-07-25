package com.whatsplan.app;

import org.junit.Test;

import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

/**
 * Hebrew glues prefixes onto nouns, so a substring test cannot tell "חזרה"
 * (a rehearsal) from "בחזרה" (on the way back). A false event is worse than a
 * missed one, because it teaches the user to stop trusting the list.
 */
public final class DetectionQualityTest {

    private final WhatsAppParser parser = new WhatsAppParser();

    @Test public void backFromSomewhereIsNotARehearsal() {
        List<EventCandidate> events = parser.parseExport(
                "12.07.2026, 10:15 - רון: אני בחזרה מהחופש ב-20:00\n", "רון");
        assertTrue("\"בחזרה\" must not create a rehearsal", events.isEmpty());
    }

    @Test public void theRehearsalWithADefiniteArticleIsStillDetected() {
        List<EventCandidate> events = parser.parseExport(
                "12.07.2026, 10:15 - רון: החזרה מחר ב-20:00\n", "הלהקה");
        assertEquals(1, events.size());
        assertTrue(events.get(0).title.startsWith("חזרה"));
    }

    @Test public void englishWordingIsDetectedToo() {
        List<EventCandidate> events = parser.parseExport(
                "12.07.2026, 10:15 - Ron: rehearsal tomorrow at 20:00\n", "Band");
        assertEquals(1, events.size());
    }

    @Test public void weeklyRecurrenceBecomesAnRrule() {
        List<EventCandidate> events = parser.parseExport(
                "12.07.2026, 10:15 - אבי: קבענו חזרה כל יום שלישי ב-20:00\n", "הלהקה");
        assertEquals(1, events.size());
        assertEquals("FREQ=WEEKLY;BYDAY=TU", events.get(0).recurrence);
    }

    @Test public void monthlyRecurrenceIsRecognised() {
        List<EventCandidate> events = parser.parseExport(
                "12.07.2026, 10:15 - אבי: פגישה כל חודש ב-15.08 בשעה 18:00\n", "מנהל");
        assertEquals("FREQ=MONTHLY", events.get(0).recurrence);
    }

    @Test public void aOneOffEventCarriesNoRecurrence() {
        List<EventCandidate> events = parser.parseExport(
                "12.07.2026, 10:15 - אבי: קבענו חזרה מחר ב-20:00\n", "הלהקה");
        assertNull(events.get(0).recurrence);
    }
}
