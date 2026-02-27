import os
from dotenv import load_dotenv

load_dotenv()

# Set ffmpeg + ffprobe paths for pydub
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

# API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")
ELEVEN_VOICE_ID = os.getenv("ELEVEN_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

# Gemini
GEMINI_MODEL = "gemini-2.5-flash"

# ElevenLabs
TTS_MODEL = "eleven_multilingual_v2"
TTS_OUTPUT_FORMAT = "mp3_44100_128"

# Voice settings optimized for calm meditation delivery
TTS_VOICE_SETTINGS = {
    "stability": 0.80,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True,
}

# Pause durations in milliseconds
PAUSE_DURATIONS = {
    "[pause]": 3000,
    "[short_pause]": 1500,
    "[long_pause]": 5000,
    "[breath]": 4000,
}

# Audio output directory
AUDIO_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "audio_output")
os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)
