package com.kesem.marketplaceanywhere;

import android.app.Activity;
import android.content.Intent;
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

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
    private EditText query;
    private Spinner country;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(buildUi());
    }

    private View buildUi() {
        int pad = dp(20);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);
        root.setBackgroundColor(Color.rgb(245, 247, 250));

        TextView title = new TextView(this);
        title.setText("Marketplace Anywhere");
        title.setTextSize(27);
        title.setTextColor(Color.rgb(20, 31, 50));
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(title, matchWrap());

        TextView note = new TextView(this);
        note.setText("לשימוש אישי בלבד. האפליקציה לא מתחברת לחשבון, לא קוראת מודעות ולא אוספת מידע. היא רק פותחת חיפוש ב־Facebook Marketplace.");
        note.setTextSize(16);
        note.setPadding(0, dp(14), 0, dp(18));
        root.addView(note, matchWrap());

        query = new EditText(this);
        query.setHint("מה לחפש? למשל: Fender Bass");
        query.setSingleLine(true);
        query.setInputType(InputType.TYPE_CLASS_TEXT);
        root.addView(query, matchWrap());

        country = new Spinner(this);
        String[] countries = {
                "ישראל — Tel Aviv", "ארה״ב — New York", "בריטניה — London",
                "גרמניה — Berlin", "צרפת — Paris", "איטליה — Rome",
                "ספרד — Madrid", "הולנד — Amsterdam", "יפן — Tokyo",
                "אוסטרליה — Sydney", "קנדה — Toronto"
        };
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, countries);
        country.setAdapter(adapter);
        root.addView(country, matchWrap());

        Button search = new Button(this);
        search.setText("פתח חיפוש ב־Facebook Marketplace");
        search.setOnClickListener(v -> openSearch());
        LinearLayout.LayoutParams buttonParams = matchWrap();
        buttonParams.topMargin = dp(18);
        root.addView(search, buttonParams);

        Button marketplace = new Button(this);
        marketplace.setText("פתח Marketplace ללא מילת חיפוש");
        marketplace.setOnClickListener(v -> openUrl("https://www.facebook.com/marketplace/"));
        root.addView(marketplace, matchWrap());

        TextView limitation = new TextView(this);
        limitation.setText("חשוב: Facebook קובע אילו תוצאות ומיקומים יוצגו. האפליקציה לא עוקפת מגבלות אזור, התחברות או כללי Facebook.");
        limitation.setTextSize(14);
        limitation.setPadding(0, dp(18), 0, 0);
        root.addView(limitation, matchWrap());

        ScrollView scroll = new ScrollView(this);
        scroll.addView(root);
        return scroll;
    }

    private void openSearch() {
        String term = query.getText().toString().trim();
        if (term.isEmpty()) {
            Toast.makeText(this, "כתוב קודם מה לחפש", Toast.LENGTH_SHORT).show();
            return;
        }
        String encoded = URLEncoder.encode(term, StandardCharsets.UTF_8).replace("+", "%20");
        openUrl("https://www.facebook.com/marketplace/search/?query=" + encoded);
    }

    private void openUrl(String url) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception e) {
            Toast.makeText(this, "לא נמצאה אפליקציה שיכולה לפתוח את הקישור", Toast.LENGTH_LONG).show();
        }
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
