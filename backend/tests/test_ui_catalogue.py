"""
The backend catalogue and the UI's option lists have to agree.

The frontend cannot read labels from the API — it needs them in Hebrew and
English, so they live in the translation files. That leaves two lists of ids
that could drift: adding a focus area in Python without adding it to the
picker would make it unreachable, and offering one in the picker that the API
rejects would fail validation on submit.

These tests read the actual frontend files, so the drift is caught here rather
than by a user meeting a 422.
"""

import json
import re
from pathlib import Path

import pytest

from config import PACE_PRESETS
from focus_areas import AGE_BANDS, FOCUS_AREAS, NEURO_ADAPTATIONS

FRONTEND = Path(__file__).resolve().parent.parent.parent / "frontend"
SESSION_FORM = FRONTEND / "src" / "components" / "SessionForm.jsx"
LOCALES = FRONTEND / "public" / "locales"

pytestmark = pytest.mark.skipif(
    not SESSION_FORM.is_file(), reason="frontend sources not present"
)


def js_list(name: str) -> list[str]:
    """Pull a top-level `const NAME = [...]` string array out of the JSX."""
    source = SESSION_FORM.read_text(encoding="utf-8")
    match = re.search(rf"const {name} = \[(.*?)\]", source, re.S)
    assert match, f"{name} not found in SessionForm.jsx"
    return re.findall(r"'([^']+)'", match.group(1))


def form_strings(lang: str) -> dict:
    return json.loads((LOCALES / lang / "translation.json").read_text(encoding="utf-8"))["form"]


class TestOptionIdsMatchTheBackend:
    def test_focus_areas_match(self):
        assert sorted(js_list("FOCUS_OPTIONS")) == sorted(FOCUS_AREAS)

    def test_age_bands_match(self):
        assert sorted(js_list("AGE_OPTIONS")) == sorted(AGE_BANDS)

    def test_neuroprofiles_match(self):
        assert sorted(js_list("NEURO_OPTIONS")) == sorted(NEURO_ADAPTATIONS)

    def test_paces_match(self):
        assert sorted(js_list("PACE_OPTIONS")) == sorted(PACE_PRESETS)


class TestEveryOptionHasALabel:
    @pytest.mark.parametrize("lang", ["en", "he"])
    def test_focus_areas_are_labelled(self, lang):
        strings = form_strings(lang)
        missing = [f for f in FOCUS_AREAS if f"focus_{f}" not in strings]
        assert not missing, f"untranslated focus areas in {lang}: {missing}"

    @pytest.mark.parametrize("lang", ["en", "he"])
    def test_age_bands_are_labelled(self, lang):
        strings = form_strings(lang)
        missing = [a for a in AGE_BANDS if f"age_{a}" not in strings]
        assert not missing, f"untranslated age bands in {lang}: {missing}"

    @pytest.mark.parametrize("lang", ["en", "he"])
    def test_neuroprofiles_are_labelled(self, lang):
        strings = form_strings(lang)
        missing = [n for n in NEURO_ADAPTATIONS if f"neuro_{n}" not in strings]
        assert not missing, f"untranslated neuroprofiles in {lang}: {missing}"

    @pytest.mark.parametrize("lang", ["en", "he"])
    def test_paces_are_labelled(self, lang):
        strings = form_strings(lang)
        missing = [p for p in PACE_PRESETS if f"pace_{p}" not in strings]
        assert not missing, f"untranslated paces in {lang}: {missing}"

    def test_the_two_locales_carry_the_same_keys(self):
        assert set(form_strings("en")) == set(form_strings("he"))

    @pytest.mark.parametrize("lang", ["en", "he"])
    def test_no_label_is_left_empty(self, lang):
        blank = [k for k, v in form_strings(lang).items() if not str(v).strip()]
        assert not blank, f"empty labels in {lang}: {blank}"
