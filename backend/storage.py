"""
Storage for generated audio artifacts.

The host filesystem is ephemeral — a deploy or restart wipes it — so generated
audio is treated as a cache rather than a record. Every file carries a TTL and a
janitor prunes the directory by age first, then by total size (oldest out).
Without this the directory grows without bound until the disk fills.

The read path goes through `resolve()`, which refuses anything that is not a
plain filename inside the audio directory.
"""

import asyncio
import logging
import os
import re
import time
import uuid
from pathlib import Path

from config import (
    AUDIO_JANITOR_INTERVAL_MINUTES,
    AUDIO_MAX_MB,
    AUDIO_OUTPUT_DIR,
    AUDIO_TTL_HOURS,
)

log = logging.getLogger(__name__)

AUDIO_ROOT = Path(AUDIO_OUTPUT_DIR).resolve()

# Filenames we mint ourselves: meditation_<hex>.mp3. Anything else is rejected
# rather than sanitized — there is no legitimate caller passing another shape.
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+\.(mp3|wav)$")


_SAFE_SESSION_ID = re.compile(r"^[a-f0-9]{12}$")


def new_filename(prefix: str = "meditation", suffix: str = ".mp3") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}{suffix}"


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def is_session_id(session_id: str) -> bool:
    return bool(session_id and _SAFE_SESSION_ID.match(session_id))


def path_for(filename: str) -> Path:
    """Absolute path for a newly minted filename (no existence check)."""
    return AUDIO_ROOT / filename


# The narration is kept separately from the finished mix so the ambience can be
# changed later without paying for the script and the TTS all over again. The
# sidecar holds the bell cue positions, which are derived during assembly and
# cannot be recovered from the audio alone.

def voice_path(session_id: str) -> Path:
    return AUDIO_ROOT / f"voice_{session_id}.mp3"


def voice_meta_path(session_id: str) -> Path:
    return AUDIO_ROOT / f"voice_{session_id}.json"


def mix_filename(session_id: str, bells_volume: int, music_volume: int) -> str:
    """
    Deterministic name for a mix of one narration at one ambience setting.

    Naming the file after its inputs makes remixing idempotent: asking for a
    combination that was already rendered costs a stat() instead of an encode.
    """
    return f"meditation_{session_id}b{int(bells_volume)}m{int(music_volume)}.mp3"


def mix_path(session_id: str, bells_volume: int, music_volume: int) -> Path:
    return AUDIO_ROOT / mix_filename(session_id, bells_volume, music_volume)


def has_voice(session_id: str) -> bool:
    return is_session_id(session_id) and voice_path(session_id).is_file()


def touch(path: Path) -> None:
    """
    Mark an artifact as recently used.

    The janitor prunes by mtime, so touching the narration on every remix keeps
    sessions that are still being played alive while idle ones age out.
    """
    try:
        os.utime(path, None)
    except OSError:
        pass


def resolve(filename: str) -> Path | None:
    """
    Resolve a client-supplied filename to a real file inside the audio root.

    Returns None if the name is malformed, escapes the root, or does not exist.
    """
    if not filename or not _SAFE_NAME.match(filename):
        return None
    candidate = (AUDIO_ROOT / filename).resolve()
    if not candidate.is_relative_to(AUDIO_ROOT):
        return None
    if not candidate.is_file():
        return None
    return candidate


def _entries() -> list[tuple[Path, float, int]]:
    """(path, mtime, size) for every artifact, oldest first."""
    out = []
    for path in AUDIO_ROOT.glob("*"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        out.append((path, stat.st_mtime, stat.st_size))
    out.sort(key=lambda e: e[1])
    return out


def _unlink(path: Path) -> int:
    try:
        size = path.stat().st_size
        path.unlink()
        return size
    except OSError:
        return 0


def is_voice_artifact(path: Path) -> bool:
    """A stored narration or its cue sidecar — the part that cannot be rebuilt."""
    return path.name.startswith("voice_")


def prune() -> dict:
    """
    Delete expired artifacts, then enforce the size budget.

    The budget pass is deliberately tiered. A mix can be rebuilt from its
    narration in a few seconds and costs nothing external; a narration can only
    be rebuilt by paying for the script and the whole TTS render again. So
    mixes are given up first, oldest to newest, and narrations are only touched
    if dropping every mix still is not enough.

    Safe to call concurrently with generation: a file being written is younger
    than the TTL, and the size pass only removes the oldest entries.
    """
    now = time.time()
    ttl_seconds = AUDIO_TTL_HOURS * 3600
    budget_bytes = AUDIO_MAX_MB * 1024 * 1024

    removed_age = 0
    freed = 0
    survivors: list[tuple[Path, float, int]] = []

    for path, mtime, size in _entries():
        if now - mtime > ttl_seconds:
            freed += _unlink(path)
            removed_age += 1
        else:
            survivors.append((path, mtime, size))

    total = sum(size for _, _, size in survivors)
    removed_size = 0

    # Cheapest to lose first: mixes, then narrations.
    for expendable in (True, False):
        if total <= budget_bytes:
            break
        for path, _, size in survivors:
            if total <= budget_bytes:
                break
            if is_voice_artifact(path) == expendable:
                continue
            freed += _unlink(path)
            total -= size
            removed_size += 1

    if removed_age or removed_size:
        log.info(
            "audio janitor: removed %d expired + %d over-budget files, freed %.1f MB",
            removed_age,
            removed_size,
            freed / 1024 / 1024,
        )
    return {"expired": removed_age, "over_budget": removed_size, "freed_bytes": freed}


async def janitor_loop() -> None:
    """Background pruning loop. Cancelled on shutdown."""
    interval = AUDIO_JANITOR_INTERVAL_MINUTES * 60
    while True:
        try:
            await asyncio.to_thread(prune)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("audio janitor pass failed")
        await asyncio.sleep(interval)
