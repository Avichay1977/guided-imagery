"""
Script -> narrated audio.

Three things here matter beyond calling a TTS API.

Concurrency: segments between pause markers are independent, so they synthesize
in parallel under a semaphore instead of one at a time. Everything that blocks —
the ElevenLabs SDK, ONNX nikud, ffmpeg decode/encode, numpy synthesis — runs in
a worker thread, because this is called from inside an async request and a
blocking call there stalls every other connected client, not just this one.

Assembly: segments are normalized to one PCM format up front, then joined as a
single buffer. `AudioSegment.__add__` in a loop copies the whole track on every
step, which is quadratic in the number of segments.

Cueing: the positions of the script's own pause markers are tracked during
assembly and handed to the ambience builder, so bells ring in the silences.
"""

import asyncio
import io
import json
import logging
import os
import re
import subprocess
import tempfile

# Configure ffmpeg + ffprobe paths before importing pydub
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass

import edge_tts
from pydub import AudioSegment

import storage
from audio_mix import build_ambience
from config import (
    BELL_CUE_OFFSET_MS,
    ELEVEN_API_KEY,
    ELEVEN_VOICE_ID,
    OUTPUT_BITRATE,
    OUTPUT_CHANNELS,
    OUTPUT_SAMPLE_RATE,
    OUTPUT_SAMPLE_WIDTH,
    PAUSE_DURATIONS,
    TTS_CONCURRENCY,
    TTS_ENGINE,
    TTS_MAX_ATTEMPTS,
    TTS_MODEL,
    TTS_OUTPUT_FORMAT,
    TTS_RETRY_BASE_DELAY,
    TTS_VOICE_SETTINGS,
    VOICE_PEAK_CEILING_DBFS,
    VOICE_TARGET_DBFS,
)
from nikud_service import add_nikud_to_segment

log = logging.getLogger(__name__)

PAUSE_PATTERN = re.compile(r'\[(pause|short_pause|long_pause|breath)\]')

# Only the structural pauses get a chime. Breaths and beats are too frequent —
# ringing on those turns a transition marker into a metronome.
BELL_CUE_MARKERS = frozenset({"[pause]", "[long_pause]"})

EDGE_VOICES = {
    "he": "he-IL-HilaNeural",
    "en": "en-US-AndrewMultilingualNeural",
}

# Prosody per language — tuned for calm, meditative delivery.
#   Hebrew: slower rate + lower pitch + softer volume for intimate feel
#   English: similar but slightly less aggressive
EDGE_PROSODY = {
    "he": {"rate": "-35%", "pitch": "-15Hz", "volume": "-10%"},
    "en": {"rate": "-30%", "pitch": "-10Hz", "volume": "-8%"},
}


class _EngineState:
    """
    Shared engine selection across parallel segment tasks.

    When one segment trips an ElevenLabs quota error the whole session drops to
    edge, so the remaining segments do not each pay their own failed call first.
    """

    def __init__(self, engine: str):
        self.engine = engine

    def downgrade(self, reason: str) -> None:
        if self.engine != "edge":
            log.warning("TTS falling back to edge for this session: %s", reason)
            self.engine = "edge"


def _improve_hebrew_prosody(text: str) -> str:
    """Add punctuation hints that guide the TTS to more natural phrasing."""
    text = re.sub(r'([^\.\!\?\,\…])(\s*\n)', r'\1.\2', text)
    text = re.sub(r'\.\.\.', '…', text)
    return text


def _get_elevenlabs_client():
    from elevenlabs.client import ElevenLabs
    return ElevenLabs(api_key=ELEVEN_API_KEY)


def split_script_on_pauses(script: str) -> list[dict]:
    """
    Split a script into alternating text and pause segments.

    Pause segments keep their marker so the caller can tell a structural pause
    from a breath when deciding where bells ring.
    """
    segments = []
    last_end = 0

    for match in PAUSE_PATTERN.finditer(script):
        text_before = script[last_end:match.start()].strip()
        if text_before:
            segments.append({"type": "text", "content": text_before})

        marker = match.group(0)
        segments.append({
            "type": "pause",
            "marker": marker,
            "duration_ms": PAUSE_DURATIONS.get(marker, 3000),
        })

        last_end = match.end()

    remaining = script[last_end:].strip()
    if remaining:
        segments.append({"type": "text", "content": remaining})

    return segments


def _detect_language(script: str) -> str:
    """Fallback only — callers should pass the language they already know."""
    # Range ֐-׿ covers Hebrew letters + nikud diacritics
    hebrew_chars = sum(1 for c in script[:300] if '֐' <= c <= '׿')
    return "he" if hebrew_chars > 10 else "en"


def _normalize(segment: AudioSegment) -> AudioSegment:
    """Force a segment into the canonical PCM format used for assembly."""
    if segment.frame_rate != OUTPUT_SAMPLE_RATE:
        segment = segment.set_frame_rate(OUTPUT_SAMPLE_RATE)
    if segment.channels != OUTPUT_CHANNELS:
        segment = segment.set_channels(OUTPUT_CHANNELS)
    if segment.sample_width != OUTPUT_SAMPLE_WIDTH:
        segment = segment.set_sample_width(OUTPUT_SAMPLE_WIDTH)
    return segment


def _concat(segments: list[AudioSegment]) -> AudioSegment:
    """
    Join pre-normalized segments in one pass.

    Repeated `+=` reallocates and copies the accumulated track each time, which
    is quadratic; joining the raw buffers is linear.
    """
    if not segments:
        return AudioSegment.silent(duration=0, frame_rate=OUTPUT_SAMPLE_RATE)
    return AudioSegment(
        b"".join(s.raw_data for s in segments),
        frame_rate=OUTPUT_SAMPLE_RATE,
        sample_width=OUTPUT_SAMPLE_WIDTH,
        channels=OUTPUT_CHANNELS,
    )


def _prepare_text(text: str, language: str) -> str:
    if language != "he":
        return text
    return _improve_hebrew_prosody(add_nikud_to_segment(text))


def _tts_edge_blocking(audio_path: str) -> AudioSegment:
    return _normalize(AudioSegment.from_mp3(audio_path))


async def _tts_edge(text: str, language: str) -> AudioSegment:
    text = await asyncio.to_thread(_prepare_text, text, language)

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
        # ffmpeg decode is a blocking subprocess — keep it off the event loop.
        return await asyncio.to_thread(_tts_edge_blocking, tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _tts_elevenlabs_blocking(text: str, language: str) -> AudioSegment:
    from elevenlabs import VoiceSettings

    text = _prepare_text(text, language) if language == "he" else text
    client = _get_elevenlabs_client()
    audio_bytes = client.text_to_speech.convert(
        text=text,
        voice_id=ELEVEN_VOICE_ID,
        model_id=TTS_MODEL,
        output_format=TTS_OUTPUT_FORMAT,
        voice_settings=VoiceSettings(**TTS_VOICE_SETTINGS),
    )
    audio_data = b"".join(chunk for chunk in audio_bytes if chunk)
    return _normalize(AudioSegment.from_mp3(io.BytesIO(audio_data)))


async def _tts_elevenlabs(text: str, language: str) -> AudioSegment:
    # The SDK is synchronous end to end, so the whole call goes to a thread.
    return await asyncio.to_thread(_tts_elevenlabs_blocking, text, language)


def _is_quota_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(token in message for token in ("quota", "401", "429", "unauthorized"))


async def _synthesize(text: str, language: str, state: _EngineState) -> AudioSegment:
    """Synthesize one segment, downgrading the whole session on a quota error."""
    if state.engine == "elevenlabs":
        try:
            return await _tts_elevenlabs(text, language)
        except Exception as exc:
            if not _is_quota_error(exc):
                raise
            state.downgrade(str(exc)[:200])
    return await _tts_edge(text, language)


async def _synthesize_with_retry(text: str, language: str, state: _EngineState) -> AudioSegment:
    """
    Retry a segment before letting it sink the whole render.

    A session is one Gemini call plus N TTS calls. Losing all of that to a
    single dropped connection is the most expensive failure available, and it is
    also the most likely one, so transient errors get a few backed-off attempts.
    Quota errors are excluded: those are handled by switching engines, and
    retrying them just burns time against a wall.
    """
    last_error: Exception | None = None
    for attempt in range(TTS_MAX_ATTEMPTS):
        try:
            return await _synthesize(text, language, state)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            last_error = exc
            if _is_quota_error(exc) or attempt == TTS_MAX_ATTEMPTS - 1:
                raise
            delay = TTS_RETRY_BASE_DELAY * (2 ** attempt)
            log.warning(
                "segment synthesis failed (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1,
                TTS_MAX_ATTEMPTS,
                delay,
                str(exc)[:200],
            )
            await asyncio.sleep(delay)
    raise last_error  # unreachable; the loop either returns or raises


def _normalize_loudness(voice: AudioSegment) -> AudioSegment:
    """
    Bring the narration to a consistent level, without ever clipping.

    Edge and ElevenLabs deliver noticeably different levels, and even one engine
    drifts between sessions. Since the ambience is mixed at a fixed dB relative
    to full scale, an unnormalized voice track changes the voice-to-bed balance
    from one session to the next.
    """
    if voice.dBFS == float("-inf"):  # pure silence has no level to correct
        return voice
    gain = VOICE_TARGET_DBFS - voice.dBFS
    headroom = VOICE_PEAK_CEILING_DBFS - voice.max_dBFS
    return voice.apply_gain(min(gain, headroom))


def _render_voice(parts: list[AudioSegment]) -> AudioSegment:
    """Join the narration and level it. No ambience yet."""
    combined = _concat(parts)
    if len(combined) == 0:
        raise ValueError("no audio was produced for this script")
    return _normalize_loudness(combined)


def _mix(
    voice: AudioSegment,
    cue_positions_ms: list[int],
    bells_volume: int,
    music_volume: int,
) -> AudioSegment:
    """Lay the ambience bed under a finished narration."""
    if bells_volume <= 0 and music_volume <= 0:
        return voice
    ambience = build_ambience(
        duration_ms=len(voice),
        cue_positions_ms=cue_positions_ms,
        bells_volume=bells_volume,
        music_volume=music_volume,
        frame_rate=OUTPUT_SAMPLE_RATE,
        channels=OUTPUT_CHANNELS,
    )
    return voice.overlay(ambience)


def _export(segment: AudioSegment, path) -> None:
    segment.export(str(path), format="mp3", bitrate=OUTPUT_BITRATE)


def _persist_voice(
    voice: AudioSegment, session_id: str, cue_positions_ms: list[int], language: str
) -> None:
    """
    Keep the narration and its cue points for later remixing.

    Cue positions are derived while walking the assembled timeline and cannot be
    recovered from the audio, so they travel in a sidecar next to the track.
    """
    _export(voice, storage.voice_path(session_id))
    storage.voice_meta_path(session_id).write_text(
        json.dumps(
            {
                "cues": cue_positions_ms,
                "duration_ms": len(voice),
                "language": language,
            }
        ),
        encoding="utf-8",
    )


def _decode(path) -> AudioSegment:
    """
    Decode one of our own artifacts, using ffmpeg and nothing else.

    pydub's from_file() runs ffprobe first to inspect the stream, which makes
    ffprobe a hard runtime requirement alongside ffmpeg. We wrote this file and
    already know what is in it, so the probe buys nothing — asking ffmpeg for
    raw PCM directly is one process instead of two and one dependency instead
    of two.
    """
    converter = AudioSegment.converter or "ffmpeg"
    result = subprocess.run(
        [
            converter, "-v", "quiet",
            "-i", str(path),
            "-f", "s16le",
            "-acodec", "pcm_s16le",
            "-ar", str(OUTPUT_SAMPLE_RATE),
            "-ac", str(OUTPUT_CHANNELS),
            "-",
        ],
        capture_output=True,
    )
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(f"could not decode {path}")
    return AudioSegment(
        result.stdout,
        frame_rate=OUTPUT_SAMPLE_RATE,
        sample_width=OUTPUT_SAMPLE_WIDTH,
        channels=OUTPUT_CHANNELS,
    )


def _load_voice(session_id: str) -> tuple[AudioSegment, list[int]]:
    """Load a stored narration and its cue points. Raises if either is gone."""
    voice_file = storage.voice_path(session_id)
    meta_file = storage.voice_meta_path(session_id)
    if not voice_file.is_file() or not meta_file.is_file():
        raise FileNotFoundError(f"no stored narration for session {session_id}")
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    return _decode(voice_file), list(meta.get("cues", []))


def _finalize(
    parts: list[AudioSegment],
    cue_positions_ms: list[int],
    bells_volume: int,
    music_volume: int,
    session_id: str,
    language: str,
) -> str:
    """
    Level the narration, store it, mix and encode. One blocking unit, one hop.
    """
    voice = _render_voice(parts)
    _persist_voice(voice, session_id, cue_positions_ms, language)
    mix_file = storage.mix_path(session_id, bells_volume, music_volume)
    _export(_mix(voice, cue_positions_ms, bells_volume, music_volume), mix_file)
    return mix_file.name


def _remix_blocking(session_id: str, bells_volume: int, music_volume: int) -> str:
    """Re-mix a stored narration at a new ambience setting."""
    mix_file = storage.mix_path(session_id, bells_volume, music_volume)
    if mix_file.is_file():
        # This exact combination was already rendered — nothing to do.
        storage.touch(mix_file)
        storage.touch(storage.voice_path(session_id))
        return mix_file.name

    voice, cues = _load_voice(session_id)
    _export(_mix(voice, cues, bells_volume, music_volume), mix_file)
    storage.touch(storage.voice_path(session_id))
    return mix_file.name


async def remix(session_id: str, bells_volume: int, music_volume: int) -> str:
    """
    Produce a new mix of an existing narration without re-synthesizing it.

    This is the whole point of keeping the voice track: changing the bells or
    the music bed costs one overlay and one encode — about a second — instead of
    a fresh script and a full TTS render.
    """
    return await asyncio.to_thread(_remix_blocking, session_id, bells_volume, music_volume)


async def generate_audio(
    script: str,
    on_progress=None,
    bells_volume: int = 50,
    music_volume: int = 35,
    language: str | None = None,
) -> dict:
    """
    Render a script to a mixed MP3.

    Returns {"session_id", "filename"}. The session id refers to the stored
    narration, which `remix()` can re-mix at any ambience setting without
    synthesizing anything again.

    Args:
        script: Text with [pause] / [breath] markers.
        on_progress: async (stage, percent) callback.
        bells_volume: 0-100, bells on pause markers.
        music_volume: 0-100, drone bed.
        language: 'he' or 'en'. Detected from the text only if omitted.
    """
    language = language or _detect_language(script)
    state = _EngineState(TTS_ENGINE)
    segments = split_script_on_pauses(script)

    text_indices = [i for i, s in enumerate(segments) if s["type"] == "text"]
    if not text_indices:
        raise ValueError("script contains no speakable text")

    total = len(text_indices)
    completed = 0
    semaphore = asyncio.Semaphore(TTS_CONCURRENCY)
    progress_lock = asyncio.Lock()

    if on_progress:
        await on_progress("tts_start", 0)

    async def synthesize_one(index: int) -> tuple[int, AudioSegment]:
        nonlocal completed
        async with semaphore:
            audio = await _synthesize_with_retry(segments[index]["content"], language, state)
        audio = audio.fade_in(50).fade_out(50)
        async with progress_lock:
            completed += 1
            if on_progress:
                await on_progress("tts_progress", int(completed / total * 100))
        return index, audio

    rendered = dict(
        await asyncio.gather(*(synthesize_one(i) for i in text_indices))
    )

    # Walk the script in order, tracking elapsed time so pause markers become
    # absolute cue positions for the bells.
    parts: list[AudioSegment] = []
    cue_positions: list[int] = []
    position_ms = 0
    for index, segment in enumerate(segments):
        if segment["type"] == "pause":
            duration = segment["duration_ms"]
            if segment.get("marker") in BELL_CUE_MARKERS:
                cue_positions.append(position_ms + BELL_CUE_OFFSET_MS)
            parts.append(
                AudioSegment.silent(duration=duration, frame_rate=OUTPUT_SAMPLE_RATE)
            )
            position_ms += duration
        else:
            audio = rendered[index]
            parts.append(audio)
            position_ms += len(audio)

    if on_progress:
        await on_progress("combining", 95)

    session_id = storage.new_session_id()
    filename = await asyncio.to_thread(
        _finalize, parts, cue_positions, bells_volume, music_volume, session_id, language
    )

    if on_progress:
        await on_progress("complete", 100)

    log.info(
        "rendered %s: %d segments, %d bells, %.1f min",
        filename,
        total,
        len(cue_positions),
        position_ms / 60000.0,
    )
    return {"session_id": session_id, "filename": filename}
