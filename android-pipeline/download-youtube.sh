#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# הורדת אודיו מיוטיוב ושליחה לצינור העבודה
#
# שימוש:
#   bash download-youtube.sh "https://www.youtube.com/watch?v=VIDEO_ID"
#   bash download-youtube.sh "https://youtu.be/VIDEO_ID"
#
# דורש: pip install yt-dlp (מותקן אוטומטית)
# ============================================================
set -e

URL="$1"

if [ -z "$URL" ]; then
    echo "שימוש: bash download-youtube.sh <youtube-url>"
    exit 1
fi

# בדיקה/התקנה של yt-dlp
if ! command -v yt-dlp &>/dev/null; then
    echo "=== מתקין yt-dlp ==="
    pip install yt-dlp
fi

WORK="$HOME/audio-pipeline/input"
mkdir -p "$WORK"

echo "=== מוריד אודיו מ-YouTube ==="
cd "$WORK"
yt-dlp \
    -x \
    --audio-format mp3 \
    --audio-quality 0 \
    -o "%(title)s.%(ext)s" \
    "$URL"

# מצא את הקובץ האחרון שהורד
LATEST=$(ls -t "$WORK"/*.mp3 2>/dev/null | head -1)

if [ -z "$LATEST" ]; then
    echo "שגיאה: ההורדה נכשלה"
    exit 1
fi

echo ""
echo "✓ הורד: $LATEST"
echo ""
echo "להמשך — הרץ:"
echo "  bash pipeline.sh \"$LATEST\""
