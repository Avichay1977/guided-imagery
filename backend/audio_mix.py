"""
Ambience bed for meditation audio: pause-synced bells over an evolving drone.

Replaces the previous bells_service, which had two problems. Musically, it
scattered chimes on a blind 15-30s timer, so a bell could land in the middle of
a sentence. Computationally, it called `AudioSegment.overlay` once per bell, and
each overlay copies the entire track — for a 20-minute session that is dozens of
copies of a ~100 MB buffer.

Both are fixed by the same change: synthesize into one float32 numpy buffer with
in-place adds (O(total samples), one allocation), and place bells at cue points
the caller derives from the script's own pause markers.

The buffer is built at 16 kHz and resampled up on the way out. Nothing here
exceeds ~4.8 kHz — the highest bell partial — so the result is audibly identical
to synthesizing at 44.1 kHz for roughly a third of the memory.
"""

import logging
import math
from functools import lru_cache

import numpy as np
from pydub import AudioSegment

from config import (
    AMBIENCE_SAMPLE_RATE,
    BELL_MIN_SPACING_MS,
    OUTPUT_CHANNELS,
    OUTPUT_SAMPLE_RATE,
    PAD_LOOP_SECONDS,
)

log = logging.getLogger(__name__)

SR = AMBIENCE_SAMPLE_RATE

# Pentatonic — C5 D5 E5 G5 A5. No semitone clashes, so any two bells that
# overlap in the tail still consonate.
BELL_FREQS = (523.25, 587.33, 659.25, 783.99, 880.00)

# Drone root, two octaves below the bells so the two layers never compete.
PAD_ROOT_HZ = 130.81  # C3

# Edges of the volume ramp, in dB, for percent 0..100.
BELLS_DB_RANGE = (-40.0, -10.0)
MUSIC_DB_RANGE = (-48.0, -18.0)

AMBIENCE_FADE_MS = 3000


def _pct_to_gain(pct: int, db_range: tuple[float, float]) -> float:
    """Map a 0-100 slider onto a linear amplitude via a dB range."""
    lo, hi = db_range
    db = lo + (max(0, min(100, pct)) / 100.0) * (hi - lo)
    return float(10.0 ** (db / 20.0))


# ── Bells ─────────────────────────────────────────────────────────


@lru_cache(maxsize=64)
def _synth_bell(freq: float, duration_s: float) -> np.ndarray:
    """
    One bell strike: inharmonic partials with independent exponential decays.

    Cached because a session reuses the same handful of (freq, duration) pairs,
    and each strike is ~100k samples of transcendental math.
    """
    t = np.linspace(0, duration_s, int(SR * duration_s), endpoint=False, dtype=np.float32)

    # Detuned upper partials are what separate a bell from an organ pipe.
    partials = (
        (1.00, 1.00, duration_s * 0.90),
        (0.50, 2.01, duration_s * 0.60),
        (0.25, 3.03, duration_s * 0.40),
        (0.12, 4.17, duration_s * 0.25),
        (0.06, 5.43, duration_s * 0.15),
    )

    signal = np.zeros_like(t)
    for amp, ratio, decay_time in partials:
        harmonic = freq * ratio
        if harmonic >= SR / 2:  # never alias
            continue
        signal += amp * np.sin(2 * np.pi * harmonic * t, dtype=np.float32) * np.exp(
            -t * (3.0 / decay_time), dtype=np.float32
        )

    attack = int(0.005 * SR)
    if attack:
        signal[:attack] *= np.linspace(0, 1, attack, dtype=np.float32)

    peak = float(np.max(np.abs(signal)))
    if peak > 0:
        signal /= peak

    signal.flags.writeable = False
    return signal


def select_cues(candidates_ms, min_spacing_ms: int = BELL_MIN_SPACING_MS) -> list[int]:
    """
    Thin a list of candidate cue positions so bells never cluster.

    Script pause markers can sit a few seconds apart; ringing on each one turns
    the bed into a chime pile-up. Keeps the earliest of each cluster.
    """
    chosen: list[int] = []
    for position in sorted(candidates_ms):
        if position < 0:
            continue
        if not chosen or position - chosen[-1] >= min_spacing_ms:
            chosen.append(int(position))
    return chosen


def _bell_pitches(count: int, rng: np.random.Generator) -> list[float]:
    """
    Walk the scale by one step at a time rather than jumping at random.

    Consecutive bells a step apart read as a phrase; random leaps read as noise.
    """
    if count <= 0:
        return []
    index = int(rng.integers(0, len(BELL_FREQS)))
    pitches = []
    for _ in range(count):
        pitches.append(BELL_FREQS[index])
        index = int(np.clip(index + rng.choice([-1, 1]), 0, len(BELL_FREQS) - 1))
    return pitches


# ── Music bed ─────────────────────────────────────────────────────


def _snap_to_loop(freq: float, loop_s: float) -> float:
    """
    Nearest frequency completing a whole number of cycles in the loop window.

    This is what makes the bed tile seamlessly: every component ends its cycle
    exactly at the loop boundary, so the wrap point is continuous and no
    crossfade is needed. The shift is under 0.02 Hz at these frequencies.
    """
    cycles = max(1.0, round(freq * loop_s))
    return cycles / loop_s


@lru_cache(maxsize=4)
def _pad_loop(loop_s: float, root_hz: float) -> np.ndarray:
    """A seamlessly loopable drone: root, fifth, octave, twelfth, each breathing."""
    t = np.linspace(0, loop_s, int(SR * loop_s), endpoint=False, dtype=np.float32)
    signal = np.zeros_like(t)

    # (amplitude, frequency ratio, LFO cycles per loop, phase offset)
    voices = (
        (1.00, 1.0, 1, 0.0),
        (0.55, 1.5, 2, math.pi / 3),
        (0.40, 2.0, 3, math.pi / 2),
        (0.18, 3.0, 5, math.pi),
    )

    for amp, ratio, lfo_cycles, phase in voices:
        freq = _snap_to_loop(root_hz * ratio, loop_s)
        if freq >= SR / 2:
            continue
        lfo_hz = lfo_cycles / loop_s
        # Breathes between 30% and 100% so voices drift in and out of focus.
        envelope = 0.65 + 0.35 * np.sin(2 * np.pi * lfo_hz * t + phase, dtype=np.float32)
        signal += amp * np.sin(2 * np.pi * freq * t, dtype=np.float32) * envelope

    peak = float(np.max(np.abs(signal)))
    if peak > 0:
        signal /= peak

    signal.flags.writeable = False
    return signal


# ── Assembly ──────────────────────────────────────────────────────


def _to_segment(buffer: np.ndarray, frame_rate: int, channels: int) -> AudioSegment:
    """float32 [-1, 1] -> AudioSegment at the target rate and channel count."""
    np.clip(buffer, -1.0, 1.0, out=buffer)
    pcm = (buffer * 32767.0).astype(np.int16)
    segment = AudioSegment(pcm.tobytes(), frame_rate=SR, sample_width=2, channels=1)
    if segment.frame_rate != frame_rate:
        segment = segment.set_frame_rate(frame_rate)
    if segment.channels != channels:
        segment = segment.set_channels(channels)
    return segment


def build_ambience(
    duration_ms: int,
    cue_positions_ms=(),
    bells_volume: int = 50,
    music_volume: int = 35,
    frame_rate: int = OUTPUT_SAMPLE_RATE,
    channels: int = OUTPUT_CHANNELS,
    seed: int | None = None,
) -> AudioSegment:
    """
    Build the full ambience bed.

    Args:
        duration_ms: Length to fill, normally the assembled voice track.
        cue_positions_ms: Where bells ring — pause positions from the script.
        bells_volume: 0-100. 0 disables bells.
        music_volume: 0-100. 0 disables the drone.
        seed: Fixes bell pitch selection, for reproducible tests.
    """
    if duration_ms <= 0:
        return AudioSegment.silent(duration=0, frame_rate=frame_rate)

    total_samples = int(duration_ms / 1000.0 * SR)
    if total_samples <= 0:
        return AudioSegment.silent(duration=0, frame_rate=frame_rate)

    buffer = np.zeros(total_samples, dtype=np.float32)
    rng = np.random.default_rng(seed)

    # Bells, added in place at their cue points.
    cues = select_cues(cue_positions_ms) if bells_volume > 0 else []
    if cues:
        gain = _pct_to_gain(bells_volume, BELLS_DB_RANGE)
        pitches = _bell_pitches(len(cues), rng)
        for position_ms, freq in zip(cues, pitches):
            start = int(position_ms / 1000.0 * SR)
            if start >= total_samples:
                continue
            # Slight length variation keeps repeated strikes from sounding sampled.
            bell = _synth_bell(freq, round(float(rng.uniform(5.0, 7.0)), 1))
            end = min(total_samples, start + bell.shape[0])
            buffer[start:end] += bell[: end - start] * gain

    # Drone, tiled in place. Chunked so the only temporary is one loop long.
    if music_volume > 0:
        gain = _pct_to_gain(music_volume, MUSIC_DB_RANGE)
        loop = _pad_loop(PAD_LOOP_SECONDS, PAD_ROOT_HZ)
        loop_len = loop.shape[0]
        position = 0
        while position < total_samples:
            span = min(loop_len, total_samples - position)
            buffer[position : position + span] += loop[:span] * gain
            position += span

    # Ease the bed in and out so it never starts or stops abruptly.
    fade = min(int(AMBIENCE_FADE_MS / 1000.0 * SR), total_samples // 2)
    if fade > 0:
        ramp = np.linspace(0, 1, fade, dtype=np.float32)
        buffer[:fade] *= ramp
        buffer[-fade:] *= ramp[::-1]

    return _to_segment(buffer, frame_rate, channels)
