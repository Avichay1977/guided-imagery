import json
import asyncio
import re
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional
from sse_starlette.sse import EventSourceResponse
from google import genai
from youtube_transcript_api import YouTubeTranscriptApi

from config import GOOGLE_API_KEY, GEMINI_MODEL, AUDIO_OUTPUT_DIR
from prompt_template import build_meditation_prompt
from tts_service import generate_audio

app = FastAPI(title="Guided Imagery")

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://guided-imagery.onrender.com",
]
# Allow custom origin from env
if os.getenv("RENDER_EXTERNAL_URL"):
    ALLOWED_ORIGINS.append(os.getenv("RENDER_EXTERNAL_URL"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/audio", StaticFiles(directory=AUDIO_OUTPUT_DIR), name="audio")

# Serve built frontend in production
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"

gemini_client = None

def get_gemini_client():
    global gemini_client
    if gemini_client is None:
        gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
    return gemini_client


class SessionRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=200)
    duration_minutes: int = Field(..., ge=3, le=30)
    language: str = Field(default="he", pattern="^(he|en)$")
    mode: str = Field(default="imagery", pattern="^(imagery|hypnosis)$")
    depth: str = Field(default="standard", pattern="^(light|standard|medium|deep)$")
    age_group: str = Field(default="adults", pattern="^(children|teens|adults)$")
    bells_volume: int = Field(default=50, ge=0, le=100)


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50000)
    source_language: str = Field(..., pattern="^(he|en)$")
    target_language: str = Field(..., pattern="^(he|en)$")


@app.post("/api/session")
async def create_session(request: Request, session: SessionRequest):
    async def event_generator():
        try:
            # Stage 1: Generate script
            yield {
                "event": "progress",
                "data": json.dumps({
                    "stage": "generating_script",
                    "message": (
                        "יוצר תסריט היפנוזה..." if session.mode == "hypnosis" else "יוצר תסריט מדיטציה..."
                    ) if session.language == "he" else (
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
            )

            response = await get_gemini_client().aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            script = response.text.strip()

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
                    "message": "התסריט מוכן, מתחיל הקלטה..." if session.language == "he" else "Script ready, recording audio...",
                    "percent": 25,
                }, ensure_ascii=False),
            }

            # Stage 2: TTS with progress
            progress_queue = asyncio.Queue()

            async def on_tts_progress(stage, percent):
                overall = 25 + int(percent * 0.70)
                msg = f"מקליט אודיו... {percent}%" if session.language == "he" else f"Recording audio... {percent}%"
                await progress_queue.put({
                    "event": "progress",
                    "data": json.dumps({
                        "stage": stage,
                        "message": msg,
                        "percent": overall,
                    }, ensure_ascii=False),
                })

            tts_task = asyncio.create_task(
                generate_audio(script, on_tts_progress, bells_volume=session.bells_volume)
            )

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

            filename = tts_task.result()

            # Stage 3: Done
            yield {
                "event": "complete",
                "data": json.dumps({
                    "script": script,
                    "audio_url": f"/audio/{filename}",
                    "duration_minutes": session.duration_minutes,
                }, ensure_ascii=False),
            }

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e)}),
            }

    return EventSourceResponse(event_generator())


@app.post("/api/translate")
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

    response = await get_gemini_client().aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    translated = response.text.strip()
    return {"translated_text": translated}


# ── YouTube Translation ─────────────────────────────────────────

class YouTubeCaptionsRequest(BaseModel):
    video_url: str = Field(..., min_length=5)
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


@app.post("/api/youtube/captions")
async def get_youtube_captions(req: YouTubeCaptionsRequest):
    """Fetch YouTube captions and translate them to target language."""
    video_id = _extract_video_id(req.video_url)

    # Try to fetch captions in order of preference
    ytt_api = YouTubeTranscriptApi()
    transcript_list = ytt_api.list(video_id)

    captions = None
    source_lang = None

    # 1. Try target language first (already translated by YouTube)
    try:
        captions = ytt_api.fetch(transcript_list, languages=[req.target_language])
        source_lang = req.target_language
    except Exception:
        pass

    # 2. Try English
    if captions is None:
        try:
            captions = ytt_api.fetch(transcript_list, languages=["en"])
            source_lang = "en"
        except Exception:
            pass

    # 3. Try any available language
    if captions is None:
        try:
            captions = ytt_api.fetch(transcript_list)
            source_lang = "unknown"
        except Exception:
            return {"error": "No captions available for this video"}

    segments = [
        {"start": s.start, "duration": s.duration, "text": s.text}
        for s in captions
    ]

    return {
        "video_id": video_id,
        "source_language": source_lang,
        "segments": segments,
    }


@app.post("/api/youtube/translate-captions")
async def translate_youtube_captions(request: Request):
    """Translate caption segments to Hebrew using Gemini via SSE streaming."""
    body = await request.json()
    segments = body.get("segments", [])
    target_language = body.get("target_language", "he")

    if not segments:
        return {"error": "No segments provided"}

    lang_names = {"he": "עברית", "en": "English", "ar": "العربية", "ru": "Русский",
                  "fr": "Français", "es": "Español", "de": "Deutsch"}
    target_name = lang_names.get(target_language, target_language)

    # Translate in batches of 20 segments for speed
    BATCH_SIZE = 20
    translated_segments = []

    for i in range(0, len(segments), BATCH_SIZE):
        batch = segments[i:i + BATCH_SIZE]
        numbered_lines = "\n".join(
            f"{j+1}. {seg['text']}" for j, seg in enumerate(batch)
        )

        prompt = f"""Translate these subtitle lines to {target_name}.

RULES:
- Return ONLY the numbered translations, one per line, same numbering
- Keep translations concise and natural for subtitles
- Do not add explanations or notes
{"- Use modern spoken Hebrew, no nikud" if target_language == "he" else ""}

{numbered_lines}"""

        response = await get_gemini_client().aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

        lines = response.text.strip().split("\n")
        for j, seg in enumerate(batch):
            translated_text = seg["text"]  # fallback
            for line in lines:
                # Match "1. translated text" or "1) translated text"
                match = re.match(rf'^{j+1}[\.\)]\s*(.+)', line)
                if match:
                    translated_text = match.group(1).strip()
                    break
            translated_segments.append({
                "start": seg["start"],
                "duration": seg["duration"],
                "original": seg["text"],
                "text": translated_text,
            })

    return {"segments": translated_segments}


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Serve frontend static files (must be after API routes)
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="frontend_assets")
    app.mount("/locales", StaticFiles(directory=FRONTEND_DIR / "locales"), name="frontend_locales")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve index.html for all non-API routes (SPA catch-all)."""
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8888))
    uvicorn.run(app, host="0.0.0.0", port=port)
