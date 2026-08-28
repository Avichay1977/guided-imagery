"""
Tests for re-mixing a stored narration.

The point of keeping the voice track is that changing the ambience should cost
an overlay and an encode instead of a fresh script and a full TTS render. These
verify that the narration really is reused, that an already-rendered
combination is not re-encoded at all, and that a pruned session fails cleanly.
"""

import json

import pytest
from conftest import HAS_FFMPEG
from pydub import AudioSegment

import storage
import tts_service
from config import OUTPUT_SAMPLE_RATE

pytestmark = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not available")


def tone(duration_ms, amplitude=0.4):
    import numpy as np

    n = int(OUTPUT_SAMPLE_RATE * duration_ms / 1000)
    samples = (np.full(n, amplitude, dtype=np.float32) * 32767).astype(np.int16)
    return AudioSegment(samples.tobytes(), frame_rate=OUTPUT_SAMPLE_RATE, sample_width=2, channels=1)


@pytest.fixture
def audio_root(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "AUDIO_ROOT", tmp_path)
    return tmp_path


@pytest.fixture
def session(audio_root):
    """A finalized session: narration on disk, cue sidecar, one mix."""
    parts = [tone(1200), AudioSegment.silent(duration=2000, frame_rate=OUTPUT_SAMPLE_RATE), tone(1200)]
    session_id = storage.new_session_id()
    filename = tts_service._finalize(parts, [1300], 50, 35, session_id, "en")
    return {"id": session_id, "filename": filename}


class TestFinalize:
    def test_stores_the_narration_for_later(self, audio_root, session):
        assert storage.voice_path(session["id"]).is_file()

    def test_stores_the_cue_points_alongside_it(self, audio_root, session):
        meta = json.loads(storage.voice_meta_path(session["id"]).read_text())
        assert meta["cues"] == [1300]
        assert meta["language"] == "en"
        assert meta["duration_ms"] > 0

    def test_writes_the_mix_under_its_derived_name(self, audio_root, session):
        assert session["filename"] == storage.mix_filename(session["id"], 50, 35)
        assert storage.mix_path(session["id"], 50, 35).is_file()

    def test_has_voice_reports_the_session(self, audio_root, session):
        assert storage.has_voice(session["id"]) is True


class TestRemix:
    def test_produces_a_new_mix_at_the_new_setting(self, audio_root, session):
        filename = tts_service._remix_blocking(session["id"], 90, 90)
        assert filename == storage.mix_filename(session["id"], 90, 90)
        assert storage.mix_path(session["id"], 90, 90).is_file()

    def test_the_new_mix_actually_differs_from_the_original(self, audio_root, session):
        tts_service._remix_blocking(session["id"], 0, 0)
        original = storage.mix_path(session["id"], 50, 35).read_bytes()
        dry = storage.mix_path(session["id"], 0, 0).read_bytes()
        assert original != dry

    def test_does_not_resynthesize_anything(self, audio_root, session, monkeypatch):
        # Nothing in the remix path may reach the TTS engines.
        async def explode(*args, **kwargs):
            raise AssertionError("remix must not call the TTS engine")

        monkeypatch.setattr(tts_service, "_synthesize", explode)
        monkeypatch.setattr(tts_service, "_synthesize_with_retry", explode)
        assert tts_service._remix_blocking(session["id"], 20, 80)

    def test_repeating_a_combination_skips_the_encode_entirely(self, audio_root, session, monkeypatch):
        tts_service._remix_blocking(session["id"], 70, 10)

        calls = []
        real_mix = tts_service._mix
        monkeypatch.setattr(tts_service, "_mix", lambda *a, **k: calls.append(1) or real_mix(*a, **k))

        tts_service._remix_blocking(session["id"], 70, 10)
        assert calls == [], "an already-rendered combination should not be mixed again"

    def test_the_original_narration_survives_remixing(self, audio_root, session):
        tts_service._remix_blocking(session["id"], 0, 0)
        assert storage.voice_path(session["id"]).is_file()

    def test_remixing_keeps_the_narration_from_ageing_out(self, audio_root, session):
        import os

        voice = storage.voice_path(session["id"])
        os.utime(voice, (1_000_000, 1_000_000))
        tts_service._remix_blocking(session["id"], 15, 15)
        assert voice.stat().st_mtime > 1_000_000

    def test_missing_narration_raises_rather_than_producing_silence(self, audio_root):
        with pytest.raises(FileNotFoundError):
            tts_service._remix_blocking("abcdef123456", 50, 35)

    def test_narration_without_its_sidecar_is_treated_as_missing(self, audio_root, session):
        storage.voice_meta_path(session["id"]).unlink()
        with pytest.raises(FileNotFoundError):
            tts_service._remix_blocking(session["id"], 11, 22)

    @pytest.mark.asyncio
    async def test_async_wrapper_returns_the_filename(self, audio_root, session):
        filename = await tts_service.remix(session["id"], 25, 25)
        assert filename == storage.mix_filename(session["id"], 25, 25)


class TestAtomicWrites:
    """
    Mix names are derived from their inputs, so concurrent requests for the same
    remix target the same path. Callers treat "the file exists" as "already
    rendered", so a partial file would be served as if it were finished.
    """

    def test_a_failed_encode_leaves_no_file_behind(self, audio_root, session, monkeypatch):
        target = storage.mix_path(session["id"], 33, 33)

        def explode(self, *args, **kwargs):
            raise RuntimeError("encoder died")

        monkeypatch.setattr(AudioSegment, "export", explode)
        with pytest.raises(RuntimeError):
            tts_service._remix_blocking(session["id"], 33, 33)

        assert not target.exists(), "a half-written mix must not be left in place"

    def test_a_failed_encode_leaves_no_temp_files(self, audio_root, session, monkeypatch):
        def explode(self, *args, **kwargs):
            raise RuntimeError("encoder died")

        monkeypatch.setattr(AudioSegment, "export", explode)
        with pytest.raises(RuntimeError):
            tts_service._remix_blocking(session["id"], 44, 44)

        assert list(audio_root.glob(".*tmp")) == []

    def test_the_previous_mix_survives_a_failed_re_encode(self, audio_root, session, monkeypatch):
        # Render once, then fail while overwriting the same target.
        tts_service._remix_blocking(session["id"], 55, 55)
        target = storage.mix_path(session["id"], 55, 55)
        good = target.read_bytes()
        target.unlink()  # force the re-encode path
        assert not target.exists()

        def explode(self, *args, **kwargs):
            raise RuntimeError("encoder died")

        monkeypatch.setattr(AudioSegment, "export", explode)
        with pytest.raises(RuntimeError):
            tts_service._remix_blocking(session["id"], 55, 55)
        assert not target.exists()
        assert good  # the earlier render really did produce bytes

    def test_a_completed_encode_leaves_only_the_final_file(self, audio_root, session):
        tts_service._remix_blocking(session["id"], 66, 66)
        assert storage.mix_path(session["id"], 66, 66).is_file()
        assert list(audio_root.glob(".*tmp")) == []

    def test_temp_files_are_never_servable(self, audio_root):
        # Even if a crash strands one, it cannot be fetched over HTTP.
        stranded = audio_root / ".meditation_abcdef123456b50m35.mp3.deadbeef.tmp"
        stranded.write_bytes(b"partial")
        assert storage.resolve(stranded.name) is None


class TestSessionIds:
    @pytest.mark.parametrize("value", ["abcdef123456", "000000000000", "ffffffffffff"])
    def test_accepts_well_formed_ids(self, value):
        assert storage.is_session_id(value)

    @pytest.mark.parametrize("value", [
        "", "short", "ABCDEF123456", "abcdef12345", "abcdef1234567", "../../etc", "abcdef12345g",
    ])
    def test_rejects_anything_else(self, value):
        assert not storage.is_session_id(value)

    def test_generated_ids_are_well_formed_and_unique(self):
        ids = {storage.new_session_id() for _ in range(50)}
        assert len(ids) == 50
        assert all(storage.is_session_id(i) for i in ids)
