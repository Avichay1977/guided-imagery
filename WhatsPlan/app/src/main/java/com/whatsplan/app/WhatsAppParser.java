package com.whatsplan.app;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.time.temporal.TemporalAdjusters;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class WhatsAppParser {
    private static final ZoneId ISRAEL = ZoneId.of("Asia/Jerusalem");
    private static final Pattern EXPORT_LINE = Pattern.compile(
            "^(?:\\[)?(\\d{1,2})[./](\\d{1,2})[./](\\d{2,4}),?\\s+(\\d{1,2}):(\\d{2})(?:\\])?\\s*(?:-|–)?\\s*([^:]{1,80}):\\s*(.*)$");
    private static final Pattern CLOCK = Pattern.compile(
            "(?<!\\d)(?:ב(?:שעה)?[\\s-]*)?(\\d{1,2})(?::|\\.)(\\d{2})(?!\\d)|(?:ב(?:שעה)?[\\s-]+)(\\d{1,2})(?!\\d)");
    private static final Pattern NUMERIC_DATE = Pattern.compile(
            "(?<!\\d)(\\d{1,2})[./](\\d{1,2})(?:[./](\\d{2,4}))?(?!\\d)");
    private static final Pattern LOCATION = Pattern.compile(
            "(?:בכתובת|כתובת[:\\s]+|מיקום[:\\s]+|נפגשים\\s+ב|אצל)\\s*([^,.;\\n]{2,60})");

    private static final Map<String, DayOfWeek> DAYS = new LinkedHashMap<>();
    static {
        DAYS.put("ראשון", DayOfWeek.SUNDAY);
        DAYS.put("שני", DayOfWeek.MONDAY);
        DAYS.put("שלישי", DayOfWeek.TUESDAY);
        DAYS.put("רביעי", DayOfWeek.WEDNESDAY);
        DAYS.put("חמישי", DayOfWeek.THURSDAY);
        DAYS.put("שישי", DayOfWeek.FRIDAY);
        DAYS.put("שבת", DayOfWeek.SATURDAY);
    }

    private static final String[] EVENT_WORDS = {
            "חזרה", "פגישה", "הופעה", "הקלטה", "מיקס", "מאסטרינג",
            "סשן", "אולפן", "חזרות", "נפגשים", "קבענו", "סגרנו"
    };
    private static final String[] CONFIRM_WORDS = {
            "סגרנו", "קבענו", "מאושר", "סופי", "יאללה", "נתראה", "תזכורת"
    };
    private static final String[] CANCEL_WORDS = {
            "מבוטל", "מבוטלת", "ביטול", "לא מתקיים", "לא תתקיים"
    };
    private static final String[] CHANGE_WORDS = {
            "נדחה", "נדחתה", "הוקדם", "הוקדמה", "במקום", "שינוי", "בסוף"
    };

    public List<EventCandidate> parseExport(String text, String sourceName) {
        List<EventCandidate> raw = new ArrayList<>();
        LocalDateTime currentStamp = null;
        String currentSender = "";
        StringBuilder message = new StringBuilder();

        for (String line : text.replace("\u200e", "").split("\\R")) {
            Matcher matcher = EXPORT_LINE.matcher(line);
            if (matcher.matches()) {
                if (currentStamp != null) {
                    analyzeMessage(raw, currentStamp, currentSender, message.toString(), sourceName);
                }
                currentStamp = parseStamp(matcher);
                currentSender = matcher.group(6).trim();
                message.setLength(0);
                message.append(matcher.group(7));
            } else if (currentStamp != null) {
                message.append('\n').append(line);
            }
        }
        if (currentStamp != null) {
            analyzeMessage(raw, currentStamp, currentSender, message.toString(), sourceName);
        }
        return mergeConversation(raw);
    }

    public List<EventCandidate> parseNotification(
            ConversationIdentity identity, String message, ZonedDateTime receivedAt) {
        List<EventCandidate> result = new ArrayList<>();
        analyzeMessage(result, receivedAt.withZoneSameInstant(ISRAEL).toLocalDateTime(),
                identity.sender, message, identity.name);
        for (EventCandidate event : result) {
            event.conversationId = identity.id;
            event.conversationName = identity.name;
            event.groupConversation = identity.group;
        }
        return result;
    }

    private void analyzeMessage(List<EventCandidate> out, LocalDateTime messageStamp,
                                String sender, String message, String source) {
        String normalized = message.toLowerCase(Locale.ROOT);
        boolean eventLanguage = containsAny(normalized, EVENT_WORDS);
        boolean cancellation = containsAny(normalized, CANCEL_WORDS);
        boolean change = containsAny(normalized, CHANGE_WORDS);
        LocalDate date = extractDate(normalized, messageStamp.toLocalDate());
        LocalTime time = extractTime(normalized);

        if (!eventLanguage && !cancellation && !change) return;
        if (date == null && time == null && !cancellation) return;

        EventCandidate event = new EventCandidate();
        event.source = source;
        event.conversationName = cleanSource(source);
        event.conversationId = stableId("export|" + cleanSource(source));
        event.groupConversation = true;
        event.sender = sender;
        event.evidence = message.trim();
        event.title = inferTitle(normalized, source);
        event.location = extractLocation(message);
        event.confidence = 42;
        if (date != null) event.confidence += 20;
        if (time != null) event.confidence += 20;
        if (containsAny(normalized, CONFIRM_WORDS)) {
            event.status = EventCandidate.Status.CONFIRMED;
            event.confidence += 12;
        }
        if (cancellation) {
            event.status = EventCandidate.Status.CANCELLED;
            event.confidence = 90;
        }
        if (change) event.confidence += 4;
        event.confidence = Math.min(99, event.confidence);

        if (date != null) {
            LocalTime resolvedTime = time == null ? LocalTime.of(9, 0) : time;
            event.start = ZonedDateTime.of(date, resolvedTime, ISRAEL);
            event.end = event.start.plusHours(2);
        }
        event.id = stableId(source + "|" + sender + "|" + messageStamp + "|" + message);
        out.add(event);
    }

    private List<EventCandidate> mergeConversation(List<EventCandidate> raw) {
        List<EventCandidate> merged = new ArrayList<>();
        for (EventCandidate next : raw) {
            EventCandidate previous = findRelated(merged, next);
            boolean mutation = containsAny(next.evidence.toLowerCase(Locale.ROOT), CHANGE_WORDS)
                    || next.status == EventCandidate.Status.CANCELLED;
            boolean sameOccurrence = previous != null && previous.start != null && next.start != null
                    && Math.abs(Duration.between(previous.start, next.start).toHours()) <= 12;
            if (previous != null && (mutation || sameOccurrence)) {
                if (next.start != null) {
                    previous.start = next.start;
                    previous.end = next.end;
                }
                if (next.location != null) previous.location = next.location;
                if (next.status == EventCandidate.Status.CANCELLED) {
                    previous.status = EventCandidate.Status.CANCELLED;
                } else if (next.status == EventCandidate.Status.CONFIRMED) {
                    previous.status = EventCandidate.Status.CONFIRMED;
                }
                previous.evidence += "\n↳ " + next.evidence;
                previous.confidence = Math.max(previous.confidence, next.confidence);
            } else {
                merged.add(next);
            }
        }
        merged.sort(Comparator.comparing(e -> e.start,
                Comparator.nullsLast(Comparator.naturalOrder())));
        return merged;
    }

    private EventCandidate findRelated(List<EventCandidate> list, EventCandidate next) {
        for (int i = list.size() - 1; i >= 0 && i >= list.size() - 8; i--) {
            EventCandidate candidate = list.get(i);
            if (!Objects.equals(candidate.source, next.source)) continue;
            if (candidate.title.equals(next.title)) return candidate;
            if (candidate.start != null && next.start != null &&
                    Math.abs(Duration.between(candidate.start, next.start).toDays()) <= 14) {
                return candidate;
            }
        }
        return null;
    }

    private LocalDate extractDate(String text, LocalDate anchor) {
        if (text.contains("מחרתיים")) return anchor.plusDays(2);
        if (text.contains("מחר")) return anchor.plusDays(1);
        if (text.contains("היום")) return anchor;

        Matcher numeric = NUMERIC_DATE.matcher(text);
        if (numeric.find()) {
            int day = Integer.parseInt(numeric.group(1));
            int month = Integer.parseInt(numeric.group(2));
            int year = numeric.group(3) == null ? anchor.getYear() :
                    normalizeYear(Integer.parseInt(numeric.group(3)));
            try {
                LocalDate result = LocalDate.of(year, month, day);
                if (numeric.group(3) == null && result.isBefore(anchor.minusMonths(2))) {
                    result = result.plusYears(1);
                }
                return result;
            } catch (DateTimeException ignored) { }
        }

        for (Map.Entry<String, DayOfWeek> entry : DAYS.entrySet()) {
            if (text.contains(entry.getKey())) {
                LocalDate result = anchor.with(TemporalAdjusters.nextOrSame(entry.getValue()));
                if (text.contains("שבוע הבא") || text.contains("בשבוע הבא")) {
                    result = result.plusWeeks(1);
                }
                return result;
            }
        }
        if (text.contains("שבוע הבא")) return anchor.plusWeeks(1);
        return null;
    }

    private LocalTime extractTime(String text) {
        Matcher clock = CLOCK.matcher(text);
        if (!clock.find()) return null;
        int hour;
        int minute;
        if (clock.group(1) != null) {
            hour = Integer.parseInt(clock.group(1));
            minute = Integer.parseInt(clock.group(2));
        } else {
            hour = Integer.parseInt(clock.group(3));
            minute = 0;
        }
        boolean evening = text.contains("בערב") || text.contains("בלילה") || text.contains("אחה");
        if (evening && hour < 12) hour += 12;
        if (hour > 23 || minute > 59) return null;
        return LocalTime.of(hour, minute);
    }

    private String inferTitle(String text, String source) {
        if (text.contains("חזרה")) return "חזרה – " + cleanSource(source);
        if (text.contains("הופעה")) return "הופעה – " + cleanSource(source);
        if (text.contains("הקלטה") || text.contains("אולפן")) return "הקלטה – " + cleanSource(source);
        if (text.contains("מיקס")) return "מיקס – " + cleanSource(source);
        if (text.contains("מאסטרינג")) return "מאסטרינג – " + cleanSource(source);
        return "פגישה – " + cleanSource(source);
    }

    private String extractLocation(String text) {
        Matcher matcher = LOCATION.matcher(text);
        return matcher.find() ? matcher.group(1).trim() : null;
    }

    private LocalDateTime parseStamp(Matcher matcher) {
        int year = normalizeYear(Integer.parseInt(matcher.group(3)));
        return LocalDateTime.of(year, Integer.parseInt(matcher.group(2)),
                Integer.parseInt(matcher.group(1)), Integer.parseInt(matcher.group(4)),
                Integer.parseInt(matcher.group(5)));
    }

    private int normalizeYear(int year) {
        return year < 100 ? 2000 + year : year;
    }

    private boolean containsAny(String value, String[] needles) {
        for (String needle : needles) if (value.contains(needle)) return true;
        return false;
    }

    private String cleanSource(String source) {
        if (source == null || source.isBlank()) return "WhatsApp";
        return source.replace("_chat", "").replace(".txt", "").replace("WhatsApp Chat with ", "").trim();
    }

    private String stableId(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder();
            for (int i = 0; i < 12; i++) hex.append(String.format("%02x", digest[i]));
            return hex.toString();
        } catch (Exception impossible) {
            return Integer.toHexString(value.hashCode());
        }
    }
}
