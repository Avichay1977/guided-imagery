package com.whatsplan.app;

import android.content.Intent;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.TextView;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.Shadows;
import org.robolectric.android.controller.ActivityController;
import org.robolectric.annotation.Config;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.AbstractExecutorService;
import java.util.concurrent.TimeUnit;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

/**
 * Drives the real screen: shares a chat into the app, walks the tabs, selects
 * everything and exports it. The parser was already covered; this is the part
 * that only shows up when the app actually runs.
 */
@RunWith(RobolectricTestRunner.class)
@Config(sdk = 34)
public final class AppFlowTest {

    private static final String CHAT =
            "01.06.2026, 10:31 - אבי: סגרנו חזרה ביום רביעי ב-20:00 אצל אולפן קסם\n" +
            "07.06.2026, 12:00 - אבי: יש לנו הופעה ב-22.07 בשעה 19:30 בלבונטין\n" +
            "08.06.2026, 20:30 - אבי: קבענו חזרה כל יום שלישי ב-20:00\n" +
            "10.06.2026, 07:30 - נועה: אני מאחר ב-20 דקות לחזרה\n";

    private ActivityController<MainActivity> launchWithChat() {
        Intent shared = new Intent(Intent.ACTION_SEND)
                .putExtra(Intent.EXTRA_TEXT, CHAT);
        ActivityController<MainActivity> controller =
                Robolectric.buildActivity(MainActivity.class, shared);
        // The framework under test is single threaded, so the app's worker runs
        // inline here. Everything else is the real code path.
        controller.get().worker = new Inline();
        controller.setup();
        settle();
        return controller;
    }

    private void settle() {
        Shadows.shadowOf(Looper.getMainLooper()).idle();
    }

    private static final class Inline extends AbstractExecutorService {
        private boolean stopped;

        @Override public void execute(Runnable command) {
            command.run();
        }

        @Override public void shutdown() {
            stopped = true;
        }

        @Override public List<Runnable> shutdownNow() {
            stopped = true;
            return new ArrayList<>();
        }

        @Override public boolean isShutdown() {
            return stopped;
        }

        @Override public boolean isTerminated() {
            return stopped;
        }

        @Override public boolean awaitTermination(long timeout, TimeUnit unit) {
            return true;
        }
    }

    @Test public void sharingAChatFillsTheReviewList() {
        MainActivity activity = launchWithChat().get();
        List<CheckBox> picks = viewsOfType(root(activity), CheckBox.class);
        assertEquals("three real events, and no rehearsal invented by the late message",
                3, picks.size());
        assertTrue(texts(picks).toString().contains("חזרה"));
        assertTrue(texts(picks).toString().contains("הופעה"));
    }

    @Test public void theStatusLineReportsWhatWasFound() {
        MainActivity activity = launchWithChat().get();
        assertTrue("status should report the import: " + texts(viewsOfType(root(activity), TextView.class)),
                texts(viewsOfType(root(activity), TextView.class)).toString().contains("נמצאו 3"));
    }

    @Test public void scheduledTabIsEmptyUntilSomethingIsScheduled() {
        MainActivity activity = launchWithChat().get();
        click(activity, "נקבעו");
        settle();
        assertTrue(viewsOfType(root(activity), CheckBox.class).isEmpty());
        assertTrue(texts(viewsOfType(root(activity), TextView.class)).toString()
                .contains("עדיין לא סימנת אירוע כנקבע"));
    }

    @Test public void selectingEverythingAndExportingWritesOneCalendarFile() throws Exception {
        MainActivity activity = launchWithChat().get();
        click(activity, "בחר הכל");
        settle();

        Button export = findStartingWith(activity, "ייצוא כקובץ יומן");
        assertNotNull("export button missing", export);
        assertTrue("export should be enabled once events are selected", export.isEnabled());
        export.performClick();
        settle();

        File file = new File(activity.getCacheDir(), "whatsplan.ics");
        assertTrue("no calendar file was written", file.exists());
        String ics = new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8);
        assertEquals("every selected event belongs in the file",
                3, count(ics, "BEGIN:VEVENT"));
        assertTrue("the weekly rehearsal must stay repeating",
                ics.contains("RRULE:FREQ=WEEKLY;BYDAY=TU"));

        Intent started = Shadows.shadowOf(activity).getNextStartedActivity();
        assertNotNull("nothing was launched for the calendar file", started);
        assertEquals(Intent.ACTION_VIEW, started.getAction());
        assertEquals("text/calendar", started.getType());
        assertEquals("content://com.whatsplan.app.calendar/whatsplan.ics",
                String.valueOf(started.getData()));
    }

    @Test public void dismissingEverythingClearsTheReviewList() {
        MainActivity activity = launchWithChat().get();
        click(activity, "בחר הכל");
        settle();
        Button dismiss = findStartingWith(activity, "סמן הכל כלא רלוונטי");
        assertNotNull(dismiss);
        dismiss.performClick();
        settle();

        assertTrue("review list should be empty",
                viewsOfType(root(activity), CheckBox.class).isEmpty());
        click(activity, "לא רלוונטי");
        settle();
        assertEquals("everything moved to the dismissed tab",
                3, viewsOfType(root(activity), TextView.class).stream()
                        .filter(view -> String.valueOf(view.getText()).startsWith("חזרה")
                                || String.valueOf(view.getText()).startsWith("הופעה"))
                        .count());
    }

    private View root(MainActivity activity) {
        return activity.findViewById(android.R.id.content);
    }

    private void click(MainActivity activity, String label) {
        Button button = findStartingWith(activity, label);
        assertNotNull("button not found: " + label, button);
        button.performClick();
    }

    private Button findStartingWith(MainActivity activity, String label) {
        for (Button button : viewsOfType(root(activity), Button.class)) {
            if (String.valueOf(button.getText()).startsWith(label)) return button;
        }
        return null;
    }

    private <T extends View> List<T> viewsOfType(View view, Class<T> type) {
        List<T> found = new ArrayList<>();
        collect(view, type, found);
        return found;
    }

    private <T extends View> void collect(View view, Class<T> type, List<T> found) {
        // CheckBox extends Button, so the exact class keeps the two apart.
        if (view.getClass() == type) found.add(type.cast(view));
        if (!(view instanceof ViewGroup)) return;
        ViewGroup group = (ViewGroup) view;
        for (int i = 0; i < group.getChildCount(); i++) collect(group.getChildAt(i), type, found);
    }

    private List<String> texts(List<? extends TextView> views) {
        List<String> values = new ArrayList<>();
        for (TextView view : views) values.add(String.valueOf(view.getText()));
        return values;
    }

    private int count(String haystack, String needle) {
        int total = 0;
        int at = haystack.indexOf(needle);
        while (at >= 0) {
            total++;
            at = haystack.indexOf(needle, at + needle.length());
        }
        return total;
    }
}
