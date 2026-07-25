package com.whatsplan.app;

import java.nio.charset.StandardCharsets;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Locale;

/**
 * Writes the approved events as one RFC 5545 calendar, so a whole import can be
 * handed to the calendar app in a single step. The app still never writes to
 * the calendar itself — the calendar app asks before importing.
 */
public final class IcsWriter {
    private static final DateTimeFormatter UTC =
            DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss'Z'", Locale.ROOT);
    private static final int MAX_OCTETS = 74;

    public String write(List<EventCandidate> events, ZonedDateTime stamp) {
        StringBuilder out = new StringBuilder();
        line(out, "BEGIN:VCALENDAR");
        line(out, "VERSION:2.0");
        line(out, "PRODID:-//WhatsPlan//Chat to calendar//HE");
        line(out, "CALSCALE:GREGORIAN");
        line(out, "METHOD:PUBLISH");
        for (EventCandidate event : events) {
            if (event.start == null) continue;
            line(out, "BEGIN:VEVENT");
            line(out, "UID:" + event.id + "@whatsplan.local");
            line(out, "DTSTAMP:" + utc(stamp));
            line(out, "DTSTART:" + utc(event.start));
            line(out, "DTEND:" + utc(event.end == null ? event.start.plusHours(2) : event.end));
            if (event.recurrence != null) line(out, "RRULE:" + event.recurrence);
            line(out, "SUMMARY:" + escape(event.title));
            if (event.location != null) line(out, "LOCATION:" + escape(event.location));
            line(out, "DESCRIPTION:" + escape(description(event)));
            if (event.status == EventCandidate.Status.CANCELLED) line(out, "STATUS:CANCELLED");
            line(out, "END:VEVENT");
        }
        line(out, "END:VCALENDAR");
        return out.toString();
    }

    private String description(EventCandidate event) {
        StringBuilder text = new StringBuilder("זוהה על ידי WhatsPlan");
        if (event.conversationName != null) {
            text.append('\n').append(event.groupConversation ? "קבוצה: " : "שיחה עם: ")
                    .append(event.conversationName);
        }
        if (event.evidence != null) {
            String evidence = event.evidence.length() > 300
                    ? event.evidence.substring(0, 300) + "…" : event.evidence;
            text.append('\n').append(evidence);
        }
        return text.toString();
    }

    private String utc(ZonedDateTime moment) {
        return moment.withZoneSameInstant(ZoneOffset.UTC).format(UTC);
    }

    /** RFC 5545 escaping: the separators would otherwise split the property. */
    private String escape(String value) {
        return value.replace("\\", "\\\\")
                .replace(";", "\\;")
                .replace(",", "\\,")
                .replace("\r\n", "\\n")
                .replace("\n", "\\n");
    }

    /**
     * Content lines are limited to 75 octets, and Hebrew costs two octets per
     * letter, so folding has to count bytes rather than characters.
     */
    private void line(StringBuilder out, String content) {
        int octets = 0;
        StringBuilder current = new StringBuilder();
        for (int i = 0; i < content.length(); ) {
            int codePoint = content.codePointAt(i);
            String chunk = new String(Character.toChars(codePoint));
            int size = chunk.getBytes(StandardCharsets.UTF_8).length;
            if (octets + size > MAX_OCTETS) {
                out.append(current).append("\r\n");
                current.setLength(0);
                current.append(' ');
                octets = 1;
            }
            current.append(chunk);
            octets += size;
            i += Character.charCount(codePoint);
        }
        out.append(current).append("\r\n");
    }
}
