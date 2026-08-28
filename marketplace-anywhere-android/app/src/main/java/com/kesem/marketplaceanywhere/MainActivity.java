package com.kesem.marketplaceanywhere;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

public class MainActivity extends Activity {
    private static final String PREFS = "marketplace_anywhere_prefs";
    private static final String KEY_SAVED_LOCATIONS = "saved_locations";

    private final List<LocationItem> locations = new ArrayList<>();
    private EditText query;
    private EditText customLocation;
    private EditText locationLabel;
    private EditText minPrice;
    private EditText maxPrice;
    private Spinner locationSpinner;
    private Spinner radiusSpinner;
    private Spinner sortSpinner;
    private Spinner ageSpinner;
    private ArrayAdapter<LocationItem> locationAdapter;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        setContentView(buildUi());
        loadSavedState();
    }

    private View buildUi() {
        int pad = dp(18);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);
        root.setBackgroundColor(Color.rgb(245, 247, 250));
        root.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);

        TextView title = text("Marketplace Anywhere", 28, true);
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(title, matchWrap());

        TextView note = text("משגר חיפוש אישי. אין התחברות בתוך האפליקציה, אין קריאת מודעות, אין מעקב ואין הרשאות. החיפוש נפתח ישירות ב־Facebook או בדפדפן.", 15, false);
        note.setPadding(0, dp(10), 0, dp(14));
        root.addView(note, matchWrap());

        addLabel(root, "מה מחפשים?");
        query = input("למשל: Fender Bass, RME UCX, Neumann U87", InputType.TYPE_CLASS_TEXT);
        root.addView(query, matchWrap());

        addLabel(root, "מיקום מוכן");
        locationSpinner = new Spinner(this);
        locationAdapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, locations);
        locationSpinner.setAdapter(locationAdapter);
        root.addView(locationSpinner, matchWrap());
        reloadLocations();

        addLabel(root, "מיקום מותאם אישית — אופציונלי");
        customLocation = input("עיר באנגלית, מזהה מיקום או קישור Marketplace מלא", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        root.addView(customLocation, matchWrap());
        TextView locationHelp = text("שדה זה גובר על הרשימה. הדרך היציבה ביותר: פתח Marketplace, בחר מיקום, העתק את הקישור והדבק כאן.", 13, false);
        locationHelp.setTextColor(Color.rgb(80, 90, 105));
        locationHelp.setPadding(0, dp(6), 0, dp(4));
        root.addView(locationHelp, matchWrap());

        addLabel(root, "שם לשמירת המיקום");
        locationLabel = input("למשל: ברלין — ציוד אולפן", InputType.TYPE_CLASS_TEXT);
        root.addView(locationLabel, matchWrap());

        LinearLayout saveRow = horizontalRow();
        Button saveLocation = button("שמור מיקום");
        saveLocation.setOnClickListener(v -> saveLocation());
        saveRow.addView(saveLocation, weighted());
        Button deleteLocation = button("מחק מיקום שמור");
        deleteLocation.setOnClickListener(v -> deleteSelectedLocation());
        saveRow.addView(deleteLocation, weighted());
        root.addView(saveRow, matchWrap());

        addLabel(root, "רדיוס חיפוש");
        radiusSpinner = stringSpinner(new String[]{"5 ק״מ", "20 ק״מ", "50 ק״מ", "100 ק״מ", "250 ק״מ", "500 ק״מ"});
        radiusSpinner.setSelection(3);
        root.addView(radiusSpinner, matchWrap());

        LinearLayout priceRow = horizontalRow();
        LinearLayout minColumn = verticalColumn();
        addLabel(minColumn, "מחיר מינימום");
        minPrice = input("לא חובה", InputType.TYPE_CLASS_NUMBER);
        minColumn.addView(minPrice, matchWrap());
        priceRow.addView(minColumn, weighted());
        LinearLayout maxColumn = verticalColumn();
        addLabel(maxColumn, "מחיר מקסימום");
        maxPrice = input("לא חובה", InputType.TYPE_CLASS_NUMBER);
        maxColumn.addView(maxPrice, matchWrap());
        priceRow.addView(maxColumn, weighted());
        root.addView(priceRow, matchWrap());

        addLabel(root, "מיון");
        sortSpinner = stringSpinner(new String[]{"החדש ביותר", "הקרוב ביותר", "הזול ביותר", "היקר ביותר", "מומלץ"});
        root.addView(sortSpinner, matchWrap());

        addLabel(root, "מתי פורסם?");
        ageSpinner = stringSpinner(new String[]{"הכול", "ב־24 השעות האחרונות", "ב־7 הימים האחרונים", "ב־30 הימים האחרונים"});
        root.addView(ageSpinner, matchWrap());

        Button search = button("פתח חיפוש ב־Facebook Marketplace");
        search.setTextSize(17);
        search.setOnClickListener(v -> openSearch());
        LinearLayout.LayoutParams searchParams = matchWrap();
        searchParams.topMargin = dp(18);
        root.addView(search, searchParams);

        Button marketplace = button("פתח את בורר המיקום של Facebook");
        marketplace.setOnClickListener(v -> openUrl("https://www.facebook.com/marketplace/"));
        root.addView(marketplace, matchWrap());

        TextView limitation = text("Facebook עשויה לשנות קישורים, להתאים תוצאות לחשבון או לא לאפשר פנייה למוכר במדינה אחרת. האפליקציה אינה עוקפת שום מגבלה.", 13, false);
        limitation.setTextColor(Color.rgb(95, 73, 25));
        limitation.setPadding(0, dp(16), 0, dp(8));
        root.addView(limitation, matchWrap());

        ScrollView scroll = new ScrollView(this);
        scroll.addView(root);
        return scroll;
    }

    private void openSearch() {
        String term = query.getText().toString().trim();
        if (term.isEmpty()) {
            toast("כתוב קודם מה לחפש");
            query.requestFocus();
            return;
        }

        String rawLocation = customLocation.getText().toString().trim();
        LocationItem selected = (LocationItem) locationSpinner.getSelectedItem();
        String token = rawLocation.isEmpty() ? selected.token : extractLocationToken(rawLocation);
        if (!rawLocation.isEmpty() && token.isEmpty()) {
            toast("לא הצלחתי לזהות את המיקום. הדבק קישור Marketplace מלא או כתוב שם עיר באנגלית");
            customLocation.requestFocus();
            return;
        }

        String base = token.isEmpty()
                ? "https://www.facebook.com/marketplace/search/"
                : "https://www.facebook.com/marketplace/" + Uri.encode(token) + "/search/";

        Uri.Builder builder = Uri.parse(base).buildUpon()
                .appendQueryParameter("query", term)
                .appendQueryParameter("radius", radiusValue())
                .appendQueryParameter("deliveryMethod", "local_pick_up");

        String min = minPrice.getText().toString().trim();
        String max = maxPrice.getText().toString().trim();
        if (!min.isEmpty()) builder.appendQueryParameter("minPrice", min);
        if (!max.isEmpty()) builder.appendQueryParameter("maxPrice", max);

        String sort = sortValue();
        if (!sort.isEmpty()) builder.appendQueryParameter("sortBy", sort);
        String days = ageValue();
        if (!days.isEmpty()) builder.appendQueryParameter("daysSinceListed", days);

        saveState();
        openUrl(builder.build().toString());
    }

    private String extractLocationToken(String raw) {
        String value = raw.trim();
        if (value.contains("facebook.com")) {
            try {
                Uri uri = Uri.parse(value);
                List<String> parts = uri.getPathSegments();
                for (int i = 0; i < parts.size() - 1; i++) {
                    if ("marketplace".equalsIgnoreCase(parts.get(i))) {
                        String candidate = parts.get(i + 1);
                        if (!candidate.equalsIgnoreCase("search")
                                && !candidate.equalsIgnoreCase("item")
                                && !candidate.equalsIgnoreCase("category")) {
                            return candidate;
                        }
                    }
                }
                return "";
            } catch (Exception ignored) {
                return "";
            }
        }
        if (value.matches("[0-9]{5,}")) return value;
        String normalized = Normalizer.normalize(value, Normalizer.Form.NFD)
                .replaceAll("\\p{M}", "")
                .toLowerCase(Locale.ROOT)
                .replaceAll("[^a-z0-9]+", "");
        return normalized;
    }

    private void saveLocation() {
        String raw = customLocation.getText().toString().trim();
        String token = extractLocationToken(raw);
        if (token.isEmpty()) {
            toast("הוסף מיקום מותאם אישית לפני השמירה");
            return;
        }
        String label = locationLabel.getText().toString().trim();
        if (label.isEmpty()) label = raw;
        label = label.replace("|", " ").replace("\n", " ").trim();
        Set<String> saved = new LinkedHashSet<>(prefs.getStringSet(KEY_SAVED_LOCATIONS, new LinkedHashSet<>()));
        saved.removeIf(item -> item.endsWith("|" + token));
        saved.add(label + "|" + token);
        prefs.edit().putStringSet(KEY_SAVED_LOCATIONS, saved).apply();
        reloadLocations();
        selectToken(token);
        toast("המיקום נשמר במכשיר");
    }

    private void deleteSelectedLocation() {
        LocationItem selected = (LocationItem) locationSpinner.getSelectedItem();
        if (selected == null || !selected.saved) {
            toast("בחר מיקום ששמרת בעצמך");
            return;
        }
        Set<String> saved = new LinkedHashSet<>(prefs.getStringSet(KEY_SAVED_LOCATIONS, new LinkedHashSet<>()));
        saved.removeIf(item -> item.endsWith("|" + selected.token));
        prefs.edit().putStringSet(KEY_SAVED_LOCATIONS, saved).apply();
        reloadLocations();
        toast("המיקום נמחק");
    }

    private void reloadLocations() {
        locations.clear();
        locations.add(new LocationItem("ללא מיקום מוגדר — Facebook יבחר", "", false));
        locations.add(new LocationItem("ישראל — תל אביב", "telaviv", false));
        locations.add(new LocationItem("ארה״ב — ניו יורק", "newyork", false));
        locations.add(new LocationItem("ארה״ב — לוס אנג׳לס", "la", false));
        locations.add(new LocationItem("בריטניה — לונדון", "london", false));
        locations.add(new LocationItem("גרמניה — ברלין", "berlin", false));
        locations.add(new LocationItem("צרפת — פריז", "paris", false));
        locations.add(new LocationItem("ספרד — מדריד", "madrid", false));
        locations.add(new LocationItem("איטליה — רומא", "rome", false));
        locations.add(new LocationItem("הולנד — אמסטרדם", "amsterdam", false));
        locations.add(new LocationItem("יפן — טוקיו", "tokyo", false));
        locations.add(new LocationItem("קנדה — טורונטו", "toronto", false));
        locations.add(new LocationItem("אוסטרליה — סידני", "sydney", false));

        Set<String> saved = prefs == null
                ? new LinkedHashSet<>()
                : prefs.getStringSet(KEY_SAVED_LOCATIONS, new LinkedHashSet<>());
        for (String entry : saved) {
            int split = entry.lastIndexOf('|');
            if (split > 0 && split < entry.length() - 1) {
                locations.add(new LocationItem("★ " + entry.substring(0, split), entry.substring(split + 1), true));
            }
        }
        if (locationAdapter != null) locationAdapter.notifyDataSetChanged();
    }

    private void loadSavedState() {
        query.setText(prefs.getString("query", ""));
        customLocation.setText(prefs.getString("custom_location", ""));
        minPrice.setText(prefs.getString("min_price", ""));
        maxPrice.setText(prefs.getString("max_price", ""));
        radiusSpinner.setSelection(prefs.getInt("radius_index", 3));
        sortSpinner.setSelection(prefs.getInt("sort_index", 0));
        ageSpinner.setSelection(prefs.getInt("age_index", 0));
        selectToken(prefs.getString("selected_token", "telaviv"));
    }

    private void saveState() {
        LocationItem selected = (LocationItem) locationSpinner.getSelectedItem();
        prefs.edit()
                .putString("query", query.getText().toString())
                .putString("custom_location", customLocation.getText().toString())
                .putString("min_price", minPrice.getText().toString())
                .putString("max_price", maxPrice.getText().toString())
                .putInt("radius_index", radiusSpinner.getSelectedItemPosition())
                .putInt("sort_index", sortSpinner.getSelectedItemPosition())
                .putInt("age_index", ageSpinner.getSelectedItemPosition())
                .putString("selected_token", selected == null ? "" : selected.token)
                .apply();
    }

    private void selectToken(String token) {
        for (int i = 0; i < locations.size(); i++) {
            if (locations.get(i).token.equals(token)) {
                locationSpinner.setSelection(i);
                return;
            }
        }
    }

    private String radiusValue() {
        String[] values = {"5", "20", "50", "100", "250", "500"};
        return values[Math.max(0, Math.min(radiusSpinner.getSelectedItemPosition(), values.length - 1))];
    }

    private String sortValue() {
        String[] values = {"creation_time_descend", "distance_ascend", "price_ascend", "price_descend", ""};
        return values[Math.max(0, Math.min(sortSpinner.getSelectedItemPosition(), values.length - 1))];
    }

    private String ageValue() {
        String[] values = {"", "1", "7", "30"};
        return values[Math.max(0, Math.min(ageSpinner.getSelectedItemPosition(), values.length - 1))];
    }

    private void openUrl(String url) {
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            startActivity(intent);
        } catch (Exception e) {
            toast("לא נמצאה אפליקציה שיכולה לפתוח את הקישור");
        }
    }

    private TextView text(String value, int size, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(Color.rgb(20, 31, 50));
        if (bold) view.setTypeface(view.getTypeface(), android.graphics.Typeface.BOLD);
        return view;
    }

    private void addLabel(LinearLayout parent, String value) {
        TextView label = text(value, 14, true);
        label.setPadding(0, dp(12), 0, dp(5));
        parent.addView(label, matchWrap());
    }

    private EditText input(String hint, int type) {
        EditText field = new EditText(this);
        field.setHint(hint);
        field.setSingleLine(true);
        field.setInputType(type);
        field.setTextDirection(View.TEXT_DIRECTION_LOCALE);
        return field;
    }

    private Spinner stringSpinner(String[] values) {
        Spinner spinner = new Spinner(this);
        spinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, values));
        return spinner;
    }

    private Button button(String value) {
        Button button = new Button(this);
        button.setText(value);
        button.setAllCaps(false);
        return button;
    }

    private LinearLayout horizontalRow() {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        return row;
    }

    private LinearLayout verticalColumn() {
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        return column;
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
    }

    private LinearLayout.LayoutParams weighted() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        params.setMarginEnd(dp(5));
        return params;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void toast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show();
    }

    private static final class LocationItem {
        final String label;
        final String token;
        final boolean saved;

        LocationItem(String label, String token, boolean saved) {
            this.label = label;
            this.token = token;
            this.saved = saved;
        }

        @Override
        public String toString() {
            return label;
        }
    }
}
