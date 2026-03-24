#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# שלב 2 — בדיקת תמלול בסיסית
# מריץ whisper על קובץ הדוגמה המובנה
# ============================================================
set -e

WHISPER="$HOME/whisper.cpp"
CLI="$WHISPER/build/bin/whisper-cli"
MODEL="$WHISPER/models/ggml-tiny.bin"

if [ ! -f "$CLI" ]; then
    echo "שגיאה: whisper-cli לא נמצא. הרץ קודם: bash setup.sh"
    exit 1
fi

if [ ! -f "$MODEL" ]; then
    echo "שגיאה: מודל לא נמצא. מוריד..."
    cd "$WHISPER" && bash models/download-ggml-model.sh tiny
fi

# שימוש בקובץ הדוגמה המובנה של whisper.cpp
SAMPLE="$WHISPER/samples/jfk.wav"
if [ ! -f "$SAMPLE" ]; then
    echo "שגיאה: קובץ דוגמה לא נמצא"
    exit 1
fi

echo "=== מתמלל קובץ דוגמה (JFK) ==="
"$CLI" -m "$MODEL" -f "$SAMPLE" --print-progress --output-txt

echo ""
echo "=== תוצאה ==="
cat "$WHISPER/samples/jfk.wav.txt" 2>/dev/null || echo "(הפלט הודפס למעלה)"
echo ""
echo "אם ראית תמלול באנגלית — whisper עובד!"
echo "המשך לשלב הבא: bash pipeline.sh <קובץ_אודיו_או_וידאו>"
