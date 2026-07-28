"""
Tests for who the session is for and how fast it is delivered.

The prompt is the product here — the audio pipeline only carries whatever the
model was told to write. So these assert that the right guidance actually
reaches the prompt, and in particular that the neurodivergent adaptations
override the generic relaxation advice rather than sitting next to it.
"""

import re

import pytest

from config import DEFAULT_PACE, PACE_PRESETS, pace_preset, pause_durations_for
from focus_areas import (
    AGE_BANDS,
    FOCUS_AREAS,
    NEURO_ADAPTATIONS,
    resolve_age,
)
from prompt_template import build_meditation_prompt
from tts_service import split_script_on_pauses


def prompt(**overrides):
    args = {
        "topic": "settling before sleep",
        "duration_minutes": 10,
        "language": "en",
    }
    args.update(overrides)
    return build_meditation_prompt(**args)


def words_in(**overrides) -> int:
    """The word target the prompt actually asks the model for."""
    match = re.search(r"~(\d+) words", prompt(**overrides))
    assert match, "prompt no longer states a word target"
    return int(match.group(1))


class TestFocusAreas:
    @pytest.mark.parametrize("focus", sorted(FOCUS_AREAS))
    def test_every_focus_area_reaches_the_prompt(self, focus):
        assert FOCUS_AREAS[focus]["guidance"].strip()[:40] in prompt(focus=focus)

    @pytest.mark.parametrize("focus", sorted(FOCUS_AREAS))
    def test_every_focus_area_works_in_hypnosis_mode_too(self, focus):
        assert FOCUS_AREAS[focus]["guidance"].strip()[:40] in prompt(focus=focus, mode="hypnosis")

    def test_an_unknown_focus_falls_back_instead_of_raising(self):
        assert "GENERAL RELAXATION" in prompt(focus="not-a-real-focus")

    def test_hair_pulling_guidance_forbids_shaming(self):
        text = prompt(focus="bfrb")
        assert "Never shame" in text
        assert "urge" in text.lower()

    def test_hair_pulling_guidance_does_not_claim_to_replace_treatment(self):
        assert "does not replace it" in prompt(focus="bfrb")

    def test_sleep_sessions_are_told_not_to_wake_the_listener(self):
        assert "no return phase" in prompt(focus="sleep").lower()

    def test_panic_guidance_avoids_dissolving_imagery(self):
        # Depersonalisation-flavoured imagery is the wrong thing to hand someone
        # rehearsing for panic.
        assert "losing control" in prompt(focus="panic")

    def test_sensory_overload_reduces_rather_than_layers_sensory_detail(self):
        assert "Reduce, do not add" in prompt(focus="sensory")

    def test_the_free_text_topic_still_reaches_the_prompt(self):
        assert "when my sister slams the door" in prompt(
            topic="when my sister slams the door", focus="anger"
        )


class TestNeuroAdaptations:
    def test_no_profile_adds_nothing(self):
        assert "ADAPTATION —" not in prompt(neuroprofile="none")

    @pytest.mark.parametrize("profile", ["autism", "adhd", "audhd"])
    def test_each_profile_adds_its_block(self, profile):
        assert "ADAPTATION —" in prompt(neuroprofile=profile)

    @pytest.mark.parametrize("profile", ["autism", "adhd", "audhd"])
    def test_adaptations_come_after_the_generic_style_rules(self, profile):
        # They contradict the generic advice on purpose, so they have to be able
        # to override it — which in a prompt means coming later.
        text = prompt(neuroprofile=profile)
        assert text.index("LANGUAGE STYLE") < text.index("ADAPTATION —")

    @pytest.mark.parametrize("profile", ["autism", "adhd", "audhd"])
    def test_no_profile_demands_closed_eyes_or_stillness(self, profile):
        text = prompt(neuroprofile=profile)
        assert "Never require closed eyes" in text
        assert "Never require stillness" in text

    @pytest.mark.parametrize("profile", ["autism", "adhd", "audhd"])
    def test_no_profile_asks_to_empty_the_mind(self, profile):
        assert 'Never say "empty your mind"' in prompt(neuroprofile=profile)

    @pytest.mark.parametrize("profile", ["autism", "audhd"])
    def test_autistic_profiles_do_not_assume_mental_imagery(self, profile):
        assert "Do not assume mental imagery" in prompt(neuroprofile=profile)

    @pytest.mark.parametrize("profile", ["autism", "audhd"])
    def test_autistic_profiles_do_not_rely_on_interoception(self, profile):
        # Hunting for a heartbeat you cannot detect is stressful, not calming.
        assert "interoception" in prompt(neuroprofile=profile).lower()

    @pytest.mark.parametrize("profile", ["autism", "audhd"])
    def test_autistic_profiles_ban_dissolving_and_melting_imagery(self, profile):
        text = prompt(neuroprofile=profile)
        assert "melting" in text or "melt" in text
        assert "literal" in text.lower()

    @pytest.mark.parametrize("profile", ["adhd", "audhd"])
    def test_attention_profiles_limit_long_silences(self, profile):
        text = prompt(neuroprofile=profile)
        assert "[long_pause]" in text
        assert "twice" in text

    @pytest.mark.parametrize("profile", ["adhd", "audhd"])
    def test_attention_profiles_normalise_a_wandering_mind(self, profile):
        assert "wandering" in prompt(neuroprofile=profile).lower()

    def test_audhd_holds_both_sides_of_the_tension(self):
        # Predictable structure and moving content, rather than a compromise
        # that serves neither.
        text = prompt(neuroprofile="audhd")
        assert "opposite directions" in text
        assert "Predictable frame, moving content" in text

    def test_autistic_profiles_get_an_opening_contract(self):
        assert "OPENING CONTRACT" in prompt(neuroprofile="audhd")

    def test_neurotypical_sessions_get_no_opening_contract(self):
        assert "OPENING CONTRACT" not in prompt(neuroprofile="none")


class TestAgeBands:
    @pytest.mark.parametrize("band", [b for b in AGE_BANDS if AGE_BANDS[b]["guidance"]])
    def test_each_band_reaches_the_prompt(self, band):
        assert "TARGET AUDIENCE" in prompt(age_group=band)

    def test_adults_get_no_age_block(self):
        assert "TARGET AUDIENCE" not in prompt(age_group="adult")

    @pytest.mark.parametrize("old,new", [
        ("children", "child"), ("teens", "teen"), ("adults", "adult"),
    ])
    def test_the_original_coarse_values_still_resolve(self, old, new):
        assert resolve_age(old) == new

    def test_an_unknown_age_falls_back_to_adult(self):
        assert resolve_age("wizard") == "adult"

    def test_teen_guidance_forbids_talking_down(self):
        text = prompt(age_group="teen")
        assert "Condescension" in text or "condescension" in text

    def test_young_children_get_a_story_not_a_meditation(self):
        assert "Not a meditation" in prompt(age_group="young_child")


class TestPace:
    def test_default_pace_matches_the_original_delivery(self):
        # The previous hardcoded rates were -35% Hebrew and -30% English.
        rate = pace_preset(DEFAULT_PACE)["rate"]
        assert rate["he"] == "-35%"
        assert rate["en"] == "-30%"

    @pytest.mark.parametrize("pace", sorted(PACE_PRESETS))
    def test_every_pace_has_a_complete_preset(self, pace):
        preset = PACE_PRESETS[pace]
        assert set(preset["rate"]) == {"he", "en"}
        assert preset["words_per_minute"] > 0
        assert preset["pause_scale"] > 0

    def test_faster_paces_speak_more_words_per_minute(self):
        wpm = [PACE_PRESETS[p]["words_per_minute"] for p in ["very_slow", "slow", "natural", "brisk"]]
        assert wpm == sorted(wpm)

    def test_faster_paces_shorten_the_silences(self):
        scales = [PACE_PRESETS[p]["pause_scale"] for p in ["very_slow", "slow", "natural", "brisk"]]
        assert scales == sorted(scales, reverse=True)

    def test_pause_durations_scale_with_pace(self):
        slow = pause_durations_for("very_slow")["[long_pause]"]
        brisk = pause_durations_for("brisk")["[long_pause]"]
        assert brisk < slow

    def test_pauses_never_collapse_to_nothing(self):
        for pace in PACE_PRESETS:
            assert min(pause_durations_for(pace).values()) >= 400

    def test_an_unknown_pace_falls_back_to_the_default(self):
        assert pause_durations_for("hyperspeed") == pause_durations_for(DEFAULT_PACE)

    def test_the_script_splitter_honours_pace(self):
        script = "a [long_pause] b"
        slow = split_script_on_pauses(script, "very_slow")[1]["duration_ms"]
        brisk = split_script_on_pauses(script, "brisk")[1]["duration_ms"]
        assert brisk < slow

    def test_a_brisk_session_asks_for_more_words_than_a_slow_one(self):
        # Otherwise a faster voice would simply finish early.
        assert words_in(pace="brisk") > words_in(pace="slow") > words_in(pace="very_slow")

    @pytest.mark.parametrize("pace", sorted(PACE_PRESETS))
    def test_the_word_target_leaves_room_for_the_silences(self, pace):
        """
        Speech time plus silence time has to come out at the requested length.

        Asking for a full duration's worth of speech and then adding the pauses
        on top overshoots by about a fifth, which is what this guards against.
        """
        minutes = 10
        preset = PACE_PRESETS[pace]
        speech_minutes = words_in(duration_minutes=minutes, pace=pace) / preset["words_per_minute"]
        assert speech_minutes < minutes, "no room left for any silence at all"
        # The remainder is the silence budget; it should be a sane slice, not
        # most of the session and not a rounding error.
        silence_share = 1 - speech_minutes / minutes
        assert 0.1 < silence_share < 0.4

    def test_the_target_scales_with_duration(self):
        assert words_in(duration_minutes=20) == pytest.approx(
            2 * words_in(duration_minutes=10), rel=0.02
        )

    def test_hypnosis_is_written_sparser_than_imagery(self):
        assert words_in(mode="hypnosis") < words_in(mode="imagery")

    def test_moving_paces_tell_the_model_to_keep_talking(self):
        assert "DELIVERY PACE — MOVING" in prompt(pace="brisk")

    def test_very_slow_tells_the_model_to_use_silence(self):
        assert "DELIVERY PACE — VERY SLOW" in prompt(pace="very_slow")


class TestCombination:
    def test_the_case_this_was_built_for(self):
        """A 14-year-old with AuDHD, working on hair pulling, at a moving pace."""
        text = prompt(
            topic="when I notice my hand going to my hair while doing homework",
            duration_minutes=8,
            language="he",
            age_group="teen",
            focus="bfrb",
            neuroprofile="audhd",
            pace="natural",
        )
        assert "BODY-FOCUSED REPETITIVE BEHAVIOUR" in text     # the clinical target
        assert "AUTISTIC + ADHD" in text                        # the adaptation
        assert "TARGET AUDIENCE: Teenagers" in text             # the register
        assert "DELIVERY PACE — MOVING" in text                 # the density
        assert "OPENING CONTRACT" in text                       # predictability
        assert "Never shame" in text                            # tone
        assert "going to my hair" in text                       # their own words
        assert "Hebrew" in text                                 # the language
