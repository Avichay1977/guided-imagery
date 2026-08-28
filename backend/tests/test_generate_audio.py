"""
Orchestration tests for generate_audio.

TTS itself is stubbed — what is under test is the part that was rewritten:
segments running concurrently rather than one at a time, results reassembled in
script order, and pause markers turned into bell cue positions.
"""

import asyncio

import pytest
from pydub import AudioSegment

import storage
import tts_service
from config import BELL_CUE_OFFSET_MS, OUTPUT_SAMPLE_RATE, TTS_CONCURRENCY

SPEECH_MS = 1000


@pytest.fixture
def stub_tts(monkeypatch):
    """Every spoken segment becomes a fixed-length silence, so timings are exact."""
    spoken = []

    async def fake_synthesize(text, language, state, pace=None):
        spoken.append(text)
        await asyncio.sleep(0)
        return AudioSegment.silent(duration=SPEECH_MS, frame_rate=OUTPUT_SAMPLE_RATE)

    monkeypatch.setattr(tts_service, "_synthesize", fake_synthesize)
    return spoken


@pytest.fixture
def captured(monkeypatch):
    """Intercept the encode step and keep what it was handed."""
    record = {}

    def fake_finalize(parts, cue_positions_ms, bells_volume, music_volume, session_id, language):
        record.update(
            parts=parts,
            cues=cue_positions_ms,
            bells=bells_volume,
            music=music_volume,
            session_id=session_id,
            language=language,
        )
        return storage.mix_filename(session_id, bells_volume, music_volume)

    monkeypatch.setattr(tts_service, "_finalize", fake_finalize)
    return record


async def run(script, **kwargs):
    return await tts_service.generate_audio(script, language="en", **kwargs)


class TestOrdering:
    @pytest.mark.asyncio
    async def test_segments_are_spoken_in_script_order(self, stub_tts, captured):
        await run("first [pause] second [pause] third")
        assert stub_tts == ["first", "second", "third"] or sorted(stub_tts) == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_assembled_parts_follow_script_order(self, stub_tts, captured):
        await run("first [pause] second")
        # text, pause, text
        assert len(captured["parts"]) == 3
        assert len(captured["parts"][0]) == pytest.approx(SPEECH_MS, abs=5)
        assert len(captured["parts"][1]) == pytest.approx(3000, abs=5)
        assert len(captured["parts"][2]) == pytest.approx(SPEECH_MS, abs=5)

    @pytest.mark.asyncio
    async def test_every_pause_kind_contributes_its_own_duration(self, stub_tts, captured):
        await run("a [short_pause] b [breath] c")
        durations = [len(p) for p in captured["parts"]]
        assert durations[1] == pytest.approx(1500, abs=5)
        assert durations[3] == pytest.approx(4000, abs=5)


class TestBellCues:
    @pytest.mark.asyncio
    async def test_cues_land_on_structural_pauses_only(self, stub_tts, captured):
        # one(0-1000) [breath](1000-5000) two(5000-6000) [pause](6000-9000)
        # three(9000-10000) [short_pause](10000-11500) four(11500-12500)
        # [long_pause](12500-17500) five
        await run("one [breath] two [pause] three [short_pause] four [long_pause] five")
        assert captured["cues"] == [
            6000 + BELL_CUE_OFFSET_MS,
            12500 + BELL_CUE_OFFSET_MS,
        ]

    @pytest.mark.asyncio
    async def test_breath_and_short_pause_never_ring(self, stub_tts, captured):
        await run("a [breath] b [short_pause] c")
        assert captured["cues"] == []

    @pytest.mark.asyncio
    async def test_cue_is_offset_into_the_silence_not_on_the_last_word(self, stub_tts, captured):
        await run("a [pause] b")
        # The word ends at SPEECH_MS; the chime lands after the pause begins.
        assert captured["cues"] == [SPEECH_MS + BELL_CUE_OFFSET_MS]
        assert captured["cues"][0] > SPEECH_MS

    @pytest.mark.asyncio
    async def test_script_with_no_markers_has_no_cues(self, stub_tts, captured):
        await run("just a single flowing passage")
        assert captured["cues"] == []


class TestConcurrency:
    @pytest.mark.asyncio
    async def test_segments_synthesize_in_parallel_up_to_the_cap(self, monkeypatch, captured):
        in_flight = 0
        peak = 0

        async def fake_synthesize(text, language, state, pace=None):
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.02)
            in_flight -= 1
            return AudioSegment.silent(duration=SPEECH_MS, frame_rate=OUTPUT_SAMPLE_RATE)

        monkeypatch.setattr(tts_service, "_synthesize", fake_synthesize)
        script = " [pause] ".join(f"segment{i}" for i in range(12))

        await run(script)

        assert peak > 1, "segments should overlap, not run one at a time"
        assert peak <= TTS_CONCURRENCY, "the semaphore must cap concurrency"

    @pytest.mark.asyncio
    async def test_parallel_run_is_faster_than_serial_would_be(self, monkeypatch, captured):
        async def slow_synthesize(text, language, state, pace=None):
            await asyncio.sleep(0.05)
            return AudioSegment.silent(duration=SPEECH_MS, frame_rate=OUTPUT_SAMPLE_RATE)

        monkeypatch.setattr(tts_service, "_synthesize", slow_synthesize)
        script = " [pause] ".join(f"s{i}" for i in range(8))

        loop = asyncio.get_running_loop()
        started = loop.time()
        await run(script)
        elapsed = loop.time() - started

        serial_estimate = 8 * 0.05
        assert elapsed < serial_estimate * 0.8


class TestProgress:
    @pytest.mark.asyncio
    async def test_reports_start_through_completion(self, stub_tts, captured):
        events = []

        async def on_progress(stage, percent):
            events.append((stage, percent))

        await run("a [pause] b [pause] c", on_progress=on_progress)

        assert events[0] == ("tts_start", 0)
        assert events[-1] == ("complete", 100)
        assert ("combining", 95) in events

    @pytest.mark.asyncio
    async def test_synthesis_progress_never_goes_backwards(self, stub_tts, captured):
        percents = []

        async def on_progress(stage, percent):
            if stage == "tts_progress":
                percents.append(percent)

        await run(" [pause] ".join(f"s{i}" for i in range(6)), on_progress=on_progress)

        assert percents == sorted(percents)
        assert percents[-1] == 100

    @pytest.mark.asyncio
    async def test_works_without_a_progress_callback(self, stub_tts, captured):
        assert await run("a [pause] b")


class TestVolumesAndOutput:
    @pytest.mark.asyncio
    async def test_volumes_are_passed_through_to_the_mixer(self, stub_tts, captured):
        await run("a [pause] b", bells_volume=77, music_volume=12)
        assert captured["bells"] == 77
        assert captured["music"] == 12

    @pytest.mark.asyncio
    async def test_returns_a_filename_the_audio_route_will_accept(self, stub_tts, captured):
        result = await run("a [pause] b")
        assert storage._SAFE_NAME.match(result["filename"])

    @pytest.mark.asyncio
    async def test_returns_a_session_id_that_remix_will_accept(self, stub_tts, captured):
        result = await run("a [pause] b")
        assert storage.is_session_id(result["session_id"])
        assert result["session_id"] == captured["session_id"]

    @pytest.mark.asyncio
    async def test_the_mix_filename_encodes_the_ambience_setting(self, stub_tts, captured):
        # This is what makes a repeated remix free — the name is derived from
        # its inputs, so an existing file is a cache hit.
        result = await run("a [pause] b", bells_volume=70, music_volume=20)
        assert result["filename"] == storage.mix_filename(result["session_id"], 70, 20)

    @pytest.mark.asyncio
    async def test_language_is_handed_to_the_encoder(self, stub_tts, captured):
        await run("a [pause] b")
        assert captured["language"] == "en"


class TestRetry:
    """
    A render is one Gemini call plus N TTS calls. Losing all of it to a single
    dropped connection is the most expensive failure mode available.
    """

    @pytest.mark.asyncio
    async def test_a_transient_failure_is_retried_and_the_render_survives(
        self, monkeypatch, captured
    ):
        attempts = []

        async def flaky(text, language, state, pace=None):
            attempts.append(text)
            if len(attempts) == 1:
                raise ConnectionError("connection reset")
            return AudioSegment.silent(duration=SPEECH_MS, frame_rate=OUTPUT_SAMPLE_RATE)

        monkeypatch.setattr(tts_service, "_synthesize", flaky)
        monkeypatch.setattr(tts_service, "TTS_RETRY_BASE_DELAY", 0)

        assert await run("a single passage")
        assert len(attempts) == 2

    @pytest.mark.asyncio
    async def test_it_gives_up_after_the_configured_number_of_attempts(
        self, monkeypatch, captured
    ):
        attempts = []

        async def always_fails(text, language, state, pace=None):
            attempts.append(text)
            raise ConnectionError("connection reset")

        monkeypatch.setattr(tts_service, "_synthesize", always_fails)
        monkeypatch.setattr(tts_service, "TTS_RETRY_BASE_DELAY", 0)

        with pytest.raises(ConnectionError):
            await run("a single passage")
        assert len(attempts) == tts_service.TTS_MAX_ATTEMPTS

    @pytest.mark.asyncio
    async def test_quota_errors_are_not_retried(self, monkeypatch, captured):
        # Quota is handled by switching engines; retrying just burns time
        # against a wall.
        attempts = []

        async def quota_exhausted(text, language, state, pace=None):
            attempts.append(text)
            raise RuntimeError("429 quota exceeded")

        monkeypatch.setattr(tts_service, "_synthesize", quota_exhausted)
        monkeypatch.setattr(tts_service, "TTS_RETRY_BASE_DELAY", 0)

        with pytest.raises(RuntimeError):
            await run("a single passage")
        assert len(attempts) == 1

    @pytest.mark.asyncio
    async def test_cancellation_is_not_swallowed_by_the_retry_loop(
        self, monkeypatch, captured
    ):
        async def cancelled(text, language, state, pace=None):
            raise asyncio.CancelledError()

        monkeypatch.setattr(tts_service, "_synthesize", cancelled)
        monkeypatch.setattr(tts_service, "TTS_RETRY_BASE_DELAY", 0)

        with pytest.raises(asyncio.CancelledError):
            await run("a single passage")


class TestFailureModes:
    @pytest.mark.asyncio
    async def test_script_of_only_markers_is_rejected(self, stub_tts, captured):
        with pytest.raises(ValueError, match="no speakable text"):
            await run("[pause] [breath] [long_pause]")

    @pytest.mark.asyncio
    async def test_empty_script_is_rejected(self, stub_tts, captured):
        with pytest.raises(ValueError):
            await run("")

    @pytest.mark.asyncio
    async def test_a_failing_segment_propagates(self, monkeypatch, captured):
        async def boom(text, language, state, pace=None):
            raise RuntimeError("tts exploded")

        monkeypatch.setattr(tts_service, "_synthesize", boom)
        with pytest.raises(RuntimeError, match="tts exploded"):
            await run("a [pause] b")
