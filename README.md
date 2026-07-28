# Guided Imagery

Generates guided-imagery and self-hypnosis sessions in Hebrew or English: a
script written by Gemini, narrated by TTS, mixed over an ambience bed of
pause-synced bells and a soft drone, and streamed back as a single MP3.

The prompt templates are built on published protocols — Ericksonian indirect
suggestion, the Dave Elman induction, the 5-phase guided imagery model, and
Elkins' Hypnotic Relaxation Therapy. See `backend/prompt_template.py` for the
full list of sources.

## Repository layout

| Path | What it is |
|---|---|
| `backend/` | FastAPI service: script generation, TTS, audio mixing |
| `frontend/` | React + Vite PWA (Hebrew/English, RTL-aware) |
| `spectrum-rights/` | Separate app — Israeli disability-rights guide, deployed to GitHub Pages |

## Running locally

```bash
# Backend
cd backend
pip install -r requirements-dev.txt
cp .env.example .env        # then fill in your keys
python main.py              # serves on :8888

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                 # serves on :5173, proxies /api to the backend
```

## Configuration

Only `GOOGLE_API_KEY` is required. Everything else has a working default.

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | — | **Required.** Gemini, for script generation and translation |
| `ELEVEN_API_KEY` | — | Only needed when `TTS_ENGINE=elevenlabs` |
| `ELEVEN_VOICE_ID` | Rachel | ElevenLabs voice |
| `TTS_ENGINE` | `edge` | `edge` (free) or `elevenlabs`. Falls back to edge on a quota error |
| `TTS_CONCURRENCY` | `4` | Segments synthesized in parallel |
| `GEMINI_MODEL` | `gemini-2.5-flash` | |
| `AUDIO_TTL_HOURS` | `6` | How long a rendered track survives before pruning |
| `AUDIO_MAX_MB` | `512` | Total size budget for rendered audio |
| `TTS_MAX_ATTEMPTS` | `3` | Retries per segment before a render is abandoned |
| `RATE_LIMIT_SESSION` | `5/hour` | Per-client generation budget |
| `RATE_LIMIT_TRANSLATE` | `20/hour` | |
| `RATE_LIMIT_YOUTUBE` | `10/hour` | |
| `RATE_LIMIT_REMIX` | `60/hour` | Remixing costs no model or TTS calls, so it is generous |
| `MAX_CONCURRENT_GENERATIONS` | `2` | Process-wide ceiling on simultaneous renders |
| `TRUSTED_PROXY_HOPS` | `1` | Reverse proxies in front of the app; used to read the real client IP |
| `ALLOWED_ORIGINS` | localhost + Render | Extra CORS origins, comma-separated |
| `LOG_LEVEL` | `INFO` | |
| `DEBUG_ERRORS` | `false` | Return raw exception text to clients. Never enable in production |

## How a session is built

1. **Script** — Gemini writes the narration with inline pause markers
   (`[breath]`, `[short_pause]`, `[pause]`, `[long_pause]`).
2. **Nikud** — Hebrew text passes through Phonikud so the TTS pronounces it
   correctly. English skips this entirely.
3. **Narration** — the script is split on pause markers and the pieces are
   synthesized **in parallel**, then reassembled in order.
4. **Ambience** — bells ring at the structural pauses, never mid-sentence, over
   a drone bed. See below.
5. **Encode** — one MP3, streamed to the client over SSE with live progress.

## Changing the ambience without re-generating

The narration is stored separately from the finished mix, so adjusting the bells
or the music bed does not mean making a new session. `POST /api/remix` takes a
`session_id` and new volumes and re-mixes the recording that already exists —
no Gemini call, no TTS, seconds instead of minutes.

Mix files are named after their inputs (`meditation_<id>b<bells>m<music>.mp3`),
which makes the whole thing idempotent: asking for a combination that was
already rendered is a `stat()`, not an encode.

The one cost is that a narration is kept alongside its mixes, roughly doubling
the storage per session. The janitor accounts for that by pruning in tiers — a
mix can be rebuilt from its narration in seconds, so mixes are dropped first and
narrations only if that is not enough.

## Notes on the audio engine

Three decisions in `audio_mix.py` and `tts_service.py` are load-bearing:

**Bells follow the script.** Cue positions come from the actual pause markers,
offset a moment into the silence. A chime marks a transition instead of
interrupting a sentence.

**The bed is one seamless loop.** Every partial and LFO in the drone is snapped
to a whole number of cycles per loop window, so tiling it needs no crossfade and
has no audible seam. `test_audio_mix.py` pins this property down directly.

**Ambience is synthesized at 16 kHz and resampled up.** Nothing in it exceeds
~4.8 kHz, so this costs nothing audible and cuts peak memory to roughly a third
of synthesizing at 44.1 kHz. It matters: a 20-minute session is a large buffer.

Assembly joins the raw PCM buffers in a single pass. Repeated `AudioSegment +=`
copies the whole accumulated track on every step, which is quadratic in the
number of segments — a real cost at ~100 segments per session.

## Tests

```bash
cd backend
python -m pytest tests/ -v
```

The audio-encode tests need `ffmpeg` on PATH and skip cleanly without it.
Everything else runs anywhere.

## Deployment

`render.yaml` defines the service. The build compiles the frontend and serves it
from the same FastAPI process, so there is one service and no CORS in
production.

One thing to know: **the host filesystem is ephemeral.** Rendered audio does not
survive a deploy or restart. It is treated as a cache — every file carries a TTL
and a janitor prunes by age and total size. If sessions ever need to be durable,
that is the piece to move to object storage; `storage.py` is the seam.
