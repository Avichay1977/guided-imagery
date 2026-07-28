import pytest
from fastapi.testclient import TestClient

import rate_limit
from main import app


@pytest.fixture
def client():
    # Limiter state is process-global and shared across tests, so each test
    # starts from a clean window.
    for window in rate_limit._registry:
        window._hits.clear()
    with TestClient(app) as test_client:
        yield test_client


class TestHealth:
    def test_health_is_ok(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestSessionValidation:
    """These never reach Gemini — validation rejects them first."""

    @pytest.mark.parametrize("payload", [
        {"topic": "x", "duration_minutes": 10},                        # topic too short
        {"topic": "calm", "duration_minutes": 99},                     # over max duration
        {"topic": "calm", "duration_minutes": 1},                      # under min duration
        {"topic": "calm", "duration_minutes": 10, "language": "fr"},   # unsupported language
        {"topic": "calm", "duration_minutes": 10, "mode": "wat"},      # unknown mode
        {"topic": "calm", "duration_minutes": 10, "bells_volume": 500},
        {"topic": "calm", "duration_minutes": 10, "music_volume": -1},
        {"duration_minutes": 10},                                      # missing topic
    ])
    def test_rejects_bad_input(self, client, payload):
        assert client.post("/api/session", json=payload).status_code == 422

    def test_topic_length_is_bounded(self, client):
        response = client.post("/api/session", json={"topic": "a" * 500, "duration_minutes": 10})
        assert response.status_code == 422


class TestTranslate:
    def test_same_language_returns_input_untouched(self, client):
        # Short-circuits before any model call.
        response = client.post("/api/translate", json={
            "text": "שלום", "source_language": "he", "target_language": "he",
        })
        assert response.status_code == 200
        assert response.json() == {"translated_text": "שלום"}

    def test_rejects_oversized_text(self, client):
        response = client.post("/api/translate", json={
            "text": "a" * 60_000, "source_language": "en", "target_language": "he",
        })
        assert response.status_code == 422

    def test_rejects_empty_text(self, client):
        response = client.post("/api/translate", json={
            "text": "", "source_language": "en", "target_language": "he",
        })
        assert response.status_code == 422


class TestCaptionLimits:
    def test_rejects_an_unbounded_segment_list(self, client):
        segments = [{"start": i, "duration": 1, "text": "hi"} for i in range(5_000)]
        response = client.post("/api/youtube/translate-captions", json={
            "segments": segments, "target_language": "he",
        })
        assert response.status_code == 422

    def test_rejects_an_empty_segment_list(self, client):
        response = client.post("/api/youtube/translate-captions", json={
            "segments": [], "target_language": "he",
        })
        assert response.status_code == 422

    def test_rejects_a_transcript_over_the_character_budget(self, client):
        # Few enough segments to pass the count check, but far too much text.
        segments = [{"start": i, "duration": 1, "text": "x" * 1_500} for i in range(100)]
        response = client.post("/api/youtube/translate-captions", json={
            "segments": segments, "target_language": "he",
        })
        assert response.status_code == 413

    def test_rejects_an_invalid_youtube_url_shape(self, client):
        response = client.post("/api/youtube/captions", json={"video_url": "x"})
        assert response.status_code == 422


class TestAudioServing:
    """
    Two behaviours to keep apart.

    Names that reach the audio route but do not name a real artifact must 404.
    Encoded traversal never reaches that route at all — the HTTP layer
    normalizes the path first, so it lands on the SPA catch-all when the
    frontend is built, or nowhere when it is not. Either way the requirement is
    the same and it is about disclosure, not about a status code, so that is
    what these assert.
    """

    LEAK_MARKERS = (b"root:", b"GOOGLE_API_KEY", b"ELEVEN_API_KEY", b"import os")

    @pytest.mark.parametrize("name", [
        "meditation_nope.mp3",   # well-formed, simply does not exist
        "config.py",             # inside the root but not an artifact name
        "notanartifact.txt",
    ])
    def test_names_that_are_not_artifacts_are_404(self, client, name):
        assert client.get(f"/audio/{name}").status_code == 404

    @pytest.mark.parametrize("path", [
        "/audio/..%2F..%2Fconfig.py",
        "/audio/..%5C..%5Cconfig.py",
        "/audio/%2Fetc%2Fpasswd",
        "/audio/....//....//config.py",
        "/audio/%2e%2e%2f%2e%2e%2fconfig.py",
    ])
    def test_traversal_never_discloses_a_file(self, client, path):
        response = client.get(path)
        assert not any(marker in response.content for marker in self.LEAK_MARKERS)

    def test_traversal_outside_the_repo_discloses_nothing(self, client):
        response = client.get("/audio/%2Fetc%2Fpasswd")
        assert b"root:" not in response.content
        assert b"/bin/bash" not in response.content


class TestRemixEndpoint:
    @pytest.mark.parametrize("payload", [
        {"session_id": "short"},
        {"session_id": "ABCDEF123456"},                          # uppercase is not our id shape
        {"session_id": "../../../etc/passwd"},
        {"session_id": "abcdef123456", "bells_volume": 300},
        {"session_id": "abcdef123456", "music_volume": -5},
        {},
    ])
    def test_rejects_bad_input(self, client, payload):
        assert client.post("/api/remix", json=payload).status_code == 422

    def test_unknown_session_is_404_not_a_server_error(self, client):
        response = client.post("/api/remix", json={
            "session_id": "abcdef123456", "bells_volume": 50, "music_volume": 35,
        })
        assert response.status_code == 404

    def test_expired_session_explains_itself(self, client):
        response = client.post("/api/remix", json={"session_id": "0123456789ab"})
        assert response.status_code == 404
        assert "generate a new one" in response.json()["detail"].lower()

    def test_remixes_a_real_session(self, client, monkeypatch, tmp_path):
        import storage
        import tts_service

        monkeypatch.setattr(storage, "AUDIO_ROOT", tmp_path)
        session_id = "abcdef123456"
        storage.voice_path(session_id).write_bytes(b"not really audio")
        storage.voice_meta_path(session_id).write_text('{"cues": [100]}')

        async def fake_remix(sid, bells, music):
            return storage.mix_filename(sid, bells, music)

        monkeypatch.setattr(tts_service, "remix", fake_remix)

        response = client.post("/api/remix", json={
            "session_id": session_id, "bells_volume": 70, "music_volume": 20,
        })
        assert response.status_code == 200
        body = response.json()
        assert body["session_id"] == session_id
        assert body["audio_url"] == f"/audio/{storage.mix_filename(session_id, 70, 20)}"


class TestRateLimiting:
    def test_repeated_calls_eventually_get_429_with_retry_after(self, client):
        payload = {"text": "hi", "source_language": "he", "target_language": "he"}
        statuses = [client.post("/api/translate", json=payload).status_code for _ in range(30)]

        assert statuses[0] == 200, "the first request should always be allowed"
        assert 429 in statuses, "the limiter should reject once the window fills"

        limited = client.post("/api/translate", json=payload)
        assert limited.status_code == 429
        assert "Retry-After" in limited.headers

    def test_the_limit_matches_the_configured_spec(self, client):
        from config import RATE_LIMIT_TRANSLATE
        from rate_limit import parse_spec

        allowed, _ = parse_spec(RATE_LIMIT_TRANSLATE)
        payload = {"text": "hi", "source_language": "he", "target_language": "he"}
        statuses = [client.post("/api/translate", json=payload).status_code for _ in range(allowed + 1)]

        assert statuses[:allowed] == [200] * allowed
        assert statuses[allowed] == 429


class TestCors:
    def test_credentialed_cors_is_not_advertised(self, client):
        response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        assert response.headers.get("access-control-allow-credentials") != "true"

    def test_known_origin_is_allowed(self, client):
        response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_unknown_origin_is_not_echoed_back(self, client):
        response = client.get("/api/health", headers={"Origin": "https://evil.example"})
        assert response.headers.get("access-control-allow-origin") != "https://evil.example"
