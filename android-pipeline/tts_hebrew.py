#!/usr/bin/env python3
"""
הקראה בעברית באמצעות Edge TTS (חינמי, ללא מפתח API).
שימוש: python3 tts_hebrew.py input.txt output.mp3

קול: he-IL-HilaNeural (נשי, ברור, טבעי)
"""
import sys
import asyncio
import edge_tts


VOICE = "he-IL-HilaNeural"
# Prosody: מעט איטי יותר לבהירות
RATE = "-20%"
PITCH = "-10Hz"


async def text_to_speech(text: str, output_file: str):
    """Generate Hebrew speech from text using Edge TTS."""
    communicate = edge_tts.Communicate(
        text=text,
        voice=VOICE,
        rate=RATE,
        pitch=PITCH,
    )
    await communicate.save(output_file)


def main():
    if len(sys.argv) < 3:
        print("שימוש: python3 tts_hebrew.py <קובץ_טקסט> <קובץ_פלט.mp3>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    with open(input_file, "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        print("שגיאה: קובץ הטקסט ריק")
        sys.exit(1)

    print(f"  מקריא {len(text.split())} מילים בעברית...")
    asyncio.run(text_to_speech(text, output_file))
    print(f"  ✓ הקובץ נשמר ל-{output_file}")


if __name__ == "__main__":
    main()
