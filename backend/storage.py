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


def new_filename(prefix: str = "meditation", suffix: str = ".mp3") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}{suffix}"


def path_for(filename: str) -> Path:
    """Absolute path for a newly minted filename (no existence check)."""
    return AUDIO_ROOT / filename


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


def prune() -> dict:
    """
    Delete expired artifacts, then enforce the size budget oldest-first.

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
    for path, _, size in survivors:
        if total <= budget_bytes:
            break
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
