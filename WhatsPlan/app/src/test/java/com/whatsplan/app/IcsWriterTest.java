package com.whatsplan.app;

import org.junit.Test;

import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.Collections;
import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

/**
 * The calendar file is what the calendar app actually reads, so its shape is
 * pinned: byte-counted folding for Hebrew, escaped separators, UTC stamps.
 */
public final class IcsWriterTest {

    private static final ZoneId ISRAEL = ZoneId.of("Asia/Jerusalem");
    private final IcsWriter writer = new IcsWriter();

    private EventCandidate event() {
        EventCandidate event = new EventCandidate();
        event.id = "abc123";
        event.title = "חזרה – הלהקה";
        event.conversationName = "הלהקה";
        event.groupConversation = true;
        event.evidence = "סגרנו חזרה ביום רביעי ב-20:00";
        event.start = ZonedDateTime.of(2026, 7, 15, 20, 0, 0, 0, ISRAEL);
        event.end = event.start.plusHours(2);
        return event;
    }

    @Test public void producesOneWrappedCalendar() {
        String ics = writer.write(Collections.singletonList(event()), ZonedDateTime.now(ISRAEL));
        assertTrue(ics.startsWith("BEGIN:VCALENDAR\r\n"));
        assertTrue(ics.trim().endsWith("END:VCALENDAR"));
        assertTrue(ics.contains("BEGIN:VEVENT"));
        assertTrue(ics.contains("UID:abc123@whatsplan.local"));
    }

    @Test public void writesTimesInUtc() {
        // 20:00 in Israel during July is 17:00 UTC.
        String ics = writer.write(Collections.singletonList(event()), ZonedDateTime.now(ISRAEL));
        assertTrue(ics.contains("DTSTART:20260715T170000Z"));
        assertTrue(ics.contains("DTEND:20260715T190000Z"));
    }

    @Test public void carriesRecurrenceAndCancellation() {
        EventCandidate repeating = event();
        repeating.recurrence = "FREQ=WEEKLY;BYDAY=TU";
        repeating.status = EventCandidate.Status.CANCELLED;
        String ics = writer.write(Collections.singletonList(repeating), ZonedDateTime.now(ISRAEL));
        assertTrue(ics.contains("RRULE:FREQ=WEEKLY;BYDAY=TU"));
        assertTrue(ics.contains("STATUS:CANCELLED"));
    }

    @Test public void escapesSeparatorsInsideText() {
        EventCandidate withSeparators = event();
        withSeparators.location = "אבן גבירול 30, תל אביב";
        withSeparators.evidence = "שורה\nשנייה; והמשך";
        String ics = writer.write(Collections.singletonList(withSeparators), ZonedDateTime.now(ISRAEL));
        assertTrue(ics.contains("\\, תל אביב"));
        assertTrue(ics.contains("\\n"));
        assertTrue(ics.contains("\\;"));
    }

    @Test public void foldsByOctetsSoHebrewLinesStayLegal() {
        EventCandidate longOne = event();
        StringBuilder evidence = new StringBuilder();
        for (int i = 0; i < 20; i++) evidence.append("חזרה ארוכה מאוד עם המון טקסט ");
        longOne.evidence = evidence.toString();
        String ics = writer.write(Collections.singletonList(longOne), ZonedDateTime.now(ISRAEL));
        for (String line : ics.split("\r\n")) {
            assertTrue("line over 75 octets: " + line,
                    line.getBytes(java.nio.charset.StandardCharsets.UTF_8).length <= 75);
        }
    }

    @Test public void skipsEventsWithoutATime() {
        EventCandidate undated = event();
        undated.start = null;
        String ics = writer.write(Collections.singletonList(undated), ZonedDateTime.now(ISRAEL));
        assertEquals("an event with no time cannot be written",
                -1, ics.indexOf("BEGIN:VEVENT"));
    }
}
