"""
Nikud (Hebrew diacritics) service using Phonikud-ONNX.
Ensures all Hebrew text has proper vowel marks for accurate TTS pronunciation.
"""

import re
import os
from functools import lru_cache
from huggingface_hub import hf_hub_download
from phonikud_onnx import Phonikud

# Phonikud adds phonetic markers we need to clean for TTS
# | = morpheme boundary, ֫ = stress mark, ֽ = meteg
_PHONETIC_CLEANUP = re.compile(r'[|ֽ֫֬]')

# Pause markers that should be preserved as-is
_PAUSE_PATTERN = re.compile(r'\[(pause|short_pause|long_pause|breath)\]')


@lru_cache(maxsize=1)
def _get_model() -> Phonikud:
    """Lazy-load model once, cache forever."""
    model_path = hf_hub_download(
        repo_id="thewh1teagle/phonikud-onnx",
        filename="phonikud-1.0.int8.onnx",
    )
    return Phonikud(model_path)


def _has_nikud(text: str) -> bool:
    """Check if text already has nikud (Hebrew vowel diacritics U+05B0-U+05BD)."""
    nikud_chars = sum(1 for c in text if '\u05B0' <= c <= '\u05BD')
    hebrew_chars = sum(1 for c in text if '\u05D0' <= c <= '\u05EA')
    if hebrew_chars == 0:
        return True  # no Hebrew = nothing to nikud
    return (nikud_chars / hebrew_chars) > 0.3


def add_nikud(script: str) -> str:
    """
    Add nikud to a meditation script while preserving pause markers.

    Strategy:
    1. Extract and protect pause markers
    2. Split into segments around pauses
    3. Apply Phonikud to each Hebrew segment
    4. Clean phonetic-only markers (|, ֫)
    5. Reassemble
    """
    if not script or not script.strip():
        return script

    # If script already has good nikud coverage, skip
    if _has_nikud(script):
        return script

    model = _get_model()

    # Split on pause markers, keeping them
    parts = _PAUSE_PATTERN.split(script)
    markers = _PAUSE_PATTERN.findall(script)

    result_parts = []
    marker_idx = 0

    for i, part in enumerate(parts):
        if i % 2 == 0:
            # Text segment - apply nikud
            if part.strip():
                vocalized = model.add_diacritics(part.strip())
                # Clean phonetic markers that TTS doesn't need
                vocalized = _PHONETIC_CLEANUP.sub('', vocalized)
                result_parts.append(vocalized)
            else:
                result_parts.append(part)
        else:
            # This is the pause type captured by the group
            result_parts.append(f'[{part}]')

    return ' '.join(p for p in result_parts if p.strip())


def add_nikud_to_segment(text: str) -> str:
    """Add nikud to a single text segment (no pause markers expected)."""
    if not text or not text.strip() or _has_nikud(text):
        return text

    model = _get_model()
    vocalized = model.add_diacritics(text.strip())
    return _PHONETIC_CLEANUP.sub('', vocalized)
