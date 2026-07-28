import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from google import genai
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from youtube_transcript_api import YouTubeTranscriptApi

import rate_limit
import storage
import tts_service
from config import (
    ALLOWED_ORIGINS,
    CAPTION_BATCH_SIZE,
    DEBUG_ERRORS,
    DEFAULT_PACE,
    ELEVEN_API_KEY,
    GEMINI_MODEL,
    GOOGLE_API_KEY,
    MAX_CAPTION_CHARS,
    MAX_CAPTION_SEGMENTS,
    MAX_CONCURRENT_GENERATIONS,
    RATE_LIMIT_REMIX,
    RATE_LIMIT_SESSION,
    RATE_LIMIT_TRANSLATE,
    RATE_LIMIT_YOUTUBE,
    TTS_ENGINE,
)
from focus_areas import DEFAULT_FOCUS, FOCUS_AREAS
from prompt_template import build_meditation_prompt
from tts_service import generate_audio

# Built from the catalogue so adding a focus area cannot drift out of sync with
# what the API will accept.
FOCUS_PATTERN = "^(" + "|".join(sorted(FOCUS_AREAS)) + ")$"

log = logging.getLogger("guided_imagery")

# Hard ceiling on simultaneous renders. The per-client limiter is the first line
# of defence; this one holds even when client identity is spoofed, because it
# counts work in flight rather than callers.
#
# Created on startup rather than at import: an asyncio primitive binds to the
# first event loop that touches it and then refuses every other one, so building
# it at import time ties the app to whichever loop happened to arrive first.
_generation_slots: asyncio.Semaphore | None = None


def _slots() -> asyncio.Semaphore:
    global _generation_slots
    if _generation_slots is None:
        _generation_slots = asyncio.Semaphore(MAX_CONCURRENT_GENERATIONS)
    return _generation_slots


def _check_configuration() -> None:
    """
    Surface misconfiguration at boot rather than on a user's first request.

    Without this, a missing key produces an SDK error halfway through a
    generation, which reads like a bug in the app rather than a blank field in
    the environment.
    """
    if not GOOGLE_API_KEY:
        log.error(
            "GOOGLE_API_KEY is not set — script generation and translation will "
            "fail. See backend/.env.example."
        )
    if TTS_ENGINE == "elevenlabs" and not ELEVEN_API_KEY:
        log.warning(
            "TTS_ENGINE=elevenlabs but ELEVEN_API_KEY is not set — every session "
            "will fall back to edge on its first segment."
        )
    for name, spec in (
        ("RATE_LIMIT_SESSION", RATE_LIMIT_SESSION),
        ("RATE_LIMIT_TRANSLATE", RATE_LIMIT_TRANSLATE),
        ("RATE_LIMIT_YOUTUBE", RATE_LIMIT_YOUTUBE),
        ("RATE_LIMIT_REMIX", RATE_LIMIT_REMIX),
    ):
        try:
            rate_limit.parse_spec(spec)
        except ValueError:
            log.error("%s is malformed (%r); expected a form like '5/hour'.", name, spec)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _generation_slots
    _check_configuration()
    # Bind the capacity gate to the loop this app is actually running on.
    _generation_slots = asyncio.Semaphore(MAX_CONCURRENT_GENERATIONS)
    storage.prune()  # clear anything a previous process left behind
    janitor = asyncio.create_task(storage.janitor_loop())
    sweeper = asyncio.create_task(_rate_limit_sweeper())
    try:
        yield
    finally:
        for task in (janitor, sweeper):
            task.cancel()
        await asyncio.gather(janitor, sweeper, return_exceptions=True)


async def _rate_limit_sweeper() -> None:
    """Drop cold rate-limit keys so the tables don't grow without bound."""
    while True:
        await asyncio.sleep(600)
        try:
            rate_limit.sweep_all()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("rate limit sweep failed")


app = FastAPI(title="Guided Imagery", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    # No cookies or Authorization headers are used, so credentialed CORS would
    # widen exposure for nothing.
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

FRONTEND_DIR = (Path(__file__).parent.parent / "frontend" / "dist").resolve()

gemini_client = None


def get_gemini_client():
    global gemini_client
    if gemini_client is None:
        gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
    return gemini_client


def _safe_error(exc: Exception, fallback: str) -> str:
    """
    Client-facing error text.

    Exception strings from the model and TTS SDKs can carry endpoints, payload
    fragments and local paths, so the detail stays in the log unless
    DEBUG_ERRORS is explicitly enabled.
    """
    log.exception(fallback)
    return str(exc) if DEBUG_ERRORS else fallback


class SessionRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=200)
    duration_minutes: int = Field(..., ge=3, le=30)
    language: str = Field(default="he", pattern="^(he|en)$")
    mode: str = Field(default="imagery", pattern="^(imagery|hypnosis)$")
    depth: str = Field(default="standard", pattern="^(light|standard|medium|deep)$")
    # The three coarse values the API originally took still resolve; the finer
    # bands exist because a 4-year-old and a 12-year-old need different scripts.
    age_group: str = Field(
        default="adult",
        pattern="^(young_child|child|teen|adult|senior|children|teens|adults)$",
    )
    focus: str = Field(default=DEFAULT_FOCUS, pattern=FOCUS_PATTERN)
    neuroprofile: str = Field(default="none", pattern="^(none|autism|adhd|audhd)$")
    pace: str = Field(default=DEFAULT_PACE, pattern="^(very_slow|slow|natural|brisk)$")
    bells_volume: int = Field(default=50, ge=0, le=100)
    music_volume: int = Field(default=35, ge=0, le=100)


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50000)
    source_language: str = Field(..., pattern="^(he|en)$")
    target_language: str = Field(..., pattern="^(he|en)$")


@app.post("/api/session", dependencies=[Depends(rate_limit.rate_limit(RATE_LIMIT_SESSION))])
async def create_session(request: Request, session: SessionRequest):
    # Acquired here rather than inside the generator so an overloaded server
    # answers with a real 429 instead of opening a stream that fails later.
    slots = _slots()
    try:
        await asyncio.wait_for(slots.acquire(), timeout=0.05)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=429,
            detail="The server is at capacity. Please try again shortly.",
            headers={"Retry-After": "60"},
        )

    is_hebrew = session.language == "he"

    async def event_generator():
        try:
            yield {
                "event": "progress",
                "data": json.dumps({
                    "stage": "generating_script",
                    "message": (
                        "יוצר תסריט היפנוזה..." if session.mode == "hypnosis" else "יוצר תסריט מדיטציה..."
                    ) if is_hebrew else (
                        "Generating hypnosis script..." if session.mode == "hypnosis" else "Generating meditation script..."
                    ),
                    "percent": 10,
                }, ensure_ascii=False),
            }

            prompt = build_meditation_prompt(
                topic=session.topic,
                duration_minutes=session.duration_minutes,
                language=session.language,
                mode=session.mode,
                depth=session.depth,
                age_group=session.age_group,
                focus=session.focus,
                neuroprofile=session.neuroprofile,
                pace=session.pace,
            )

            response = await get_gemini_client().aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            script = (response.text or "").strip()

            if not script:
                yield {
                    "event": "error",
                    "data": json.dumps({"message": "Failed to generate script"}),
                }
                return

            yield {
                "event": "progress",
                "data": json.dumps({
                    "stage": "script_ready",
                    "message": "התסריט מוכן, מתחיל הקלטה..." if is_hebrew else "Script ready, recording audio...",
                    "percent": 25,
                }, ensure_ascii=False),
            }

            progress_queue = asyncio.Queue()

            async def on_tts_progress(stage, percent):
                overall = 25 + int(percent * 0.70)
                msg = f"מקליט אודיו... {percent}%" if is_hebrew else f"Recording audio... {percent}%"
                await progress_queue.put({
                    "event": "progress",
                    "data": json.dumps({
                        "stage": stage,
                        "message": msg,
                        "percent": overall,
                    }, ensure_ascii=False),
                })

            tts_task = asyncio.create_task(
                generate_audio(
                    script,
                    on_tts_progress,
                    bells_volume=session.bells_volume,
                    music_volume=session.music_volume,
                    language=session.language,
                    pace=session.pace,
                )
            )

            try:
                while not tts_task.done():
                    try:
                        event = await asyncio.wait_for(progress_queue.get(), timeout=0.5)
                        yield event
                    except asyncio.TimeoutError:
                        pass

                    if await request.is_disconnected():
                        tts_task.cancel()
                        return

                while not progress_queue.empty():
                    yield await progress_queue.get()

                result = tts_task.result()
            finally:
                if not tts_task.done():
                    tts_task.cancel()

            yield {
                "event": "complete",
                "data": json.dumps({
                    "script": script,
                    "audio_url": f"/audio/{result['filename']}",
                    "session_id": result["session_id"],
                    "duration_minutes": session.duration_minutes,
                }, ensure_ascii=False),
            }

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            message = _safe_error(exc, "Failed to generate the session. Please try again.")
            yield {"event": "error", "data": json.dumps({"message": message}, ensure_ascii=False)}
        finally:
            slots.release()

    return EventSourceResponse(event_generator())


class RemixRequest(BaseModel):
    session_id: str = Field(..., min_length=12, max_length=12, pattern="^[a-f0-9]{12}$")
    bells_volume: int = Field(default=50, ge=0, le=100)
    music_volume: int = Field(default=35, ge=0, le=100)


@app.post("/api/remix", dependencies=[Depends(rate_limit.rate_limit(RATE_LIMIT_REMIX))])
async def remix_session(req: RemixRequest):
    """
    Re-mix an existing narration at a new ambience setting.

    Changing the bells or the music used to mean generating a whole new session:
    a fresh Gemini script and a full TTS render, minutes of work and real API
    spend, for a change that only touches the last overlay. The narration is
    kept, so this is one overlay and one encode. Repeat requests for a
    combination already rendered do not even cost that.
    """
    if not storage.has_voice(req.session_id):
        raise HTTPException(
            status_code=404,
            detail="That session is no longer available. Generate a new one.",
        )
    try:
        filename = await tts_service.remix(
            req.session_id, req.bells_volume, req.music_volume
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="That session is no longer available. Generate a new one.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=_safe_error(exc, "Could not remix that session.")
        )
    return {"audio_url": f"/audio/{filename}", "session_id": req.session_id}


@app.post("/api/translate", dependencies=[Depends(rate_limit.rate_limit(RATE_LIMIT_TRANSLATE))])
async def translate_script(req: TranslateRequest):
    """Translate a meditation script between Hebrew and English using Gemini."""
    if req.source_language == req.target_language:
        return {"translated_text": req.text}

    lang_names = {"he": "Hebrew", "en": "English"}
    source = lang_names[req.source_language]
    target = lang_names[req.target_language]

    prompt = f"""You are a professional translator specializing in meditation and guided imagery scripts.

Translate the following {source} meditation script into {target}.

RULES:
- Preserve ALL pause markers exactly as they are: [pause], [short_pause], [long_pause], [breath]
- Keep the same calm, flowing, therapeutic tone
- Use natural {target} suitable for spoken meditation guidance
- Do not add or remove content — translate faithfully
- Output ONLY the translated text, nothing else
{"- Use warm modern spoken Hebrew (no biblical/formal). No nikud (diacritics)." if req.target_language == "he" else "- Use warm, flowing English suitable for deep relaxation."}

TEXT TO TRANSLATE:
{req.text}"""

    try:
        response = await get_gemini_client().aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=_safe_error(exc, "Translation service is unavailable."),
        )
    return {"translated_text": (response.text or "").strip()}


# ── YouTube Translation ─────────────────────────────────────────

class YouTubeCaptionsRequest(BaseModel):
    video_url: str = Field(..., min_length=5, max_length=500)
    target_language: str = Field(default="he", pattern="^(he|en|ar|ru|fr|es|de)$")


class CaptionSegment(BaseModel):
    start: float = Field(..., ge=0)
    duration: float = Field(default=0, ge=0)
    text: str = Field(default="", max_length=2000)


class TranslateCaptionsRequest(BaseModel):
    """
    Bounded on purpose.

    This endpoint fans out to Gemini once per batch, so an unbounded segment
    list is an unbounded bill. The previous version read the raw JSON body with
    no model and no ceiling.
    """

    segments: list[CaptionSegment] = Field(..., min_length=1, max_length=MAX_CAPTION_SEGMENTS)
    target_language: str = Field(default="he", pattern="^(he|en|ar|ru|fr|es|de)$")


def _extract_video_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:v=|\/v\/|youtu\.be\/|embed\/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("Invalid YouTube URL")


@app.post("/api/youtube/captions", dependencies=[Depends(rate_limit.rate_limit(RATE_LIMIT_YOUTUBE))])
async def get_youtube_captions(req: YouTubeCaptionsRequest):
    """Fetch YouTube captions in the best available language."""
    try:
        video_id = _extract_video_id(req.video_url)
    except ValueError:
        return {"error": "קישור יוטיוב לא תקין"}

    def _fetch():
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)
        # Preference order: requested language, then English, then anything.
        for languages, label in (
            ([req.target_language], req.target_language),
            (["en"], "en"),
            (None, "unknown"),
        ):
            try:
                if languages is None:
                    return ytt_api.fetch(transcript_list), label
                return ytt_api.fetch(transcript_list, languages=languages), label
            except Exception:
                continue
        return None, None

    try:
        captions, source_lang = await asyncio.to_thread(_fetch)
    except Exception as exc:
        log.warning("youtube caption fetch failed for %s: %s", video_id, exc)
        return {"error": "לא ניתן לגשת לכתוביות של הסרטון"}

    if captions is None:
        return {"error": "No captions available for this video"}

    return {
        "video_id": video_id,
        "source_language": source_lang,
        "segments": [
            {"start": s.start, "duration": s.duration, "text": s.text} for s in captions
        ],
    }


@app.post(
    "/api/youtube/translate-captions",
    dependencies=[Depends(rate_limit.rate_limit(RATE_LIMIT_YOUTUBE))],
)
async def translate_youtube_captions(req: TranslateCaptionsRequest):
    """Translate caption segments, batching and running the batches in parallel."""
    total_chars = sum(len(s.text) for s in req.segments)
    if total_chars > MAX_CAPTION_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Transcript too long ({total_chars} chars, limit {MAX_CAPTION_CHARS}).",
        )

    lang_names = {"he": "עברית", "en": "English", "ar": "العربية", "ru": "Русский",
                  "fr": "Français", "es": "Español", "de": "Deutsch"}
    target_name = lang_names.get(req.target_language, req.target_language)
    nikud_rule = "- Use modern spoken Hebrew, no nikud" if req.target_language == "he" else ""

    batches = [
        req.segments[i:i + CAPTION_BATCH_SIZE]
        for i in range(0, len(req.segments), CAPTION_BATCH_SIZE)
    ]
    # Batches are independent; running them serially made a long video take
    # minutes for no reason.
    semaphore = asyncio.Semaphore(4)

    async def translate_batch(batch):
        numbered = "\n".join(f"{j + 1}. {seg.text}" for j, seg in enumerate(batch))
        prompt = f"""Translate these subtitle lines to {target_name}.

RULES:
- Return ONLY the numbered translations, one per line, same numbering
- Keep translations concise and natural for subtitles
- Do not add explanations or notes
{nikud_rule}

{numbered}"""
        async with semaphore:
            try:
                response = await get_gemini_client().aio.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                )
                lines = (response.text or "").strip().split("\n")
            except Exception:
                log.exception("caption batch translation failed; falling back to source text")
                lines = []

        out = []
        for j, seg in enumerate(batch):
            translated = seg.text
            for line in lines:
                match = re.match(rf'^{j + 1}[\.\)]\s*(.+)', line)
                if match:
                    translated = match.group(1).strip()
                    break
            out.append({
                "start": seg.start,
                "duration": seg.duration,
                "original": seg.text,
                "text": translated,
            })
        return out

    results = await asyncio.gather(*(translate_batch(b) for b in batches))
    return {"segments": [seg for batch in results for seg in batch]}


@app.get("/api/health")
async def health():
    return {"status": "ok"}




@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """
    Serve a generated track.

    Goes through storage.resolve, which rejects anything that is not a plain
    filename inside the audio directory. Artifacts are pruned on a TTL, so a
    404 here means expired, not missing.
    """
    path = storage.resolve(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Audio not found or expired.")
    return FileResponse(
        path,
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# Serve frontend static files (must be after API routes)
if FRONTEND_DIR.exists():
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA catch-all, refusing any path that resolves outside the build dir."""
        index = FRONTEND_DIR / "index.html"
        try:
            candidate = (FRONTEND_DIR / full_path).resolve()
        except (OSError, ValueError):
            return FileResponse(index)
        if candidate.is_file() and candidate.is_relative_to(FRONTEND_DIR):
            return FileResponse(candidate)
        return FileResponse(index)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8888))
    uvicorn.run(app, host="0.0.0.0", port=port)
