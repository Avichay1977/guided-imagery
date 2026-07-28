import numpy as np
import pytest

from audio_mix import (
    BELLS_DB_RANGE,
    PAD_ROOT_HZ,
    SR,
    _bell_pitches,
    _pad_loop,
    _pct_to_gain,
    _snap_to_loop,
    _synth_bell,
    build_ambience,
    select_cues,
)
from config import PAD_LOOP_SECONDS


class TestSelectCues:
    def test_keeps_cues_that_are_far_enough_apart(self):
        assert select_cues([0, 30_000, 60_000], min_spacing_ms=20_000) == [0, 30_000, 60_000]

    def test_thins_clustered_cues_keeping_the_earliest(self):
        assert select_cues([0, 1_000, 2_000, 25_000], min_spacing_ms=20_000) == [0, 25_000]

    def test_sorts_unordered_input(self):
        assert select_cues([60_000, 0, 30_000], min_spacing_ms=20_000) == [0, 30_000, 60_000]

    def test_drops_negative_positions(self):
        assert select_cues([-5_000, 0], min_spacing_ms=1) == [0]

    def test_empty_input(self):
        assert select_cues([]) == []


class TestVolumeMapping:
    def test_zero_maps_to_the_floor_of_the_range(self):
        expected = 10 ** (BELLS_DB_RANGE[0] / 20)
        assert _pct_to_gain(0, BELLS_DB_RANGE) == pytest.approx(expected)

    def test_hundred_maps_to_the_ceiling(self):
        expected = 10 ** (BELLS_DB_RANGE[1] / 20)
        assert _pct_to_gain(100, BELLS_DB_RANGE) == pytest.approx(expected)

    def test_is_monotonic(self):
        gains = [_pct_to_gain(p, BELLS_DB_RANGE) for p in range(0, 101, 10)]
        assert gains == sorted(gains)

    def test_clamps_out_of_range_input(self):
        assert _pct_to_gain(-50, BELLS_DB_RANGE) == _pct_to_gain(0, BELLS_DB_RANGE)
        assert _pct_to_gain(500, BELLS_DB_RANGE) == _pct_to_gain(100, BELLS_DB_RANGE)


class TestSeamlessPadLoop:
    """
    The music bed is one short loop tiled to full length. It only works because
    every partial and LFO completes a whole number of cycles per loop, so the
    wrap point is continuous. These tests pin that property down.
    """

    def test_snapping_produces_whole_cycles_per_loop(self):
        for freq in (130.81, 196.2, 261.63, 392.4):
            snapped = _snap_to_loop(freq, 30.0)
            assert snapped * 30.0 == pytest.approx(round(snapped * 30.0))

    def test_snapping_barely_moves_the_frequency(self):
        assert _snap_to_loop(130.81, 30.0) == pytest.approx(130.81, abs=0.02)

    def test_loop_wraps_without_a_discontinuity(self):
        loop = _pad_loop(PAD_LOOP_SECONDS, PAD_ROOT_HZ)
        wrap_jump = abs(float(loop[0]) - float(loop[-1]))
        largest_internal_step = float(np.max(np.abs(np.diff(loop))))
        # A seam would show up as a jump far larger than any step inside the loop.
        assert wrap_jump <= largest_internal_step * 2

    def test_loop_is_normalized_and_finite(self):
        loop = _pad_loop(PAD_LOOP_SECONDS, PAD_ROOT_HZ)
        assert np.all(np.isfinite(loop))
        assert float(np.max(np.abs(loop))) == pytest.approx(1.0, abs=1e-5)

    def test_loop_is_cached_not_resynthesized(self):
        assert _pad_loop(PAD_LOOP_SECONDS, PAD_ROOT_HZ) is _pad_loop(PAD_LOOP_SECONDS, PAD_ROOT_HZ)


class TestBellSynthesis:
    def test_bell_is_normalized_and_finite(self):
        bell = _synth_bell(523.25, 6.0)
        assert np.all(np.isfinite(bell))
        assert float(np.max(np.abs(bell))) == pytest.approx(1.0, abs=1e-5)

    def test_bell_decays_toward_silence(self):
        bell = _synth_bell(523.25, 6.0)
        head = float(np.max(np.abs(bell[: SR // 2])))
        tail = float(np.max(np.abs(bell[-SR // 2:])))
        assert tail < head * 0.1

    def test_bell_starts_from_silence_so_there_is_no_click(self):
        assert abs(float(_synth_bell(523.25, 6.0)[0])) < 1e-6

    def test_cached_results_are_immutable(self):
        bell = _synth_bell(587.33, 5.0)
        with pytest.raises(ValueError):
            bell[0] = 1.0

    def test_pitches_walk_by_one_scale_step(self):
        from audio_mix import BELL_FREQS

        pitches = _bell_pitches(30, np.random.default_rng(7))
        indices = [BELL_FREQS.index(p) for p in pitches]
        assert all(abs(b - a) <= 1 for a, b in zip(indices, indices[1:]))

    def test_no_pitches_requested(self):
        assert _bell_pitches(0, np.random.default_rng(1)) == []


class TestBuildAmbience:
    def test_output_length_matches_request(self):
        segment = build_ambience(duration_ms=8_000, cue_positions_ms=[1_000], seed=1)
        assert len(segment) == pytest.approx(8_000, abs=60)

    def test_output_uses_the_requested_frame_rate(self):
        segment = build_ambience(duration_ms=4_000, frame_rate=44_100, seed=1)
        assert segment.frame_rate == 44_100

    def test_both_layers_off_yields_silence(self):
        segment = build_ambience(
            duration_ms=4_000, cue_positions_ms=[500], bells_volume=0, music_volume=0, seed=1
        )
        assert segment.max == 0

    def test_bells_only_still_produces_audio(self):
        segment = build_ambience(
            duration_ms=10_000, cue_positions_ms=[1_000], bells_volume=80, music_volume=0, seed=1
        )
        assert segment.max > 0

    def test_music_only_still_produces_audio(self):
        segment = build_ambience(
            duration_ms=10_000, cue_positions_ms=[], bells_volume=0, music_volume=80, seed=1
        )
        assert segment.max > 0

    def test_louder_setting_is_actually_louder(self):
        quiet = build_ambience(duration_ms=10_000, cue_positions_ms=[], music_volume=20, bells_volume=0, seed=1)
        loud = build_ambience(duration_ms=10_000, cue_positions_ms=[], music_volume=90, bells_volume=0, seed=1)
        assert loud.dBFS > quiet.dBFS

    def test_cue_beyond_the_track_is_ignored_not_an_error(self):
        segment = build_ambience(duration_ms=3_000, cue_positions_ms=[999_000], seed=1)
        assert len(segment) == pytest.approx(3_000, abs=60)

    def test_zero_duration_is_handled(self):
        assert len(build_ambience(duration_ms=0)) == 0

    def test_negative_duration_is_handled(self):
        assert len(build_ambience(duration_ms=-100)) == 0

    def test_bed_fades_in_rather_than_starting_abruptly(self):
        segment = build_ambience(duration_ms=20_000, cue_positions_ms=[], music_volume=90, bells_volume=0, seed=1)
        opening = segment[:200]
        middle = segment[10_000:10_200]
        assert opening.dBFS < middle.dBFS

    def test_same_seed_reproduces_the_same_mix(self):
        a = build_ambience(duration_ms=8_000, cue_positions_ms=[1_000, 40_000], seed=42)
        b = build_ambience(duration_ms=8_000, cue_positions_ms=[1_000, 40_000], seed=42)
        assert a.raw_data == b.raw_data
