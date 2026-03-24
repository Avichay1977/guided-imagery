#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# שלב 1 — התקנת בסיס עבודה ב-Termux
# הרץ פעם אחת: bash setup.sh
# ============================================================
set -e

echo "=== עדכון חבילות Termux ==="
pkg update -y && pkg upgrade -y

echo "=== התקנת כלים בסיסיים ==="
pkg install -y git cmake ffmpeg clang make python python-pip termux-api

echo "=== שכפול whisper.cpp ==="
WHISPER_DIR="$HOME/whisper.cpp"
if [ -d "$WHISPER_DIR" ]; then
    echo "whisper.cpp כבר קיים ב-$WHISPER_DIR"
    cd "$WHISPER_DIR" && git pull
else
    git clone https://github.com/ggml-org/whisper.cpp.git "$WHISPER_DIR"
    cd "$WHISPER_DIR"
fi

echo "=== בניית whisper.cpp ==="
cmake -B build
cmake --build build -j$(nproc)

echo "=== הורדת מודל קטן (tiny) לבדיקה ==="
bash models/download-ggml-model.sh tiny

echo "=== התקנת חבילות Python ==="
pip install edge-tts google-genai

echo "=== יצירת תיקיות עבודה ==="
mkdir -p "$HOME/audio-pipeline/input"
mkdir -p "$HOME/audio-pipeline/output"

echo ""
echo "============================================"
echo "  ההתקנה הושלמה בהצלחה!"
echo "  whisper.cpp: $WHISPER_DIR/build/bin/whisper-cli"
echo "  תיקיית עבודה: $HOME/audio-pipeline/"
echo "============================================"
echo ""
echo "בדיקה מהירה — הרץ:"
echo "  bash test-whisper.sh"
