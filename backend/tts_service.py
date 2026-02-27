import re
import uuid
import io
import os
import tempfile

# Configure ffmpeg + ffprobe paths before importing pydub
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

from pydub import AudioSegment
import edge_tts
from config import (
    ELEVEN_API_KEY, ELEVEN_VOICE_ID, TTS_MODEL, TTS_OUTPUT_FORMAT,
    TTS_VOICE_SETTINGS, PAUSE_DURATIONS, AUDIO_OUTPUT_DIR,
)
from nikud_service import add_nikud_to_segment
from bells_service import generate_bells_track

PAUSE_PATTERN = re.compile(r'\[(pause|short_pause|long_pause|breath)\]')

# Edge-TTS voice options
EDGE_VOICES = {
    "he": "he-IL-HilaNeural",
    "en": "en-US-AndrewMultilingualNeural",
}

# Prosody settings per language — tuned for calm, meditative delivery
# Based on forum recommendations for meditation TTS:
#   Hebrew: slower rate + lower pitch + softer volume for intimate feel
#   English: similar but slightly less aggressive
EDGE_PROSODY = {
    "he": {"rate": "-35%", "pitch": "-15Hz", "volume": "-10%"},
    "en": {"rate": "-30%", "pitch": "-10Hz", "volume": "-8%"},
}

# TTS engine: "edge" (free) or "elevenlabs" (premium)
TTS_ENGINE = os.getenv("TTS_ENGINE", "edge")

def _improve_hebrew_prosody(text: str) -> str:
    """Add punctuation hints that guide the TTS to more natural phrasing."""
    # Ensure sentences end with proper punctuation
    text = re.sub(r'([^\.\!\?\,\…])(\s*\n)', r'\1.\2', text)
    # Ellipsis for trailing phrases (meditative style)
    text = re.sub(r'\.\.\.', '…', text)
    return text


def _get_elevenlabs_client():
    from elevenlabs.client import ElevenLabs
    return ElevenLabs(api_key=ELEVEN_API_KEY)


def split_script_on_pauses(script: str) -> list[dict]:
    segments = []
    last_end = 0

    for match in PAUSE_PATTERN.finditer(script):
        text_before = script[last_end:match.start()].strip()
        if text_before:
            segments.append({"type": "text", "content": text_before})

        pause_key = match.group(0)
        duration = PAUSE_DURATIONS.get(pause_key, 3000)
        segments.append({"type": "pause", "duration_ms": duration})

        last_end = match.end()

    remaining = script[last_end:].strip()
    if remaining:
        segments.append({"type": "text", "content": remaining})

    return segments


def _detect_language(script: str) -> str:
    # Range \u0590-\u05FF covers Hebrew letters + nikud diacritics
    hebrew_chars = sum(1 for c in script[:300] if '\u0590' <= c <= '\u05FF')
    return "he" if hebrew_chars > 10 else "en"


async def _tts_edge(text: str, language: str) -> AudioSegment:
    # Pre-process Hebrew: add nikud for correct pronunciation, then prosody hints
    if language == "he":
        text = add_nikud_to_segment(text)
        text = _improve_hebrew_prosody(text)

    voice = EDGE_VOICES.get(language, EDGE_VOICES["en"])
    prosody = EDGE_PROSODY.get(language, EDGE_PROSODY["en"])

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=prosody["rate"],
        pitch=prosody["pitch"],
        volume=prosody.get("volume", "+0%"),
    )
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    try:
        await communicate.save(tmp.name)
        audio = AudioSegment.from_mp3(tmp.name)
        return audio
    finally:
        os.unlink(tmp.name)


def _tts_elevenlabs(text: str, language: str = "he") -> AudioSegment:
    if language == "he":
        text = add_nikud_to_segment(text)
    from elevenlabs import VoiceSettings
    client = _get_elevenlabs_client()
    voice_settings = VoiceSettings(**TTS_VOICE_SETTINGS)
    audio_bytes = client.text_to_speech.convert(
        text=text,
        voice_id=ELEVEN_VOICE_ID,
        model_id=TTS_MODEL,
        output_format=TTS_OUTPUT_FORMAT,
        voice_settings=voice_settings,
    )
    audio_data = b"".join(chunk for chunk in audio_bytes if chunk)
    return AudioSegment.from_mp3(io.BytesIO(audio_data))


async def generate_audio(script: str, on_progress=None, bells_volume: int = 50) -> str:
    engine = TTS_ENGINE
    language = _detect_language(script)
    segments = split_script_on_pauses(script)
    text_segments = [s for s in segments if s["type"] == "text"]
    total_text = len(text_segments)
    text_index = 0

    if on_progress:
        await on_progress("tts_start", 0)

    audio_parts = []
    for segment in segments:
        if segment["type"] == "pause":
            silence = AudioSegment.silent(duration=segment["duration_ms"])
            audio_parts.append(silence)
        else:
            try:
                if engine == "elevenlabs":
                    audio_segment = _tts_elevenlabs(segment["content"], language)
                else:
                    audio_segment = await _tts_edge(segment["content"], language)
            except Exception as e:
                error_msg = str(e).lower()
                if "quota" in error_msg or "401" in error_msg or "429" in error_msg:
                    engine = "edge"
                    audio_segment = await _tts_edge(segment["content"], language)
                else:
                    raise

            audio_segment = audio_segment.fade_in(50).fade_out(50)
            audio_parts.append(audio_segment)

            text_index += 1
            if on_progress:
                percent = int((text_index / total_text) * 100)
                await on_progress("tts_progress", percent)

    if on_progress:
        await on_progress("combining", 95)

    combined = AudioSegment.empty()
    for part in audio_parts:
        combined += part

    # Mix bells background if volume > 0
    if bells_volume > 0:
        bells = generate_bells_track(len(combined), volume_pct=bells_volume)
        combined = combined.overlay(bells)

    filename = f"meditation_{uuid.uuid4().hex[:8]}.mp3"
    filepath = f"{AUDIO_OUTPUT_DIR}/{filename}"
    combined.export(filepath, format="mp3", bitrate="192k")

    if on_progress:
        await on_progress("complete", 100)

    return filename
