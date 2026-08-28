package com.whatsplan.app;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;

import java.io.File;
import java.io.FileNotFoundException;

/**
 * Hands the generated calendar file to the calendar app and nothing else. A
 * file:// URI is refused by Android, and the app carries no support library, so
 * this serves the one file from the private cache under a granted permission.
 */
public final class IcsProvider extends ContentProvider {
    static final String AUTHORITY = "com.whatsplan.app.calendar";
    static final String FILE_NAME = "whatsplan.ics";

    static File file(Context context) {
        return new File(context.getCacheDir(), FILE_NAME);
    }

    static Uri uri() {
        return Uri.parse("content://" + AUTHORITY + "/" + FILE_NAME);
    }

    @Override public boolean onCreate() {
        return true;
    }

    @Override public ParcelFileDescriptor openFile(Uri uri, String mode)
            throws FileNotFoundException {
        if (!FILE_NAME.equals(uri.getLastPathSegment())) {
            throw new FileNotFoundException("unknown file");
        }
        return ParcelFileDescriptor.open(file(getContext()), ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override public String getType(Uri uri) {
        return "text/calendar";
    }

    @Override public Cursor query(Uri uri, String[] projection, String selection,
                                  String[] selectionArgs, String sortOrder) {
        MatrixCursor cursor = new MatrixCursor(
                new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE});
        cursor.addRow(new Object[]{FILE_NAME, file(getContext()).length()});
        return cursor;
    }

    @Override public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override public int delete(Uri uri, String selection, String[] selectionArgs) {
        return 0;
    }

    @Override public int update(Uri uri, ContentValues values, String selection,
                                String[] selectionArgs) {
        return 0;
    }
}
