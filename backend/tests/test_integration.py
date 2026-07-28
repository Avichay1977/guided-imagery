"""
The whole path, end to end: generate a session, then remix it.

Only the two network calls are stubbed — the model and the TTS engine.
Everything downstream is the real pipeline: parsing, parallel assembly, cue
derivation, loudness, the ambience bed, encoding, storage and the HTTP layer.
The unit tests each cover one seam; this one covers the seams between them.
"""

import json

import pytest
from conftest import HAS_FFMPEG
from fastapi.testclient import TestClient
from pydub import AudioSegment

import main
import rate_limit
import storage
import tts_service
from config import OUTPUT_SAMPLE_RATE

pytestmark = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not available")

SCRIPT = "Settle in [breath] let go [pause] rest here [long_pause] and return"
SPEECH_MS = 1500


@pytest.fixture
def client(tmp_path, monkeypatch):
    for window in rate_limit._registry:
        window._hits.clear()
    monkeypatch.setattr(storage, "AUDIO_ROOT", tmp_path)

    class Models:
        async def generate_content(self, **kwargs):
            return type("R", (), {"text": SCRIPT})()

    monkeypatch.setattr(
        main, "get_gemini_client",
        lambda: type("C", (), {"aio": type("A", (), {"models": Models()})()})(),
    )

    async def fake_segment(text, language, state):
        return AudioSegment.silent(duration=SPEECH_MS, frame_rate=OUTPUT_SAMPLE_RATE)

    monkeypatch.setattr(tts_service, "_synthesize", fake_segment)

    with TestClient(main.app) as test_client:
        yield test_client


def generate(client, **overrides):
    payload = {
        "topic": "release anxiety", "duration_minutes": 5, "language": "en",
        "bells_volume": 60, "music_volume": 40,
    }
    payload.update(overrides)
    response = client.post("/api/session", json=payload)
    assert response.status_code == 200
    for line in response.text.splitlines():
        if line.startswith("data:") and "audio_url" in line:
            return json.loads(line[5:])
    raise AssertionError(f"no completion event in stream: {response.text[:400]}")


class TestGenerateThenRemix:
    def test_the_stream_completes_with_a_usable_result(self, client):
        result = generate(client)
        assert result["script"] == SCRIPT
        assert storage.is_session_id(result["session_id"])
        assert result["audio_url"].startswith("/audio/")

    def test_the_generated_audio_is_downloadable(self, client):
        result = generate(client)
        response = client.get(result["audio_url"])
        assert response.status_code == 200
        assert len(response.content) > 0

    def test_the_narration_is_kept_for_remixing(self, client):
        result = generate(client)
        assert storage.has_voice(result["session_id"])

    def test_cues_land_on_structural_pauses_only(self, client):
        # Settle in(0-1500) [breath](1500-5500) let go(5500-7000)
        # [pause](7000-10000) rest here(10000-11500) [long_pause](11500-16500)
        result = generate(client)
        meta = json.loads(storage.voice_meta_path(result["session_id"]).read_text())
        assert meta["cues"] == [7250, 11750]

    def test_the_mix_name_reflects_the_requested_ambience(self, client):
        result = generate(client)
        expected = storage.mix_filename(result["session_id"], 60, 40)
        assert result["audio_url"] == f"/audio/{expected}"

    def test_remixing_yields_different_audio_from_the_same_narration(self, client):
        result = generate(client)
        original = client.get(result["audio_url"]).content

        response = client.post("/api/remix", json={
            "session_id": result["session_id"], "bells_volume": 0, "music_volume": 0,
        })
        assert response.status_code == 200

        remixed = client.get(response.json()["audio_url"])
        assert remixed.status_code == 200
        assert remixed.content != original

    def test_remixing_does_not_touch_the_original_mix(self, client):
        result = generate(client)
        before = client.get(result["audio_url"]).content
        client.post("/api/remix", json={
            "session_id": result["session_id"], "bells_volume": 5, "music_volume": 95,
        })
        assert client.get(result["audio_url"]).content == before

    def test_seeking_works_on_the_generated_file(self, client):
        # A 20-minute session would otherwise refetch from the start on every seek.
        result = generate(client)
        response = client.get(result["audio_url"], headers={"Range": "bytes=0-99"})
        assert response.status_code == 206
        assert len(response.content) == 100

    def test_capacity_is_returned_after_the_whole_flow(self, client):
        result = generate(client)
        client.post("/api/remix", json={"session_id": result["session_id"], "bells_volume": 0})
        assert main._generation_slots._value == main.MAX_CONCURRENT_GENERATIONS

    def test_two_sessions_do_not_collide(self, client):
        first = generate(client)
        second = generate(client)
        assert first["session_id"] != second["session_id"]
        assert client.get(first["audio_url"]).status_code == 200
        assert client.get(second["audio_url"]).status_code == 200
