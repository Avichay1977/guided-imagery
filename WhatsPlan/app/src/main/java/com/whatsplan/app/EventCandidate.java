package com.whatsplan.app;

import java.time.ZonedDateTime;
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
    public int confidence;
    public Status status;

    public EventCandidate() {
        status = Status.PROPOSED;
        confidence = 50;
    }

    public String fingerprint() {
        String day = start == null ? "unknown" : start.toLocalDate().toString();
        return normalize(title) + "|" + day + "|" + normalize(source);
    }

    private static String normalize(String value) {
        return Objects.toString(value, "").toLowerCase()
                .replaceAll("[^\\p{L}\\p{N}]+", " ").trim();
    }
}
