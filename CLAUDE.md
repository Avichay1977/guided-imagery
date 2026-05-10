# Guided Imagery — Claude Code Guide

## Project overview

Guided Imagery is a meditation and hypnosis app. Users describe a topic, choose a duration and depth, and the backend generates a fully voiced audio session. It supports Hebrew and English, with a YouTube simultaneous-translation feature as a bonus tool.

Stack:
- **Backend**: FastAPI + Google Gemini (script generation) + ElevenLabs / edge-tts (TTS) + pydub (audio mixing)
- **Frontend**: React 19 + Vite + react-i18next (Hebrew/English)
- **Deploy**: Render (single service — frontend is built and served as static files by the FastAPI process)

---

## Local development

### Environment variables

Create `backend/.env`:

```
GOOGLE_API_KEY=...
ELEVEN_API_KEY=...           # optional — falls back to edge-tts when absent
ELEVEN_VOICE_ID=...          # optional — defaults to Rachel (21m00Tcm4TlvDq8ikWAM)
```

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8888
```

API available at `http://localhost:8888`.

### Frontend

```bash
cd frontend
npm install
npm run dev       # dev server on http://localhost:5173 — proxies /api to port 8888
```

### Production build (mirrors Render)

```bash
cd frontend && npm run build
cd ../backend && uvicorn main:app --host 0.0.0.0 --port 8888
```

The FastAPI app serves the built frontend from `frontend/dist` when that directory exists.

---

## Key files

| Path | Purpose |
|------|---------|
| `backend/main.py` | All API routes: `/api/session`, `/api/translate`, `/api/youtube/*`, `/api/health` |
| `backend/prompt_template.py` | Builds the Gemini prompt for meditation/hypnosis scripts |
| `backend/tts_service.py` | ElevenLabs TTS with pydub silence splicing; falls back to edge-tts |
| `backend/bells_service.py` | Mixes bell tones into the audio at session start/end |
| `backend/config.py` | Reads env vars; configures Gemini model, TTS settings, pause durations |
| `frontend/src/components/SessionForm.jsx` | Main form — topic, duration, mode, depth, age group, bells volume |
| `frontend/src/components/ScriptDisplay.jsx` | Shows generated script with inline translation toggle |
| `frontend/src/components/AudioPlayer.jsx` | Custom audio player for the generated session |
| `frontend/src/components/YouTubeTranslator.jsx` | YouTube URL → Hebrew subtitle overlay |
| `frontend/src/hooks/useSession.js` | SSE client that drives the progress flow |

---

## Architecture notes

- `/api/session` is a **Server-Sent Events (SSE)** endpoint. The frontend `useSession` hook consumes progress events (`generating_script`, `script_ready`, recording stages) and a final `complete` event that carries the script and audio URL.
- Audio generation produces an MP3 in `backend/audio_output/`. Files are served under `/audio/`. There is no cleanup scheduled — for production you would want a periodic purge or object storage.
- The TTS pipeline detects pause markers (`[pause]`, `[short_pause]`, `[long_pause]`, `[breath]`) in the script and splices silent audio segments of the configured durations.
- Nikud (Hebrew diacritics) are added to the Hebrew script via `phonikud` before being sent to the TTS service to improve pronunciation accuracy.

---

## Using Remote Control for this project

[Remote Control](https://code.claude.com/docs/remote-control) lets you continue a Claude Code session running on your development machine from a browser or the Claude mobile app, without stopping the local process. This is useful when you start a task (e.g., debugging the TTS pipeline) at your desk and want to keep working from another device.

### Quick start

1. Make sure you're on Claude Code v2.1.51 or later (`claude --version`).
2. Sign in with a claude.ai Pro/Max/Team/Enterprise account — API keys are not supported.
3. From this project directory:

   ```bash
   # Server mode — stays running, accepts connections from any device
   claude remote-control --name "Guided Imagery"

   # Or: start an interactive session that's also accessible remotely
   claude --remote-control "Guided Imagery"
   ```

4. Open the session URL shown in the terminal, scan the QR code, or find the session by name at [claude.ai/code](https://claude.ai/code) or in the Claude mobile app under **Code**.

### Useful flags for this project

| Flag | When to use |
|------|-------------|
| `--spawn worktree` | Working on multiple features in parallel without file conflicts — each remote connection gets its own git worktree |
| `--sandbox` | Experimenting with unfamiliar TTS or audio dependencies and want filesystem/network isolation |
| `--name "Guided Imagery"` | Keeps the session easy to find in the remote session list |

### Limitations to keep in mind

- The backend dev server and the `claude remote-control` process both need to stay running on your machine. If you close the terminal, both stop.
- If your machine is offline for more than ~10 minutes the Remote Control session times out; run `claude remote-control` again to reconnect.
- The `/mobile` command inside Claude Code shows a download QR code for the Claude app if you don't have it yet.

---

## Deployment

The app deploys automatically to Render on every push to `main`. The build command installs frontend dependencies and runs `vite build`, then installs Python dependencies. The start command runs `uvicorn` from the `backend/` directory.

Required Render environment variables (set in the Render dashboard):

- `GOOGLE_API_KEY`
- `ELEVEN_API_KEY`
- `ELEVEN_VOICE_ID` (optional)
