import com.whatsplan.app.EventCandidate;
import com.whatsplan.app.WhatsAppParser;

import java.time.LocalDate;
import java.util.List;

public final class ParserTest {
    public static void main(String[] args) {
        WhatsAppParser parser = new WhatsAppParser();

        String history =
                "12.07.2026, 10:15 - רון: אפשר חזרה ביום רביעי בערב ב-20:00?\n" +
                "13.07.2026, 11:00 - אבי: סגרנו חזרה ביום רביעי ב-20:00 אצל אולפן קסם\n" +
                "14.07.2026, 09:12 - רון: בסוף החזרה נדחתה ליום חמישי ב-21:00\n" +
                "16.07.2026, 08:00 - אבי: ההופעה ב-22.7 בשעה 19:30 בלבונטין\n";
        List<EventCandidate> events = parser.parseExport(history, "הלהקה");

        require(events.size() == 2, "expected 2 merged events, got " + events.size());
        EventCandidate rehearsal = events.stream()
                .filter(e -> e.title.startsWith("חזרה")).findFirst().orElseThrow();
        require(rehearsal.start.toLocalDate().equals(LocalDate.of(2026, 7, 16)),
                "rescheduled rehearsal date was not merged");
        require(rehearsal.start.getHour() == 21, "evening time should be 21:00");
        require(rehearsal.evidence.contains("נדחתה"), "change evidence must be retained");

        String cancelled =
                "20.07.2026, 12:00 - דני: קבענו פגישה מחר בשעה 10:00\n" +
                "20.07.2026, 18:00 - דני: הפגישה מבוטלת\n";
        List<EventCandidate> cancelledEvents = parser.parseExport(cancelled, "דני");
        require(cancelledEvents.size() == 1, "cancellation should merge into existing event");
        require(cancelledEvents.get(0).status == EventCandidate.Status.CANCELLED,
                "event should be cancelled");

        System.out.println("WhatsPlan parser tests passed: " +
                (events.size() + cancelledEvents.size()) + " scenarios");
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
