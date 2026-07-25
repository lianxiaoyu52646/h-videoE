package com.videoenglish.app;

import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

public class DictionaryDatabaseHelper extends SQLiteOpenHelper {

    private static final String TAG = "DictionaryDB";
    private static final String DATABASE_NAME = "dictionary.db";
    private static final int DATABASE_VERSION = 1;

    private final Context mContext;
    private SQLiteDatabase mDatabase;
    private boolean mIsDatabaseReady = false;

    public DictionaryDatabaseHelper(Context context) {
        super(context, DATABASE_NAME, null, DATABASE_VERSION);
        this.mContext = context;
        initDatabase();
    }

    private void initDatabase() {
        File dbFile = mContext.getDatabasePath(DATABASE_NAME);
        if (!dbFile.exists()) {
            copyDatabaseFromAssets();
        }
        try {
            mDatabase = SQLiteDatabase.openDatabase(dbFile.getPath(), null, SQLiteDatabase.OPEN_READONLY);
            mIsDatabaseReady = true;
            Log.d(TAG, "Database opened successfully");
        } catch (Exception e) {
            Log.e(TAG, "Failed to open database: " + e.getMessage());
        }
    }

    private void copyDatabaseFromAssets() {
        try {
            InputStream inputStream = mContext.getAssets().open(DATABASE_NAME);
            File dbFile = mContext.getDatabasePath(DATABASE_NAME);
            File parentDir = dbFile.getParentFile();
            if (!parentDir.exists()) {
                parentDir.mkdirs();
            }
            OutputStream outputStream = new FileOutputStream(dbFile);
            byte[] buffer = new byte[8192];
            int length;
            while ((length = inputStream.read(buffer)) > 0) {
                outputStream.write(buffer, 0, length);
            }
            outputStream.flush();
            outputStream.close();
            inputStream.close();
            Log.d(TAG, "Database copied from assets");
        } catch (IOException e) {
            Log.e(TAG, "Failed to copy database: " + e.getMessage());
        }
    }

    public boolean isReady() {
        return mIsDatabaseReady;
    }

    public String lookupWord(String word) {
        if (!mIsDatabaseReady || word == null || word.trim().isEmpty()) {
            return null;
        }

        String result = null;
        Cursor cursor = null;

        try {
            cursor = mDatabase.query(
                    "words",
                    new String[]{"word", "phonetic", "translation", "exchange", "tags"},
                    "word = ?",
                    new String[]{word.toLowerCase()},
                    null, null, null
            );

            if (cursor != null && cursor.moveToFirst()) {
                StringBuilder sb = new StringBuilder();
                sb.append("{");
                sb.append("\"word\":\"").append(escapeJson(cursor.getString(0))).append("\",");
                sb.append("\"phonetic\":\"").append(escapeJson(cursor.getString(1))).append("\",");
                sb.append("\"translation\":\"").append(escapeJson(cursor.getString(2))).append("\",");
                sb.append("\"exchange\":\"").append(escapeJson(cursor.getString(3))).append("\",");
                sb.append("\"tags\":\"").append(escapeJson(cursor.getString(4))).append("\"");
                sb.append("}");
                result = sb.toString();
            }
        } catch (Exception e) {
            Log.e(TAG, "Lookup error: " + e.getMessage());
        } finally {
            if (cursor != null) {
                cursor.close();
            }
        }

        return result;
    }

    public String fuzzySearch(String keyword) {
        if (!mIsDatabaseReady || keyword == null || keyword.trim().isEmpty()) {
            return "[]";
        }

        StringBuilder result = new StringBuilder();
        result.append("[");
        Cursor cursor = null;

        try {
            cursor = mDatabase.rawQuery(
                    "SELECT word, phonetic, translation FROM words WHERE word LIKE ? LIMIT 20",
                    new String[]{keyword.toLowerCase() + "%"}
            );

            boolean first = true;
            while (cursor != null && cursor.moveToNext()) {
                if (!first) {
                    result.append(",");
                }
                first = false;
                result.append("{");
                result.append("\"word\":\"").append(escapeJson(cursor.getString(0))).append("\",");
                result.append("\"phonetic\":\"").append(escapeJson(cursor.getString(1))).append("\",");
                result.append("\"translation\":\"").append(escapeJson(cursor.getString(2))).append("\"");
                result.append("}");
            }
        } catch (Exception e) {
            Log.e(TAG, "Fuzzy search error: " + e.getMessage());
        } finally {
            if (cursor != null) {
                cursor.close();
            }
        }

        result.append("]");
        return result.toString();
    }

    public int getWordCount() {
        if (!mIsDatabaseReady) {
            return 0;
        }

        Cursor cursor = null;
        try {
            cursor = mDatabase.rawQuery("SELECT COUNT(*) FROM words", null);
            if (cursor != null && cursor.moveToFirst()) {
                return cursor.getInt(0);
            }
        } catch (Exception e) {
            Log.e(TAG, "Count error: " + e.getMessage());
        } finally {
            if (cursor != null) {
                cursor.close();
            }
        }
        return 0;
    }

    private String escapeJson(String value) {
        if (value == null) {
            return "";
        }
        return value.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }

    @Override
    public void onCreate(SQLiteDatabase db) {
    }

    @Override
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
    }

    public void closeDatabase() {
        if (mDatabase != null && mDatabase.isOpen()) {
            mDatabase.close();
        }
    }
}