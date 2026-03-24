#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# העתקת סקריפטים לתיקיית העבודה ב-Termux
# הרץ פעם אחת אחרי setup.sh
# ============================================================
set -e

DEST="$HOME/audio-pipeline"
mkdir -p "$DEST"

# העתק סקריפטים
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cp "$SCRIPT_DIR/pipeline.sh" "$DEST/"
cp "$SCRIPT_DIR/translate.py" "$DEST/"
cp "$SCRIPT_DIR/tts_hebrew.py" "$DEST/"
cp "$SCRIPT_DIR/download-youtube.sh" "$DEST/"
cp "$SCRIPT_DIR/test-whisper.sh" "$DEST/"

chmod +x "$DEST"/*.sh

echo "✓ הסקריפטים הועתקו ל-$DEST/"
echo ""
echo "שימוש:"
echo "  cd $DEST"
echo "  bash pipeline.sh <קובץ>"
echo "  bash download-youtube.sh <youtube-url>"
