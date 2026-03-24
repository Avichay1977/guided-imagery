#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# צינור עבודה מלא: אודיו/וידאו → תמלול → תרגום → הקראה
#
# שימוש:
#   bash pipeline.sh video.mp4
#   bash pipeline.sh audio.mp3
#   bash pipeline.sh recording.m4a
#   bash pipeline.sh video.mp4 --model small  (מודל גדול יותר)
#   bash pipeline.sh video.mp4 --lang auto    (זיהוי שפה אוטומטי)
#   bash pipeline.sh video.mp4 --lang en      (כפה אנגלית)
#   bash pipeline.sh video.mp4 --skip-tts     (ללא הקראה)
# ============================================================
set -e

# ── פרמטרים ──
INPUT_FILE="$1"
MODEL_SIZE="tiny"
LANGUAGE="auto"
SKIP_TTS=false

shift || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --model) MODEL_SIZE="$2"; shift 2 ;;
        --lang)  LANGUAGE="$2"; shift 2 ;;
        --skip-tts) SKIP_TTS=true; shift ;;
        *) echo "פרמטר לא מוכר: $1"; exit 1 ;;
    esac
done

if [ -z "$INPUT_FILE" ] || [ ! -f "$INPUT_FILE" ]; then
    echo "שימוש: bash pipeline.sh <קובץ_אודיו_או_וידאו>"
    echo ""
    echo "אפשרויות:"
    echo "  --model tiny|base|small|medium   (ברירת מחדל: tiny)"
    echo "  --lang auto|en|he|ar|...         (ברירת מחדל: auto)"
    echo "  --skip-tts                       (דלג על הקראה עברית)"
    exit 1
fi

# ── נתיבים ──
WHISPER="$HOME/whisper.cpp"
CLI="$WHISPER/build/bin/whisper-cli"
WORK="$HOME/audio-pipeline"
BASENAME=$(basename "${INPUT_FILE%.*}")
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTDIR="$WORK/output/${BASENAME}_${TIMESTAMP}"
mkdir -p "$OUTDIR"

MODEL_FILE="$WHISPER/models/ggml-${MODEL_SIZE}.bin"
if [ ! -f "$MODEL_FILE" ]; then
    echo "=== מוריד מודל $MODEL_SIZE ==="
    cd "$WHISPER" && bash models/download-ggml-model.sh "$MODEL_SIZE"
fi

# ── שלב 1: המרה ל-WAV 16kHz mono ──
echo ""
echo "▶ שלב 1/4 — המרת אודיו..."
WAV_FILE="$OUTDIR/audio.wav"
ffmpeg -i "$INPUT_FILE" -ar 16000 -ac 1 -c:a pcm_s16le "$WAV_FILE" -y -loglevel warning
echo "  ✓ $(du -h "$WAV_FILE" | cut -f1) — $WAV_FILE"

# ── שלב 2: תמלול עם whisper.cpp ──
echo ""
echo "▶ שלב 2/4 — תמלול (מודל: $MODEL_SIZE)..."

WHISPER_ARGS="-m $MODEL_FILE -f $WAV_FILE --print-progress"
if [ "$LANGUAGE" != "auto" ]; then
    WHISPER_ARGS="$WHISPER_ARGS -l $LANGUAGE"
fi

"$CLI" $WHISPER_ARGS --output-txt --output-srt --of "$OUTDIR/transcript"

TRANSCRIPT_FILE="$OUTDIR/transcript.txt"
if [ ! -f "$TRANSCRIPT_FILE" ]; then
    echo "שגיאה: התמלול נכשל"
    exit 1
fi

WORD_COUNT=$(wc -w < "$TRANSCRIPT_FILE")
echo "  ✓ $WORD_COUNT מילים — $TRANSCRIPT_FILE"
echo ""
echo "── תמלול ──"
cat "$TRANSCRIPT_FILE"
echo ""

# ── שלב 3: תרגום לעברית ──
echo ""
echo "▶ שלב 3/4 — תרגום לעברית..."

TRANSLATED_FILE="$OUTDIR/hebrew.txt"
python3 "$HOME/audio-pipeline/translate.py" "$TRANSCRIPT_FILE" "$TRANSLATED_FILE"

if [ -f "$TRANSLATED_FILE" ]; then
    echo "  ✓ $(wc -w < "$TRANSLATED_FILE") מילים — $TRANSLATED_FILE"
    echo ""
    echo "── תרגום עברי ──"
    cat "$TRANSLATED_FILE"
    echo ""
else
    echo "  ✗ התרגום נכשל"
    exit 1
fi

# ── שלב 4: הקראה בעברית (TTS) ──
if [ "$SKIP_TTS" = true ]; then
    echo ""
    echo "▶ שלב 4/4 — דילוג על הקראה (--skip-tts)"
else
    echo ""
    echo "▶ שלב 4/4 — הקראה בעברית..."

    SPEECH_FILE="$OUTDIR/hebrew_speech.mp3"
    python3 "$HOME/audio-pipeline/tts_hebrew.py" "$TRANSLATED_FILE" "$SPEECH_FILE"

    if [ -f "$SPEECH_FILE" ]; then
        echo "  ✓ $(du -h "$SPEECH_FILE" | cut -f1) — $SPEECH_FILE"
    else
        echo "  ✗ ההקראה נכשלה"
        exit 1
    fi
fi

# ── סיכום ──
echo ""
echo "============================================"
echo "  הושלם בהצלחה!"
echo "  תיקייה: $OUTDIR"
echo "  קבצים:"
ls -lh "$OUTDIR/" | grep -v ^total | awk '{print "    " $NF " (" $5 ")"}'
echo "============================================"

if [ "$SKIP_TTS" = false ] && [ -f "$SPEECH_FILE" ]; then
    echo ""
    echo "להשמעה:"
    echo "  termux-media-player play $SPEECH_FILE"
    echo ""
    echo "או שתף את הקובץ:"
    echo "  termux-share $SPEECH_FILE"
fi
