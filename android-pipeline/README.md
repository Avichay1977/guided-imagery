# Android Audio Transcription Pipeline

צינור עבודה ל-Termux באנדרואיד:
**וידאו/אודיו → תמלול → תרגום לעברית → הקראה בעברית**

## מבנה

```
audio-pipeline/
├── setup.sh              # התקנה ראשונית (פעם אחת)
├── test-whisper.sh       # בדיקת תמלול
├── pipeline.sh           # הצינור המלא
├── translate.py          # תרגום דרך Gemini
├── tts_hebrew.py         # הקראה עברית (Edge TTS)
├── download-youtube.sh   # הורדת אודיו מיוטיוב
└── install-scripts.sh    # העתקה לתיקיית עבודה
```

## התחלה מהירה

### שלב 1 — התקנה
```bash
bash setup.sh
```

### שלב 2 — בדיקה
```bash
bash test-whisper.sh
```

### שלב 3 — הגדרת מפתח API לתרגום
```bash
echo 'GOOGLE_API_KEY=your-key-here' >> ~/.env
```

### שלב 4 — הרצה
```bash
# על קובץ מקומי
bash pipeline.sh video.mp4

# מיוטיוב
bash download-youtube.sh "https://youtu.be/VIDEO_ID"
bash pipeline.sh ~/audio-pipeline/input/video_title.mp3

# אפשרויות
bash pipeline.sh file.mp4 --model small    # מודל גדול יותר (מדויק)
bash pipeline.sh file.mp4 --skip-tts       # ללא הקראה
bash pipeline.sh file.mp4 --lang en        # כפה שפה
```

## סטאק טכני

| רכיב | כלי | הערות |
|-------|------|-------|
| חילוץ אודיו | ffmpeg | 16kHz mono WAV |
| תמלול | whisper.cpp | מודלים: tiny/base/small/medium |
| תרגום | Gemini 2.5 Flash | דורש GOOGLE_API_KEY |
| הקראה | Edge TTS | חינמי, he-IL-HilaNeural |

## דרישות מכשיר

- **מודל tiny**: כל מכשיר, ~75MB RAM
- **מודל small**: 2GB+ RAM, תמלול מדויק יותר
- **מודל medium**: 4GB+ RAM, הכי מדויק (איטי)
