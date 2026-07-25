package com.whatsplan.app;

import android.content.*;
import android.database.Cursor;
import android.database.sqlite.*;

import java.time.ZonedDateTime;
import java.time.Duration;
import java.util.*;

public final class EventStore extends SQLiteOpenHelper {
    private static final String DB = "whatsplan.db";

    /** Waiting for the user to decide. */
    public static final int PENDING = 0;
    /** The user said it is not an event, or not relevant. */
    public static final int DISMISSED = 1;
    /** The user confirmed it went into the calendar. */
    public static final int SCHEDULED = 2;

    public EventStore(Context context) {
        super(context, DB, null, 3);
    }

    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE events (" +
                "id TEXT PRIMARY KEY, title TEXT NOT NULL, source TEXT, sender TEXT," +
                "conversation_id TEXT, conversation_name TEXT, is_group INTEGER DEFAULT 0," +
                "location TEXT, evidence TEXT, starts TEXT, ends TEXT," +
                "confidence INTEGER, status TEXT, recurrence TEXT," +
                "reviewed INTEGER DEFAULT 0, updated_at INTEGER NOT NULL)");
    }

    @Override public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        if (oldVersion < 2) {
            db.execSQL("ALTER TABLE events ADD COLUMN conversation_id TEXT");
            db.execSQL("ALTER TABLE events ADD COLUMN conversation_name TEXT");
            db.execSQL("ALTER TABLE events ADD COLUMN is_group INTEGER DEFAULT 0");
        }
        if (oldVersion < 3) {
            db.execSQL("ALTER TABLE events ADD COLUMN recurrence TEXT");
        }
    }

    public void upsertAll(List<EventCandidate> events) {
        SQLiteDatabase db = getWritableDatabase();
        db.beginTransaction();
        try {
            for (EventCandidate event : events) {
                mergeWithExistingConversationEvent(db, event);
                keepEarlierDecision(db, event);
                ContentValues values = toValues(event);
                db.insertWithOnConflict("events", null, values, SQLiteDatabase.CONFLICT_REPLACE);
            }
            db.setTransactionSuccessful();
        } finally {
            db.endTransaction();
        }
    }

    /**
     * Bridges an imported chat and future notifications even when WhatsApp's
     * internal shortcut ID was unavailable in the export file.
     */
    private void mergeWithExistingConversationEvent(SQLiteDatabase db, EventCandidate incoming) {
        try (Cursor cursor = db.query("events", null, "reviewed IN (0,2)",
                null, null, null, "updated_at DESC", "40")) {
            while (cursor.moveToNext()) {
                EventCandidate existing = fromCursor(cursor);
                // Two unknown conversations are not the same conversation.
                boolean sameConversation =
                        sameValue(existing.conversationId, incoming.conversationId)
                        || sameValue(normalize(existing.conversationName),
                                normalize(incoming.conversationName));
                boolean sameKind = eventKind(existing.title).equals(eventKind(incoming.title));
                if (!sameConversation || !sameKind) continue;

                // A message that moves or cancels something may point at a date
                // two weeks out. Anything else has to be the same occurrence,
                // otherwise a standing weekly rehearsal swallows the one-off.
                boolean sameOccurrence = incoming.start == null || existing.start == null
                        || Math.abs(Duration.between(existing.start, incoming.start).toHours()) <= 12;
                boolean reachable = sameOccurrence || (incoming.update
                        && Math.abs(Duration.between(existing.start, incoming.start).toDays()) <= 14);
                if (!reachable) continue;

                incoming.id = existing.id;
                if (incoming.start == null) {
                    incoming.start = existing.start;
                    incoming.end = existing.end;
                }
                if (incoming.location == null) incoming.location = existing.location;
                if (incoming.evidence != null && existing.evidence != null
                        && !existing.evidence.contains(incoming.evidence)) {
                    incoming.evidence = existing.evidence + "\n↳ " + incoming.evidence;
                }
                incoming.confidence = Math.max(existing.confidence, incoming.confidence);
                if (incoming.recurrence == null) incoming.recurrence = existing.recurrence;
                // A cancellation or a new time must come back for review even if
                // the user had already put the old version in the calendar.
                boolean changed = incoming.status == EventCandidate.Status.CANCELLED
                        || (incoming.start != null && !incoming.start.equals(existing.start));
                incoming.state = changed ? PENDING : existing.state;
                return;
            }
        }
    }

    /**
     * Re-importing a chat used to resurrect everything the user had already
     * dismissed, because the row is replaced by a freshly parsed one. The same
     * message is the same decision unless it now says something changed.
     */
    private void keepEarlierDecision(SQLiteDatabase db, EventCandidate incoming) {
        if (incoming.update || incoming.id == null) return;
        try (Cursor cursor = db.query("events", new String[]{"reviewed"}, "id=?",
                new String[]{incoming.id}, null, null, null)) {
            if (cursor.moveToFirst()) incoming.state = cursor.getInt(0);
        }
    }

    public List<EventCandidate> pending() {
        return byState(PENDING);
    }

    public List<EventCandidate> byState(int state) {
        List<EventCandidate> result = new ArrayList<>();
        try (Cursor cursor = getReadableDatabase().query("events", null,
                "reviewed=?", new String[]{String.valueOf(state)},
                null, null, "starts IS NULL, starts ASC")) {
            while (cursor.moveToNext()) result.add(fromCursor(cursor));
        }
        return result;
    }

    public void setState(String id, int state) {
        ContentValues values = new ContentValues();
        values.put("reviewed", state);
        getWritableDatabase().update("events", values, "id=?", new String[]{id});
    }

    private ContentValues toValues(EventCandidate event) {
        ContentValues values = new ContentValues();
        values.put("id", event.id);
        values.put("title", event.title);
        values.put("source", event.source);
        values.put("conversation_id", event.conversationId);
        values.put("conversation_name", event.conversationName);
        values.put("is_group", event.groupConversation ? 1 : 0);
        values.put("sender", event.sender);
        values.put("location", event.location);
        values.put("evidence", event.evidence);
        values.put("starts", event.start == null ? null : event.start.toString());
        values.put("ends", event.end == null ? null : event.end.toString());
        values.put("confidence", event.confidence);
        values.put("status", event.status.name());
        values.put("recurrence", event.recurrence);
        values.put("reviewed", event.state);
        values.put("updated_at", System.currentTimeMillis());
        return values;
    }

    private EventCandidate fromCursor(Cursor cursor) {
        EventCandidate event = new EventCandidate();
        event.id = get(cursor, "id");
        event.title = get(cursor, "title");
        event.source = get(cursor, "source");
        event.conversationId = get(cursor, "conversation_id");
        event.conversationName = get(cursor, "conversation_name");
        event.groupConversation = cursor.getInt(cursor.getColumnIndexOrThrow("is_group")) == 1;
        event.sender = get(cursor, "sender");
        event.location = get(cursor, "location");
        event.evidence = get(cursor, "evidence");
        String starts = get(cursor, "starts");
        String ends = get(cursor, "ends");
        event.start = starts == null ? null : ZonedDateTime.parse(starts);
        event.end = ends == null ? null : ZonedDateTime.parse(ends);
        event.confidence = cursor.getInt(cursor.getColumnIndexOrThrow("confidence"));
        event.status = EventCandidate.Status.valueOf(get(cursor, "status"));
        event.recurrence = get(cursor, "recurrence");
        event.state = cursor.getInt(cursor.getColumnIndexOrThrow("reviewed"));
        return event;
    }

    private String get(Cursor cursor, String name) {
        int index = cursor.getColumnIndexOrThrow(name);
        return cursor.isNull(index) ? null : cursor.getString(index);
    }

    private boolean sameValue(String left, String right) {
        return left != null && !left.isEmpty() && left.equals(right);
    }

    private String normalize(String value) {
        return Objects.toString(value, "").toLowerCase(Locale.ROOT)
                .replaceAll("[^\\p{L}\\p{N}]+", " ").trim();
    }

    private String eventKind(String title) {
        String normalized = normalize(title);
        int separator = normalized.indexOf(' ');
        return separator < 0 ? normalized : normalized.substring(0, separator);
    }
}
