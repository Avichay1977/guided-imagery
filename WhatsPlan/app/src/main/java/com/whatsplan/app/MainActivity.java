package com.whatsplan.app;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.*;
import android.provider.CalendarContract;
import android.provider.DocumentsContract;
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
    private static final int OPEN_CALENDAR = 302;
    private static final int PURPLE = Color.rgb(108, 77, 255);
    private static final int MUTED = Color.rgb(170, 174, 196);
    private final WhatsAppParser parser = new WhatsAppParser();
    // One worker keeps parsing and every SQLite access off the UI thread and
    // serialised against each other.
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private EventStore store;
    private LinearLayout cards;
    private LinearLayout tabs;
    private TextView status;
    private Button accessButton;
    private int shownState = EventStore.PENDING;
    private EventCandidate awaitingCalendar;

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

    @Override protected void onResume() {
        super.onResume();
        updateAccessButton();
        refresh();
    }

    @Override protected void onDestroy() {
        worker.shutdown();
        super.onDestroy();
    }

    private void buildUi() {
        getWindow().setStatusBarColor(Color.rgb(17, 18, 26));
        LinearLayout root = column();
        root.setBackgroundColor(Color.rgb(17, 18, 26));
        root.setPadding(dp(18), dp(18), dp(18), dp(18));

        TextView title = text("WhatsPlan", 30, Color.WHITE);
        title.setTypeface(null, Typeface.BOLD);
        root.addView(title);
        root.addView(text("חזרות ופגישות מתוך WhatsApp — בשליטה שלך", 15,
                Color.rgb(180, 184, 205)));

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setPadding(0, dp(16), 0, dp(8));
        Button importButton = button("ייבוא שיחה");
        importButton.setOnClickListener(v -> pickChat());
        accessButton = button("התראות חדשות");
        accessButton.setOnClickListener(v -> startActivity(
                new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)));
        actions.addView(importButton, new LinearLayout.LayoutParams(0, dp(52), 1));
        LinearLayout.LayoutParams second = new LinearLayout.LayoutParams(0, dp(52), 1);
        second.setMarginStart(dp(10));
        actions.addView(accessButton, second);
        root.addView(actions);

        tabs = new LinearLayout(this);
        tabs.setOrientation(LinearLayout.HORIZONTAL);
        tabs.setPadding(0, dp(6), 0, dp(4));
        addTab("לבדיקה", EventStore.PENDING);
        addTab("נקבעו", EventStore.SCHEDULED);
        addTab("לא רלוונטי", EventStore.DISMISSED);
        root.addView(tabs);

        status = text("", 14, Color.rgb(130, 226, 179));
        status.setPadding(0, dp(6), 0, dp(10));
        root.addView(status);

        ScrollView scroll = new ScrollView(this);
        cards = column();
        scroll.addView(cards);
        root.addView(scroll, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(root);
        updateAccessButton();
    }

    private void addTab(String label, int state) {
        Button tab = new Button(this);
        tab.setText(label);
        tab.setTextSize(13);
        tab.setAllCaps(false);
        tab.setOnClickListener(v -> {
            shownState = state;
            paintTabs();
            refresh();
        });
        tab.setTag(state);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, dp(44), 1);
        if (tabs.getChildCount() > 0) params.setMarginStart(dp(6));
        tabs.addView(tab, params);
        paintTabs();
    }

    private void paintTabs() {
        for (int i = 0; i < tabs.getChildCount(); i++) {
            Button tab = (Button) tabs.getChildAt(i);
            boolean selected = Integer.valueOf(shownState).equals(tab.getTag());
            tab.setBackgroundColor(selected ? PURPLE : Color.rgb(31, 33, 46));
            tab.setTextColor(selected ? Color.WHITE : MUTED);
        }
    }

    /**
     * Android drops notification listeners after updates or memory pressure, and
     * says nothing. Showing the live state turns a silent failure into a visible
     * one.
     */
    private void updateAccessButton() {
        if (accessButton == null) return;
        boolean granted = notificationAccessGranted();
        accessButton.setText(granted ? "התראות · פעיל" : "התראות · כבוי");
        accessButton.setBackgroundColor(granted ? Color.rgb(38, 110, 76) : PURPLE);
        if (granted) {
            android.service.notification.NotificationListenerService.requestRebind(
                    new ComponentName(this, WhatsNotificationListener.class));
        }
    }

    private boolean notificationAccessGranted() {
        String enabled = Settings.Secure.getString(
                getContentResolver(), "enabled_notification_listeners");
        return enabled != null && enabled.contains(getPackageName());
    }

    /**
     * WhatsApp exports one chat at a time, so importing a few of them should
     * still be a single action. The picker also opens in Downloads, where the
     * export lands, instead of the recent-files list.
     */
    private void pickChat() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES,
                new String[]{"text/plain", "application/zip"});
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        intent.putExtra(DocumentsContract.EXTRA_INITIAL_URI,
                DocumentsContract.buildDocumentUri(
                        "com.android.externalstorage.documents", "primary:Download"));
        startActivityForResult(intent, PICK_CHAT);
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == PICK_CHAT && resultCode == RESULT_OK && data != null) {
            importUris(selectedUris(data));
        } else if (requestCode == OPEN_CALENDAR) {
            confirmCalendarResult();
        }
    }

    /**
     * Calendar apps report a cancelled result even after a successful save, so
     * the only reliable source is the user. Until they answer, the event stays
     * in the review list instead of quietly disappearing.
     */
    private void confirmCalendarResult() {
        EventCandidate event = awaitingCalendar;
        awaitingCalendar = null;
        if (event == null) return;
        new AlertDialog.Builder(this)
                .setTitle("נקבע ביומן?")
                .setMessage(event.title)
                .setPositiveButton("כן, נקבע", (dialog, which) ->
                        setState(event.id, EventStore.SCHEDULED))
                .setNegativeButton("עדיין לא", (dialog, which) -> refresh())
                .show();
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

    private List<Uri> selectedUris(Intent data) {
        List<Uri> uris = new ArrayList<>();
        ClipData clip = data.getClipData();
        if (clip != null) {
            for (int i = 0; i < clip.getItemCount(); i++) uris.add(clip.getItemAt(i).getUri());
        } else if (data.getData() != null) {
            uris.add(data.getData());
        }
        return uris;
    }

    private void importUri(Uri uri) {
        if (uri == null) return;
        importUris(Collections.singletonList(uri));
    }

    private void importUris(List<Uri> uris) {
        if (uris.isEmpty()) return;
        worker.execute(() -> {
            int events = 0;
            int chats = 0;
            String failure = null;
            for (Uri uri : uris) {
                try {
                    events += importOne(uri);
                    chats++;
                } catch (Exception error) {
                    failure = error.getMessage();
                }
            }
            int foundEvents = events;
            int readChats = chats;
            String reason = failure;
            shownState = EventStore.PENDING;
            List<EventCandidate> shown = store.byState(shownState);
            runOnUiThread(() -> {
                status.setText(importSummary(foundEvents, readChats, uris.size(), reason));
                paintTabs();
                render(shown);
            });
        });
    }

    /** Runs on the worker: a multi-year export is far too slow for the UI thread. */
    private int importOne(Uri uri) throws IOException {
        String name = displayName(uri);
        String content;
        try (InputStream input = getContentResolver().openInputStream(uri)) {
            content = name.toLowerCase(Locale.ROOT).endsWith(".zip")
                    ? readTxtFromZip(input) : readAll(input);
        }
        List<EventCandidate> found = parser.parseExport(content, name);
        store.upsertAll(found);
        return found.size();
    }

    private String importSummary(int events, int chats, int requested, String failure) {
        if (chats == 0) return "הייבוא נכשל: " + failure;
        String summary = "נמצאו " + events + " אירועים מתוך " + chats
                + (chats == 1 ? " שיחה" : " שיחות");
        return requested > chats ? summary + " · " + (requested - chats) + " נכשלו" : summary;
    }

    private void importText(String content, String source) {
        List<EventCandidate> found = parser.parseExport(content, source);
        store.upsertAll(found);
        shownState = EventStore.PENDING;
        List<EventCandidate> shown = store.byState(shownState);
        runOnUiThread(() -> {
            status.setText("נמצאו " + found.size() + " אירועים לבדיקה");
            paintTabs();
            render(shown);
        });
    }

    private void refresh() {
        int state = shownState;
        worker.execute(() -> {
            List<EventCandidate> events = store.byState(state);
            runOnUiThread(() -> render(events));
        });
    }

    private void setState(String id, int state) {
        worker.execute(() -> {
            store.setState(id, state);
            List<EventCandidate> events = store.byState(shownState);
            runOnUiThread(() -> render(events));
        });
    }

    private void render(List<EventCandidate> events) {
        cards.removeAllViews();
        if (events.isEmpty()) {
            TextView empty = text(emptyMessage(), 17, Color.rgb(180, 184, 205));
            empty.setGravity(Gravity.CENTER);
            empty.setPadding(dp(10), dp(80), dp(10), dp(20));
            cards.addView(empty);
            return;
        }
        for (EventCandidate event : events) cards.addView(eventCard(event));
    }

    private String emptyMessage() {
        if (shownState == EventStore.SCHEDULED) {
            return "עדיין לא סימנת אירוע כנקבע.\nאחרי שתפתח אירוע ביומן ותאשר, הוא יופיע כאן.";
        }
        if (shownState == EventStore.DISMISSED) return "לא סימנת שום אירוע כלא רלוונטי.";
        return "עדיין אין אירועים לבדיקה.\nייצא שיחת WhatsApp ללא מדיה ושתף אותה ל־WhatsPlan.";
    }

    private View eventCard(EventCandidate event) {
        LinearLayout card = column();
        card.setPadding(dp(16), dp(16), dp(16), dp(16));
        card.setBackgroundColor(Color.rgb(31, 33, 46));
        TextView title = text(event.title, 19, Color.WHITE);
        title.setTypeface(null, Typeface.BOLD);
        card.addView(title);

        String when = event.start == null ? "תאריך/שעה דורשים השלמה" :
                event.start.format(DateTimeFormatter.ofPattern("EEEE, d.M.yyyy · HH:mm",
                        new Locale("he", "IL")));
        card.addView(text(when, 16, Color.rgb(181, 169, 255)));
        if (event.recurrence != null) {
            card.addView(text("חוזר: " + recurrenceLabel(event.recurrence), 14,
                    Color.rgb(130, 226, 179)));
        }
        if (event.location != null) card.addView(text("מקום: " + event.location, 14, Color.WHITE));
        card.addView(text("ודאות: " + event.confidence + "% · " + statusLabel(event), 13, MUTED));
        String conversation = event.groupConversation
                ? "קבוצה: " + event.conversationName + " · שולח: " + event.sender
                : "שיחה עם: " + event.sender;
        card.addView(text(conversation + "\n“" + shorten(event.evidence) + "”", 13, MUTED));
        card.addView(cardButtons(event));
        return card;
    }

    private View cardButtons(EventCandidate event) {
        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        if (shownState == EventStore.PENDING) {
            Button calendar = button(event.status == EventCandidate.Status.CANCELLED
                    ? "סמן כטופל" : "פתח ביומן");
            calendar.setEnabled(event.start != null
                    || event.status == EventCandidate.Status.CANCELLED);
            calendar.setOnClickListener(v -> {
                if (event.status == EventCandidate.Status.CANCELLED) {
                    setState(event.id, EventStore.DISMISSED);
                } else {
                    openCalendar(event);
                }
            });
            Button dismiss = button("לא רלוונטי");
            dismiss.setOnClickListener(v -> setState(event.id, EventStore.DISMISSED));
            addSideBySide(buttons, calendar, dismiss);
        } else {
            Button back = button("החזר לבדיקה");
            back.setOnClickListener(v -> setState(event.id, EventStore.PENDING));
            buttons.addView(back, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, dp(48)));
        }
        return buttons;
    }

    private void addSideBySide(LinearLayout row, View first, View second) {
        row.addView(first, new LinearLayout.LayoutParams(0, dp(48), 1));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, dp(48), 1);
        params.setMarginStart(dp(8));
        row.addView(second, params);
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
        if (event.recurrence != null) {
            intent.putExtra(CalendarContract.Events.RRULE, event.recurrence);
        }
        awaitingCalendar = event;
        startActivityForResult(intent, OPEN_CALENDAR);
    }

    private String recurrenceLabel(String rrule) {
        if (rrule.startsWith("FREQ=MONTHLY")) return "כל חודש";
        int day = rrule.indexOf("BYDAY=");
        if (day < 0) return "כל שבוע";
        String code = rrule.substring(day + 6);
        Map<String, String> names = new HashMap<>();
        names.put("SU", "ראשון");
        names.put("MO", "שני");
        names.put("TU", "שלישי");
        names.put("WE", "רביעי");
        names.put("TH", "חמישי");
        names.put("FR", "שישי");
        names.put("SA", "שבת");
        String name = names.get(code);
        return name == null ? "כל שבוע" : "כל יום " + name;
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

    private LinearLayout column() {
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
        button.setAllCaps(false);
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
