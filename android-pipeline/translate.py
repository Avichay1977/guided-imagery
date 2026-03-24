#!/usr/bin/env python3
"""
תרגום טקסט לעברית באמצעות Google Gemini API.
שימוש: python3 translate.py input.txt output.txt

דורש: GOOGLE_API_KEY בסביבה או בקובץ .env
"""
import sys
import os

def translate_to_hebrew(text: str, api_key: str) -> str:
    """Translate text to Hebrew using Gemini."""
    from google import genai

    client = genai.Client(api_key=api_key)

    prompt = f"""Translate the following text to Hebrew.

RULES:
- Use modern spoken Hebrew, natural and clear
- No nikud (diacritics)
- Preserve paragraph breaks
- Do not add explanations — output ONLY the translation
- If the text is already in Hebrew, return it as-is

TEXT:
{text}"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return response.text.strip()


def main():
    if len(sys.argv) < 3:
        print("שימוש: python3 translate.py <קובץ_קלט> <קובץ_פלט>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    # Load API key
    api_key = os.environ.get("GOOGLE_API_KEY")

    # Try .env file
    if not api_key:
        env_file = os.path.expanduser("~/.env")
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GOOGLE_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break

    if not api_key:
        print("שגיאה: חסר GOOGLE_API_KEY")
        print("הגדר: export GOOGLE_API_KEY='your-key-here'")
        print("או צור קובץ ~/.env עם: GOOGLE_API_KEY=your-key-here")
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        print("שגיאה: קובץ הקלט ריק")
        sys.exit(1)

    print(f"  מתרגם {len(text.split())} מילים...")
    translated = translate_to_hebrew(text, api_key)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(translated)

    print(f"  ✓ התרגום נשמר ל-{output_file}")


if __name__ == "__main__":
    main()
