"""
Gentle meditation bells synthesizer.
Generates a background track of soft, resonant bell chimes
that can be mixed under the spoken meditation audio.
"""

import random
import numpy as np
from pydub import AudioSegment

SAMPLE_RATE = 44100

# Bell tunings — pentatonic scale frequencies for a peaceful feel
# C5, D5, E5, G5, A5 (no dissonance)
BELL_FREQS = [523.25, 587.33, 659.25, 783.99, 880.00]

# How quiet the bells are relative to voice (in dB)
BELLS_VOLUME_DB = -22


def _synth_bell(freq: float, duration_s: float = 6.0) -> np.ndarray:
    """
    Synthesize a single bell strike with harmonics and exponential decay.
    Models a Tibetan singing bowl / wind chime timbre.
    """
    t = np.linspace(0, duration_s, int(SAMPLE_RATE * duration_s), endpoint=False)

    # Fundamental + inharmonic partials (characteristic of bells)
    harmonics = [
        (1.0,   freq,         duration_s * 0.9),   # fundamental
        (0.5,   freq * 2.01,  duration_s * 0.6),   # 2nd partial (slightly detuned)
        (0.25,  freq * 3.03,  duration_s * 0.4),   # 3rd
        (0.12,  freq * 4.17,  duration_s * 0.25),  # 4th (more detuned = bell character)
        (0.06,  freq * 5.43,  duration_s * 0.15),  # 5th
    ]

    signal = np.zeros_like(t)
    for amp, h_freq, decay_time in harmonics:
        decay = np.exp(-t * (3.0 / decay_time))
        signal += amp * np.sin(2 * np.pi * h_freq * t) * decay

    # Soft attack (avoid click)
    attack_samples = int(0.005 * SAMPLE_RATE)
    signal[:attack_samples] *= np.linspace(0, 1, attack_samples)

    # Normalize
    peak = np.max(np.abs(signal))
    if peak > 0:
        signal = signal / peak * 0.8

    return signal


def _numpy_to_segment(samples: np.ndarray) -> AudioSegment:
    """Convert float64 numpy array to pydub AudioSegment."""
    pcm = (samples * 32767).astype(np.int16)
    return AudioSegment(
        pcm.tobytes(),
        frame_rate=SAMPLE_RATE,
        sample_width=2,
        channels=1,
    )


def generate_bells_track(duration_ms: int, volume_pct: int = 50) -> AudioSegment:
    """
    Generate a gentle bells background track of the given duration.

    Args:
        duration_ms: Track length in milliseconds.
        volume_pct: Bell volume 0-100 (0=silent, 50=default, 100=loud).
    """
    if volume_pct <= 0:
        return AudioSegment.silent(duration=duration_ms)

    duration_s = duration_ms / 1000.0
    track = AudioSegment.silent(duration=duration_ms)

    # Place bells every 15-30 seconds
    pos_s = random.uniform(5, 10)  # first bell after 5-10s
    while pos_s < duration_s - 7:
        freq = random.choice(BELL_FREQS)
        bell_duration = random.uniform(5.0, 7.0)
        bell_samples = _synth_bell(freq, bell_duration)
        bell_audio = _numpy_to_segment(bell_samples)

        # Random subtle volume variation per bell
        vol_variation = random.uniform(-3, 2)
        bell_audio = bell_audio + vol_variation

        pos_ms = int(pos_s * 1000)
        track = track.overlay(bell_audio, position=pos_ms)

        # Next bell in 15-30 seconds
        pos_s += random.uniform(15, 30)

    # Map 0-100 percentage to dB range: -40dB (quiet) to -10dB (loud)
    volume_db = -40 + (volume_pct / 100.0) * 30
    track = track + volume_db

    return track
