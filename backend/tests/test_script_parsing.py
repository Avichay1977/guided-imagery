import pytest

from tts_service import _detect_language, split_script_on_pauses


class TestSplitScriptOnPauses:
    def test_splits_text_and_pauses_in_order(self):
        segments = split_script_on_pauses("Breathe in [pause] and out [breath] gently")
        assert [s["type"] for s in segments] == ["text", "pause", "text", "pause", "text"]
        assert segments[0]["content"] == "Breathe in"
        assert segments[2]["content"] == "and out"
        assert segments[4]["content"] == "gently"

    def test_keeps_marker_so_callers_can_tell_pause_kinds_apart(self):
        segments = split_script_on_pauses("a [pause] b [breath] c [long_pause] d")
        markers = [s["marker"] for s in segments if s["type"] == "pause"]
        assert markers == ["[pause]", "[breath]", "[long_pause]"]

    def test_maps_each_marker_to_its_duration(self):
        segments = split_script_on_pauses("a [short_pause] b [long_pause] c")
        durations = [s["duration_ms"] for s in segments if s["type"] == "pause"]
        assert durations == [1500, 5000]

    def test_drops_empty_text_between_adjacent_markers(self):
        segments = split_script_on_pauses("a [pause] [pause] b")
        assert [s["type"] for s in segments] == ["text", "pause", "pause", "text"]

    def test_script_without_markers_is_one_segment(self):
        segments = split_script_on_pauses("just words")
        assert segments == [{"type": "text", "content": "just words"}]

    def test_empty_script_yields_nothing(self):
        assert split_script_on_pauses("") == []

    def test_leading_marker_produces_no_empty_lead_segment(self):
        segments = split_script_on_pauses("[pause] then speech")
        assert segments[0]["type"] == "pause"
        assert len(segments) == 2


class TestDetectLanguage:
    def test_detects_hebrew(self):
        assert _detect_language("שלום וברוך הבא למדיטציה הזאת של רגיעה עמוקה") == "he"

    def test_detects_english(self):
        assert _detect_language("Welcome to this deep relaxation meditation") == "en"

    def test_a_few_stray_hebrew_words_do_not_flip_an_english_script(self):
        assert _detect_language("Welcome, this is calm " + "word " * 40) == "en"


class TestExtractVideoId:
    @pytest.mark.parametrize("url", [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "dQw4w9WgXcQ",
    ])
    def test_accepts_known_url_shapes(self, url):
        from main import _extract_video_id
        assert _extract_video_id(url) == "dQw4w9WgXcQ"

    @pytest.mark.parametrize("url", ["https://example.com", "not a url", "v=tooshort"])
    def test_rejects_anything_else(self, url):
        from main import _extract_video_id
        with pytest.raises(ValueError):
            _extract_video_id(url)
