package com.whatsplan.app;

import java.time.ZonedDateTime;
import java.util.Locale;
import java.util.Objects;

public final class EventCandidate {
    public enum Status { PROPOSED, CONFIRMED, CANCELLED }

    public String id;
    public String title;
    public String source;
    public String conversationId;
    public String conversationName;
    public boolean groupConversation;
    public String sender;
    public String location;
    public String evidence;
    public ZonedDateTime start;
    public ZonedDateTime end;
    public String recurrence;
    /** The message changed or cancelled something, rather than proposing it. */
    public boolean update;
    public int confidence;
    public Status status;
    /** One of EventStore.PENDING, EventStore.DISMISSED, EventStore.SCHEDULED. */
    public int state;

    public EventCandidate() {
        status = Status.PROPOSED;
        confidence = 50;
        state = EventStore.PENDING;
    }

    public String fingerprint() {
        String day = start == null ? "unknown" : start.toLocalDate().toString();
        return normalize(title) + "|" + day + "|" + normalize(source);
    }

    private static String normalize(String value) {
        return Objects.toString(value, "").toLowerCase(Locale.ROOT)
                .replaceAll("[^\\p{L}\\p{N}]+", " ").trim();
    }
}
