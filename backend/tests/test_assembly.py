import numpy as np
import pytest
from pydub import AudioSegment

from conftest import HAS_FFMPEG

from config import (
    OUTPUT_CHANNELS,
    OUTPUT_SAMPLE_RATE,
    OUTPUT_SAMPLE_WIDTH,
    VOICE_PEAK_CEILING_DBFS,
    VOICE_TARGET_DBFS,
)
from tts_service import _concat, _mix, _normalize, _normalize_loudness, _render_voice


def tone(duration_ms, amplitude=0.5, frame_rate=OUTPUT_SAMPLE_RATE):
    n = int(frame_rate * duration_ms / 1000)
    samples = (np.full(n, amplitude, dtype=np.float32) * 32767).astype(np.int16)
    return AudioSegment(samples.tobytes(), frame_rate=frame_rate, sample_width=2, channels=1)


class TestNormalize:
    def test_upsamples_to_the_canonical_rate(self):
        assert _normalize(tone(100, frame_rate=24_000)).frame_rate == OUTPUT_SAMPLE_RATE

    def test_downmixes_to_the_canonical_channel_count(self):
        stereo = tone(100).set_channels(2)
        assert _normalize(stereo).channels == OUTPUT_CHANNELS

    def test_converts_sample_width(self):
        assert _normalize(tone(100).set_sample_width(4)).sample_width == OUTPUT_SAMPLE_WIDTH

    def test_already_canonical_input_is_unchanged(self):
        segment = tone(100)
        result = _normalize(segment)
        assert (result.frame_rate, result.channels, result.sample_width) == (
            OUTPUT_SAMPLE_RATE,
            OUTPUT_CHANNELS,
            OUTPUT_SAMPLE_WIDTH,
        )


class TestConcat:
    def test_total_length_is_the_sum_of_the_parts(self):
        parts = [AudioSegment.silent(duration=d, frame_rate=OUTPUT_SAMPLE_RATE) for d in (100, 250, 400)]
        assert len(_concat(parts)) == pytest.approx(750, abs=2)

    def test_empty_input_yields_an_empty_segment(self):
        assert len(_concat([])) == 0

    def test_output_is_in_the_canonical_format(self):
        result = _concat([tone(100), tone(100)])
        assert result.frame_rate == OUTPUT_SAMPLE_RATE
        assert result.channels == OUTPUT_CHANNELS
        assert result.sample_width == OUTPUT_SAMPLE_WIDTH

    def test_order_is_preserved(self):
        loud, quiet = tone(200, 0.9), tone(200, 0.1)
        result = _concat([loud, quiet])
        assert result[:150].dBFS > result[-150:].dBFS

    def test_matches_naive_concatenation_sample_for_sample(self):
        # The fast path must be byte-identical to what `a + b + c` produced,
        # since that is the behaviour it replaced.
        parts = [tone(120, 0.8), AudioSegment.silent(duration=90, frame_rate=OUTPUT_SAMPLE_RATE), tone(150, 0.3)]
        naive = parts[0] + parts[1] + parts[2]
        assert _concat(parts).raw_data == naive.raw_data

    def test_single_part(self):
        assert len(_concat([tone(300)])) == pytest.approx(300, abs=2)


class TestLoudnessNormalization:
    """
    Sessions must land at a consistent level, because the ambience is mixed at a
    fixed dB relative to full scale. A drifting voice level silently changes the
    voice-to-bed balance from one session to the next.
    """

    def test_quiet_input_is_brought_up_to_target(self):
        result = _normalize_loudness(tone(500, 0.02))
        assert result.dBFS == pytest.approx(VOICE_TARGET_DBFS, abs=0.5)

    def test_loud_input_is_brought_down_to_target(self):
        result = _normalize_loudness(tone(500, 0.9))
        assert result.dBFS == pytest.approx(VOICE_TARGET_DBFS, abs=0.5)

    def test_normalization_never_clips(self):
        # A near-full-scale signal cannot be pushed past the ceiling.
        result = _normalize_loudness(tone(500, 0.999))
        assert result.max_dBFS <= VOICE_PEAK_CEILING_DBFS + 0.1

    def test_two_different_inputs_end_up_at_the_same_level(self):
        a = _normalize_loudness(tone(500, 0.05))
        b = _normalize_loudness(tone(500, 0.5))
        assert a.dBFS == pytest.approx(b.dBFS, abs=0.5)

    def test_silence_is_left_alone_rather_than_amplified(self):
        silence = AudioSegment.silent(duration=300, frame_rate=OUTPUT_SAMPLE_RATE)
        assert _normalize_loudness(silence).max == 0


class TestRenderVoice:
    def test_joins_and_levels_the_narration(self):
        voice = _render_voice([tone(400, 0.02), tone(400, 0.02)])
        assert len(voice) == pytest.approx(800, abs=5)
        assert voice.dBFS == pytest.approx(VOICE_TARGET_DBFS, abs=0.5)

    def test_refuses_an_empty_track(self):
        with pytest.raises(ValueError, match="no audio"):
            _render_voice([])


class TestMix:
    def test_ambience_disabled_returns_the_narration_untouched(self):
        voice = tone(2000, 0.4)
        assert _mix(voice, [500], 0, 0) is voice

    def test_mixing_preserves_length(self):
        voice = tone(4000, 0.4)
        assert len(_mix(voice, [500], 60, 40)) == pytest.approx(len(voice), abs=60)

    def test_mixing_changes_the_audio(self):
        voice = tone(4000, 0.4)
        assert _mix(voice, [500], 90, 90).raw_data != voice.raw_data


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not available")
class TestEncodeEndToEnd:
    """The real encode path: render -> mix -> mp3 on disk."""

    def build_parts(self):
        return [
            tone(1500, 0.6),
            AudioSegment.silent(duration=3000, frame_rate=OUTPUT_SAMPLE_RATE),
            tone(1500, 0.6),
        ]

    def test_writes_a_playable_mp3(self, tmp_path):
        from tts_service import _export

        out = tmp_path / "session.mp3"
        _export(_mix(_render_voice(self.build_parts()), [1600], 50, 35), out)

        assert out.stat().st_size > 0
        head = out.read_bytes()[:3]
        assert head == b"ID3" or head[0] == 0xFF  # ID3 tag or a raw MPEG frame

    def test_ambience_actually_changes_the_encoded_output(self, tmp_path):
        from tts_service import _export

        voice = _render_voice(self.build_parts())
        dry, wet = tmp_path / "dry.mp3", tmp_path / "wet.mp3"
        _export(_mix(voice, [1600], 0, 0), dry)
        _export(_mix(voice, [1600], 90, 90), wet)
        assert dry.read_bytes() != wet.read_bytes()
