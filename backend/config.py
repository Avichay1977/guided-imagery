import logging
import os

from dotenv import load_dotenv

load_dotenv()

# Set ffmpeg + ffprobe paths for pydub
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass


def _env_int(name: str, default: int, lo: int | None = None, hi: int | None = None) -> int:
    """Read an int from the environment, clamped and never raising on junk."""
    try:
        value = int(os.getenv(name, default))
    except (TypeError, ValueError):
        value = default
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# ── Logging ───────────────────────────────────────────────────────

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

# When true, API errors return the raw exception text. Never enable in production —
# exception strings from the model/TTS SDKs can carry endpoint and path details.
DEBUG_ERRORS = _env_flag("DEBUG_ERRORS", False)

# ── API Keys ──────────────────────────────────────────────────────

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")
ELEVEN_VOICE_ID = os.getenv("ELEVEN_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

# ── Gemini ────────────────────────────────────────────────────────

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ── TTS ───────────────────────────────────────────────────────────

# "edge" (free) or "elevenlabs" (premium). Falls back to edge on quota errors.
TTS_ENGINE = os.getenv("TTS_ENGINE", "edge")
TTS_MODEL = "eleven_multilingual_v2"
TTS_OUTPUT_FORMAT = "mp3_44100_128"

# Segments between pause markers are independent, so they synthesize in parallel.
# Kept modest: the ceiling is the TTS provider's tolerance, not our CPU.
TTS_CONCURRENCY = _env_int("TTS_CONCURRENCY", 4, lo=1, hi=16)

# A whole render is expensive — one Gemini call plus N TTS calls. Throwing all
# of it away because a single segment hit a transient network blip is the most
# wasteful failure mode there is, so segments retry before giving up.
TTS_MAX_ATTEMPTS = _env_int("TTS_MAX_ATTEMPTS", 3, lo=1, hi=6)
TTS_RETRY_BASE_DELAY = float(_env_int("TTS_RETRY_BASE_DELAY_MS", 500, lo=0)) / 1000.0

# Narration is normalized to this level before mixing. Without it, perceived
# loudness drifts between engines and between sessions, and the ambience bed
# sits at a different relative level every time.
VOICE_TARGET_DBFS = -20.0
# Headroom kept below full scale so normalization can never clip.
VOICE_PEAK_CEILING_DBFS = -1.0

# Voice settings optimized for calm meditation delivery
TTS_VOICE_SETTINGS = {
    "stability": 0.80,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True,
}

# Canonical PCM format for the assembled track. Normalizing every segment to this
# up front is what lets the concatenation be a single buffer join.
OUTPUT_SAMPLE_RATE = 44100
OUTPUT_CHANNELS = 1
OUTPUT_SAMPLE_WIDTH = 2
OUTPUT_BITRATE = "128k"

# Pause durations in milliseconds
PAUSE_DURATIONS = {
    "[pause]": 3000,
    "[short_pause]": 1500,
    "[long_pause]": 5000,
    "[breath]": 4000,
}

# ── Ambience (bells + music bed) ──────────────────────────────────

# Ambience is all low-frequency content — the highest bell partial lands near
# 4.8 kHz — so it is synthesized at 16 kHz and resampled up on mix. That is a
# ~2.75x cut in peak memory versus synthesizing at 44.1 kHz, with nothing
# audible lost under a voice track.
AMBIENCE_SAMPLE_RATE = 16000

# Seamless-loop length for the music bed. Partial and LFO frequencies are
# snapped to whole cycles of this window so the loop joins without a crossfade.
PAD_LOOP_SECONDS = 30.0

# Bells ring on script pause markers, never mid-sentence. This is the floor on
# spacing so consecutive markers don't cluster into a chime pile-up.
BELL_MIN_SPACING_MS = 20_000
# Delay after a pause begins, so the chime lands in the silence, not on the
# tail of the last word.
BELL_CUE_OFFSET_MS = 250

# ── Audio artifact storage ────────────────────────────────────────

AUDIO_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "audio_output")
os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)

# Generated audio is a cache, not a record: the host filesystem is ephemeral and
# is wiped on every deploy. The janitor prunes by age first, then by total size.
AUDIO_TTL_HOURS = _env_int("AUDIO_TTL_HOURS", 6, lo=1)
AUDIO_MAX_MB = _env_int("AUDIO_MAX_MB", 512, lo=16)
AUDIO_JANITOR_INTERVAL_MINUTES = _env_int("AUDIO_JANITOR_INTERVAL_MINUTES", 30, lo=1)

# ── Rate limiting ─────────────────────────────────────────────────

# Per-client sliding windows.
#
# This is a personal tool running on localhost, so these are not sized to hold
# off an attacker — they are a runaway guard. A loop that starts firing requests
# would otherwise spend real money against the Gemini and TTS accounts before
# anyone noticed. The numbers are set high enough that ordinary use never
# reaches them: an evening of trying out a dozen different phrasings is fine.
#
# Tighten them if this is ever exposed on a public URL, where the first line of
# defence has to be the limit rather than the fact that only you can reach it.
RATE_LIMIT_SESSION = os.getenv("RATE_LIMIT_SESSION", "60/hour")
RATE_LIMIT_TRANSLATE = os.getenv("RATE_LIMIT_TRANSLATE", "120/hour")
RATE_LIMIT_YOUTUBE = os.getenv("RATE_LIMIT_YOUTUBE", "60/hour")
# Remixing costs one overlay and one encode, no model or TTS calls at all.
RATE_LIMIT_REMIX = os.getenv("RATE_LIMIT_REMIX", "240/hour")

# Backstop against the per-client limit being sidestepped by spoofed forwarding
# headers: a hard ceiling on generations running at once, process-wide.
MAX_CONCURRENT_GENERATIONS = _env_int("MAX_CONCURRENT_GENERATIONS", 2, lo=1, hi=32)

# Number of reverse proxies in front of the app. The client IP is read this many
# hops from the right of X-Forwarded-For; entries further left are attacker
# controlled. Render terminates at one proxy.
TRUSTED_PROXY_HOPS = _env_int("TRUSTED_PROXY_HOPS", 1, lo=0)

# ── CORS ──────────────────────────────────────────────────────────

# Local development only. The app is not deployed to a public URL; if that ever
# changes, add the origin through ALLOWED_ORIGINS rather than hardcoding it.
_DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8888",
]
_extra_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if os.getenv("RENDER_EXTERNAL_URL"):
    _extra_origins.append(os.getenv("RENDER_EXTERNAL_URL"))
ALLOWED_ORIGINS = list(dict.fromkeys(_DEFAULT_ORIGINS + _extra_origins))

# ── Request limits ────────────────────────────────────────────────

MAX_CAPTION_SEGMENTS = _env_int("MAX_CAPTION_SEGMENTS", 1500, lo=1)
MAX_CAPTION_CHARS = _env_int("MAX_CAPTION_CHARS", 100_000, lo=1000)
CAPTION_BATCH_SIZE = _env_int("CAPTION_BATCH_SIZE", 20, lo=1, hi=100)
