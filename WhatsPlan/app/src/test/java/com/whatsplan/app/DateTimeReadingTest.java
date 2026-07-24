package com.whatsplan.app;

import org.junit.Test;

import java.time.LocalDate;
import java.util.List;

import static org.junit.Assert.assertEquals;

/**
 * A dotted date and a dotted clock look alike in Hebrew messages. Reading one as
 * the other silently moves an event by hours, so both directions are pinned.
 */
public final class DateTimeReadingTest {

    private final WhatsAppParser parser = new WhatsAppParser();

    @Test public void dottedDateDoesNotBecomeTheHour() {
        List<EventCandidate> events = parser.parseExport(
                "16.07.2026, 08:00 - אבי: ההופעה ב-22.07 בשעה 19:30 בלבונטין\n", "הלהקה");
        assertEquals(1, events.size());
        assertEquals(LocalDate.of(2026, 7, 22), events.get(0).start.toLocalDate());
        assertEquals(19, events.get(0).start.getHour());
        assertEquals(30, events.get(0).start.getMinute());
    }

    @Test public void dottedClockIsStillATime() {
        List<EventCandidate> events = parser.parseExport(
                "16.07.2026, 08:00 - אבי: קבענו חזרה מחר ב-19.30\n", "הלהקה");
        assertEquals(LocalDate.of(2026, 7, 17), events.get(0).start.toLocalDate());
        assertEquals(19, events.get(0).start.getHour());
        assertEquals(30, events.get(0).start.getMinute());
    }

    @Test public void aRehearsalIsNeverAbsorbedByAConcert() {
        String history =
                "13.07.2026, 11:00 - אבי: סגרנו חזרה ב-15.07 בשעה 20:00\n" +
                "13.07.2026, 11:05 - אבי: וההופעה ב-18.07 בשעה 21:00\n";
        List<EventCandidate> events = parser.parseExport(history, "הלהקה");
        assertEquals("rehearsal and concert are separate events", 2, events.size());
    }
}
