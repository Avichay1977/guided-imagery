"""
The generation slot must always come back.

`MAX_CONCURRENT_GENERATIONS` is the backstop that holds when per-client rate
limiting is defeated by a spoofed forwarding header. It is acquired before the
SSE response is returned and released inside the generator, so any path that
skips the release permanently removes capacity from the process — a slow leak
that ends in every request getting a 429 with nothing actually running.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

import main
import rate_limit
from config import MAX_CONCURRENT_GENERATIONS


class FakeResponse:
    text = "Breathe in [pause] and out [long_pause] rest"


class FakeModels:
    async def generate_content(self, **kwargs):
        return FakeResponse()


class FakeClient:
    aio = type("Aio", (), {"models": FakeModels()})()


@pytest.fixture
def client(monkeypatch):
    for window in rate_limit._registry:
        window._hits.clear()
    monkeypatch.setattr(main, "get_gemini_client", lambda: FakeClient())
    with TestClient(main.app) as test_client:
        yield test_client


def slots_free() -> int:
    return main._generation_slots._value


def payload():
    return {"topic": "release anxiety", "duration_minutes": 5}


class TestGenerationSlot:
    def test_starts_at_full_capacity(self, client):
        assert slots_free() == MAX_CONCURRENT_GENERATIONS

    def test_slot_is_returned_after_a_successful_render(self, client, monkeypatch):
        async def fake_render(script, on_progress=None, **kwargs):
            if on_progress:
                await on_progress("tts_progress", 100)
            return {"session_id": "abcdef123456", "filename": "meditation_abcdef123456b50m35.mp3"}

        monkeypatch.setattr(main, "generate_audio", fake_render)

        response = client.post("/api/session", json=payload())
        assert response.status_code == 200
        assert "complete" in response.text
        assert slots_free() == MAX_CONCURRENT_GENERATIONS

    def test_slot_is_returned_when_rendering_fails(self, client, monkeypatch):
        async def fake_render(script, on_progress=None, **kwargs):
            raise RuntimeError("render exploded")

        monkeypatch.setattr(main, "generate_audio", fake_render)

        response = client.post("/api/session", json=payload())
        assert response.status_code == 200  # the stream opens, then reports an error
        assert "error" in response.text
        assert slots_free() == MAX_CONCURRENT_GENERATIONS

    def test_slot_is_returned_when_the_model_returns_nothing(self, client, monkeypatch):
        class EmptyModels:
            async def generate_content(self, **kwargs):
                return type("R", (), {"text": "   "})()

        monkeypatch.setattr(
            main, "get_gemini_client",
            lambda: type("C", (), {"aio": type("A", (), {"models": EmptyModels()})()})(),
        )

        response = client.post("/api/session", json=payload())
        assert response.status_code == 200
        assert slots_free() == MAX_CONCURRENT_GENERATIONS

    def test_slot_is_returned_when_the_model_call_raises(self, client, monkeypatch):
        class BrokenModels:
            async def generate_content(self, **kwargs):
                raise RuntimeError("gemini unavailable")

        monkeypatch.setattr(
            main, "get_gemini_client",
            lambda: type("C", (), {"aio": type("A", (), {"models": BrokenModels()})()})(),
        )

        client.post("/api/session", json=payload())
        assert slots_free() == MAX_CONCURRENT_GENERATIONS

    def test_repeated_renders_do_not_leak_capacity(self, client, monkeypatch):
        # A leak of one slot per request is the failure this guards against.
        async def fake_render(script, on_progress=None, **kwargs):
            return {"session_id": "abcdef123456", "filename": "meditation_abcdef123456b50m35.mp3"}

        monkeypatch.setattr(main, "generate_audio", fake_render)

        for _ in range(4):
            client.post("/api/session", json=payload())
        assert slots_free() == MAX_CONCURRENT_GENERATIONS

    def test_requests_are_refused_once_every_slot_is_busy(self, client):
        # Simulate a full house: the next caller should be turned away rather
        # than queued behind an expensive render.
        original = main._generation_slots._value
        main._generation_slots._value = 0
        try:
            response = client.post("/api/session", json=payload())
            assert response.status_code == 429
            assert response.headers.get("Retry-After")
        finally:
            main._generation_slots._value = original

        assert slots_free() == MAX_CONCURRENT_GENERATIONS

    def test_a_refused_request_does_not_consume_a_slot(self, client):
        original = main._generation_slots._value
        main._generation_slots._value = 0
        try:
            client.post("/api/session", json=payload())
        finally:
            main._generation_slots._value = original
        assert slots_free() == MAX_CONCURRENT_GENERATIONS
