package com.whatsplan.app;

import org.junit.Test;

import java.time.LocalDate;
import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

/**
 * Export files differ by the exporting phone: Android or iOS layout, 24-hour or
 * AM/PM clock, day-first or month-first dates. All of them must land on the same
 * calendar moment.
 */
public final class ExportFormatTest {

    private final WhatsAppParser parser = new WhatsAppParser();

    @Test public void iosBracketLayoutIsParsed() {
        List<EventCandidate> events = parser.parseExport(
                "[13/07/2026, 11:00:07] אבי: סגרנו חזרה ביום רביעי ב-20:00\n", "הלהקה");
        assertEquals(1, events.size());
        assertEquals(LocalDate.of(2026, 7, 15), events.get(0).start.toLocalDate());
        assertEquals(20, events.get(0).start.getHour());
    }

    @Test public void amPmExportKeepsTheAfternoon() {
        List<EventCandidate> events = parser.parseExport(
                "13/07/2026, 8:15 PM - Avi: סגרנו חזרה מחר ב-21:00\n", "Band");
        assertEquals(1, events.size());
        // 8:15 PM is the message stamp; "מחר" must resolve against 13.7, not 14.7.
        assertEquals(LocalDate.of(2026, 7, 14), events.get(0).start.toLocalDate());
    }

    @Test public void monthFirstExportIsDetectedFromTheFile() {
        // 7/13 can only be month-first, so 7/12 in the same file is 12 July.
        String history =
                "7/12/2026, 10:15 - Ron: קבענו חזרה היום ב-20:00\n" +
                "7/13/2026, 11:00 - Ron: נתראה\n";
        List<EventCandidate> events = parser.parseExport(history, "Band");
        assertEquals(1, events.size());
        assertEquals(LocalDate.of(2026, 7, 12), events.get(0).start.toLocalDate());
    }

    @Test public void dayFirstStaysDayFirst() {
        String history =
                "25.07.2026, 10:15 - רון: קבענו חזרה היום ב-20:00\n" +
                "26.07.2026, 11:00 - רון: נתראה\n";
        List<EventCandidate> events = parser.parseExport(history, "הלהקה");
        assertEquals(LocalDate.of(2026, 7, 25), events.get(0).start.toLocalDate());
    }

    @Test public void byteOrderMarkDoesNotSwallowTheFirstLine() {
        List<EventCandidate> events = parser.parseExport(
                "﻿12.07.2026, 10:15 - רון: קבענו חזרה היום ב-20:00\n", "הלהקה");
        assertEquals(1, events.size());
    }

    @Test public void twoParticipantsAreNotAGroup() {
        String history =
                "12.07.2026, 10:15 - רון: קבענו חזרה היום ב-20:00\n" +
                "12.07.2026, 10:16 - אבי: מעולה\n";
        assertFalse(parser.parseExport(history, "רון").get(0).groupConversation);
    }

    @Test public void threeParticipantsAreAGroup() {
        String history =
                "12.07.2026, 10:15 - רון: קבענו חזרה היום ב-20:00\n" +
                "12.07.2026, 10:16 - אבי: מעולה\n" +
                "12.07.2026, 10:17 - נועם: אני בפנים\n";
        assertTrue(parser.parseExport(history, "הלהקה").get(0).groupConversation);
    }
}
