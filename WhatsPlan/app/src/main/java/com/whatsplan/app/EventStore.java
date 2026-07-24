package com.whatsplan.app;

import android.content.*;
import android.database.Cursor;
import android.database.sqlite.*;

import java.time.ZonedDateTime;
import java.time.Duration;
import java.util.*;

public final class EventStore extends SQLiteOpenHelper {
    private static final String DB = "whatsplan.db";

    public EventStore(Context context) {
        super(context, DB, null, 2);
    }

    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE events (" +
                "id TEXT PRIMARY KEY, title TEXT NOT NULL, source TEXT, sender TEXT," +
                "conversation_id TEXT, conversation_name TEXT, is_group INTEGER DEFAULT 0," +
                "location TEXT, evidence TEXT, starts TEXT, ends TEXT," +
                "confidence INTEGER, status TEXT, reviewed INTEGER DEFAULT 0," +
                "updated_at INTEGER NOT NULL)");
    }

    @Override public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        if (oldVersion < 2) {
            db.execSQL("ALTER TABLE events ADD COLUMN conversation_id TEXT");
            db.execSQL("ALTER TABLE events ADD COLUMN conversation_name TEXT");
            db.execSQL("ALTER TABLE events ADD COLUMN is_group INTEGER DEFAULT 0");
        }
    }

    public void upsertAll(List<EventCandidate> events) {
        SQLiteDatabase db = getWritableDatabase();
        db.beginTransaction();
        try {
            for (EventCandidate event : events) {
                mergeWithExistingConversationEvent(db, event);
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
        try (Cursor cursor = db.query("events", null, "reviewed=0",
                null, null, null, "updated_at DESC", "40")) {
            while (cursor.moveToNext()) {
                EventCandidate existing = fromCursor(cursor);
                boolean sameConversation =
                        Objects.equals(existing.conversationId, incoming.conversationId)
                        || normalize(existing.conversationName)
                        .equals(normalize(incoming.conversationName));
                boolean sameKind = eventKind(existing.title).equals(eventKind(incoming.title));
                if (!sameConversation || !sameKind) continue;

                boolean closeEnough = incoming.start == null || existing.start == null
                        || Math.abs(Duration.between(existing.start, incoming.start).toDays()) <= 14;
                if (!closeEnough) continue;

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
                return;
            }
        }
    }

    public List<EventCandidate> pending() {
        List<EventCandidate> result = new ArrayList<>();
        try (Cursor cursor = getReadableDatabase().query("events", null,
                "reviewed=0", null, null, null, "starts IS NULL, starts ASC")) {
            while (cursor.moveToNext()) result.add(fromCursor(cursor));
        }
        return result;
    }

    public void markReviewed(String id) {
        ContentValues values = new ContentValues();
        values.put("reviewed", 1);
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
        return event;
    }

    private String get(Cursor cursor, String name) {
        int index = cursor.getColumnIndexOrThrow(name);
        return cursor.isNull(index) ? null : cursor.getString(index);
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
