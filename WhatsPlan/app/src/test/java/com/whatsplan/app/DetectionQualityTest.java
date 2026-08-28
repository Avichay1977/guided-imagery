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

    @Test public void arrivingLateIsNotANewEvent() {
        List<EventCandidate> events = parser.parseExport(
                "03.06.2026, 19:55 - רון: אני מאחר ב-20 דקות לחזרה\n", "הלהקה");
        assertTrue("lateness must not invent a rehearsal at 20:00", events.isEmpty());
    }

    @Test public void missingAnEventIsNotAnEvent() {
        List<EventCandidate> events = parser.parseExport(
                "10.06.2026, 07:30 - נועה: אני חוזרת מחו\"ל ב-15.6, "
                        + "אז את החזרה של ה-14 אני מפספסת\n", "הלהקה");
        assertTrue(events.isEmpty());
    }

    @Test public void becauseIsNotLateness() {
        // "מאחר ש" is a conjunction; it must not veto a real reschedule.
        List<EventCandidate> events = parser.parseExport(
                "04.06.2026, 09:00 - אבי: מאחר שהאולפן סגור, "
                        + "החזרה נדחתה ליום חמישי ב-21:00\n", "הלהקה");
        assertEquals(1, events.size());
        assertEquals(21, events.get(0).start.getHour());
    }

    @Test public void aCancellationSurvivesAnApology() {
        List<EventCandidate> events = parser.parseExport(
                "20.06.2026, 09:00 - אבי: אני לא אגיע, החזרה מחר מבוטלת\n", "הלהקה");
        assertEquals(1, events.size());
        assertEquals(EventCandidate.Status.CANCELLED, events.get(0).status);
    }

    @Test public void aPostponementUpdatesTheRehearsalInsteadOfAddingOne() {
        String history =
                "01.06.2026, 10:31 - אבי: סגרנו חזרה ביום רביעי ב-20:00 אצל אולפן קסם\n" +
                "03.06.2026, 19:55 - רון: אני מאחר ב-20 דקות לחזרה\n" +
                "04.06.2026, 09:00 - אבי: בסוף החזרה נדחתה ליום חמישי ב-21:00\n";
        List<EventCandidate> events = parser.parseExport(history, "הלהקה");
        assertEquals("one rehearsal, moved — not two", 1, events.size());
        assertEquals(21, events.get(0).start.getHour());
        assertEquals("אולפן קסם", events.get(0).location);
    }

    @Test public void schedulingWithoutAnEventNounIsStillCaught() {
        List<EventCandidate> events = parser.parseExport(
                "12.07.2026, 10:15 - רון: נתראה ביום שני ב-18:00\n", "רון");
        assertEquals(1, events.size());
        assertEquals(18, events.get(0).start.getHour());
        assertTrue("a bare hint should rank below a named event",
                events.get(0).confidence < 80);
    }

    @Test public void aHintWithoutBothDateAndTimeIsIgnored() {
        assertTrue("no time, so nothing to schedule",
                parser.parseExport("12.07.2026, 10:15 - רון: נתראה ביום שני\n", "רון").isEmpty());
        assertTrue("no date either",
                parser.parseExport("12.07.2026, 10:15 - רון: נתראה\n", "רון").isEmpty());
    }

    @Test public void chatterWithATimeIsStillIgnored() {
        assertTrue(parser.parseExport(
                "12.07.2026, 10:15 - רון: הסרט מתחיל מחר ב-20:00 בטלוויזיה\n", "רון").isEmpty());
    }

    @Test public void aOneOffEventCarriesNoRecurrence() {
        List<EventCandidate> events = parser.parseExport(
                "12.07.2026, 10:15 - אבי: קבענו חזרה מחר ב-20:00\n", "הלהקה");
        assertNull(events.get(0).recurrence);
    }
}
