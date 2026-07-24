package com.whatsplan.app;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.graphics.Color;
import android.net.Uri;
import android.os.*;
import android.provider.CalendarContract;
import android.provider.Settings;
import android.view.*;
import android.widget.*;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.*;

public final class MainActivity extends Activity {
    private static final int PICK_CHAT = 301;
    private static final int PURPLE = Color.rgb(108, 77, 255);
    private final WhatsAppParser parser = new WhatsAppParser();
    // One worker keeps parsing and every SQLite access off the UI thread and
    // serialised against each other.
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private EventStore store;
    private LinearLayout cards;
    private TextView status;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        store = new EventStore(this);
        buildUi();
        requestNotificationPermission();
        handleIntent(getIntent());
        refresh();
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handleIntent(intent);
    }

    @Override protected void onDestroy() {
        worker.shutdown();
        super.onDestroy();
    }

    private void buildUi() {
        getWindow().setStatusBarColor(Color.rgb(17, 18, 26));
        LinearLayout root = column(20);
        root.setBackgroundColor(Color.rgb(17, 18, 26));
        root.setPadding(dp(18), dp(18), dp(18), dp(18));

        TextView title = text("WhatsPlan", 30, Color.WHITE);
        title.setTypeface(null, 1);
        root.addView(title);
        root.addView(text("חזרות ופגישות מתוך WhatsApp — בשליטה שלך", 15,
                Color.rgb(180, 184, 205)));

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setPadding(0, dp(16), 0, dp(8));
        Button importButton = button("ייבוא שיחה");
        importButton.setOnClickListener(v -> pickChat());
        Button accessButton = button("התראות חדשות");
        accessButton.setOnClickListener(v -> startActivity(
                new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)));
        actions.addView(importButton, new LinearLayout.LayoutParams(0, dp(52), 1));
        LinearLayout.LayoutParams second = new LinearLayout.LayoutParams(0, dp(52), 1);
        second.setMarginStart(dp(10));
        actions.addView(accessButton, second);
        root.addView(actions);

        status = text("", 14, Color.rgb(130, 226, 179));
        status.setPadding(0, dp(6), 0, dp(10));
        root.addView(status);

        ScrollView scroll = new ScrollView(this);
        cards = column(12);
        scroll.addView(cards);
        root.addView(scroll, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(root);
    }

    private void pickChat() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES,
                new String[]{"text/plain", "application/zip"});
        startActivityForResult(intent, PICK_CHAT);
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == PICK_CHAT && resultCode == RESULT_OK && data != null) {
            importUri(data.getData());
        }
    }

    private void handleIntent(Intent intent) {
        if (!Intent.ACTION_SEND.equals(intent.getAction())) return;
        Uri uri = intent.getParcelableExtra(Intent.EXTRA_STREAM);
        if (uri != null) importUri(uri);
        else {
            String text = intent.getStringExtra(Intent.EXTRA_TEXT);
            if (text != null) worker.execute(() -> importText(text, "הודעה משותפת"));
        }
    }

    private void importUri(Uri uri) {
        if (uri == null) return;
        worker.execute(() -> {
            try {
                String name = displayName(uri);
                String content;
                try (InputStream input = getContentResolver().openInputStream(uri)) {
                    content = name.toLowerCase(Locale.ROOT).endsWith(".zip")
                            ? readTxtFromZip(input) : readAll(input);
                }
                importText(content, name);
            } catch (Exception error) {
                String reason = error.getMessage();
                runOnUiThread(() -> status.setText("הייבוא נכשל: " + reason));
            }
        });
    }

    /** Runs on the worker: a multi-year export is far too slow for the UI thread. */
    private void importText(String content, String source) {
        List<EventCandidate> found = parser.parseExport(content, source);
        store.upsertAll(found);
        List<EventCandidate> pending = store.pending();
        runOnUiThread(() -> {
            status.setText("נמצאו " + found.size() + " אירועים לבדיקה");
            render(pending);
        });
    }

    private void refresh() {
        worker.execute(() -> {
            List<EventCandidate> pending = store.pending();
            runOnUiThread(() -> render(pending));
        });
    }

    private void render(List<EventCandidate> events) {
        cards.removeAllViews();
        if (events.isEmpty()) {
            TextView empty = text("עדיין אין אירועים לבדיקה.\nייצא שיחת WhatsApp ללא מדיה ושתף אותה ל־WhatsPlan.",
                    17, Color.rgb(180, 184, 205));
            empty.setGravity(Gravity.CENTER);
            empty.setPadding(dp(10), dp(80), dp(10), dp(20));
            cards.addView(empty);
            return;
        }
        for (EventCandidate event : events) cards.addView(eventCard(event));
    }

    private View eventCard(EventCandidate event) {
        LinearLayout card = column(8);
        card.setPadding(dp(16), dp(16), dp(16), dp(16));
        card.setBackgroundColor(Color.rgb(31, 33, 46));
        TextView title = text(event.title, 19, Color.WHITE);
        title.setTypeface(null, 1);
        card.addView(title);

        String when = event.start == null ? "תאריך/שעה דורשים השלמה" :
                event.start.format(DateTimeFormatter.ofPattern("EEEE, d.M.yyyy · HH:mm",
                        new Locale("he", "IL")));
        card.addView(text(when, 16, Color.rgb(181, 169, 255)));
        if (event.location != null) card.addView(text("מקום: " + event.location, 14, Color.WHITE));
        card.addView(text("ודאות: " + event.confidence + "% · " + statusLabel(event),
                13, Color.rgb(170, 174, 196)));
        String conversation = event.groupConversation
                ? "קבוצה: " + event.conversationName + " · שולח: " + event.sender
                : "שיחה עם: " + event.sender;
        card.addView(text(conversation + "\n“" + shorten(event.evidence) + "”",
                13, Color.rgb(170, 174, 196)));

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        Button calendar = button(event.status == EventCandidate.Status.CANCELLED
                ? "סמן כטופל" : "פתח ביומן");
        calendar.setEnabled(event.start != null);
        calendar.setOnClickListener(v -> {
            if (event.status == EventCandidate.Status.CANCELLED) markReviewed(event.id);
            else openCalendar(event);
        });
        Button dismiss = button("התעלם");
        dismiss.setOnClickListener(v -> markReviewed(event.id));
        buttons.addView(calendar, new LinearLayout.LayoutParams(0, dp(48), 1));
        LinearLayout.LayoutParams dismissParams = new LinearLayout.LayoutParams(0, dp(48), 1);
        dismissParams.setMarginStart(dp(8));
        buttons.addView(dismiss, dismissParams);
        card.addView(buttons);
        return card;
    }

    private void openCalendar(EventCandidate event) {
        Intent intent = new Intent(Intent.ACTION_INSERT)
                .setData(CalendarContract.Events.CONTENT_URI)
                .putExtra(CalendarContract.Events.TITLE, event.title)
                .putExtra(CalendarContract.Events.DESCRIPTION,
                        "זוהה על ידי WhatsPlan\n\n" + event.evidence)
                .putExtra(CalendarContract.Events.EVENT_LOCATION, event.location)
                .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME,
                        event.start.toInstant().toEpochMilli())
                .putExtra(CalendarContract.EXTRA_EVENT_END_TIME,
                        event.end.toInstant().toEpochMilli());
        startActivity(intent);
        markReviewed(event.id);
    }

    private void markReviewed(String id) {
        worker.execute(() -> {
            store.markReviewed(id);
            List<EventCandidate> pending = store.pending();
            runOnUiThread(() -> render(pending));
        });
    }

    private void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                        != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 900);
        }
    }

    private String readTxtFromZip(InputStream input) throws IOException {
        try (ZipInputStream zip = new ZipInputStream(input, StandardCharsets.UTF_8)) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                if (!entry.isDirectory() && entry.getName().toLowerCase(Locale.ROOT).endsWith(".txt")) {
                    return readAll(zip);
                }
            }
        }
        throw new IOException("לא נמצא קובץ טקסט בתוך ה־ZIP");
    }

    private String readAll(InputStream input) throws IOException {
        if (input == null) throw new IOException("לא ניתן לפתוח את הקובץ");
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int read;
        while ((read = input.read(buffer)) != -1) output.write(buffer, 0, read);
        // ByteArrayOutputStream#toString(Charset) needs API 33; minSdk here is 26.
        return new String(output.toByteArray(), StandardCharsets.UTF_8);
    }

    private String displayName(Uri uri) {
        String tail = uri.getLastPathSegment();
        return tail == null ? "WhatsApp export" : tail.substring(tail.lastIndexOf('/') + 1);
    }

    private LinearLayout column(int spacing) {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setShowDividers(LinearLayout.SHOW_DIVIDER_MIDDLE);
        return layout;
    }

    private TextView text(String value, int size, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setTextDirection(View.TEXT_DIRECTION_RTL);
        return view;
    }

    private Button button(String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextSize(14);
        button.setTextColor(Color.WHITE);
        button.setBackgroundColor(PURPLE);
        return button;
    }

    private String statusLabel(EventCandidate event) {
        if (event.status == EventCandidate.Status.CANCELLED) return "בוטל";
        if (event.status == EventCandidate.Status.CONFIRMED) return "אושר בשיחה";
        return "הצעה";
    }

    private String shorten(String value) {
        if (value == null) return "";
        return value.length() > 220 ? value.substring(0, 220) + "…" : value;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
