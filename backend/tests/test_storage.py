import time

import pytest

import storage


@pytest.fixture
def audio_root(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "AUDIO_ROOT", tmp_path)
    return tmp_path


def write(path, size=1024, age_hours=0.0):
    path.write_bytes(b"\0" * size)
    if age_hours:
        stamp = time.time() - age_hours * 3600
        import os
        os.utime(path, (stamp, stamp))
    return path


class TestResolve:
    def test_resolves_a_real_artifact(self, audio_root):
        write(audio_root / "meditation_abc123.mp3")
        assert storage.resolve("meditation_abc123.mp3") is not None

    def test_missing_file_is_none(self, audio_root):
        assert storage.resolve("meditation_nope.mp3") is None

    @pytest.mark.parametrize("name", [
        "../config.py",
        "../../etc/passwd",
        "..%2Fconfig.py",
        "sub/dir/file.mp3",
        "/etc/passwd",
        "meditation_abc.exe",
        "meditation abc.mp3",
        "",
    ])
    def test_rejects_anything_that_is_not_a_plain_artifact_name(self, audio_root, name):
        assert storage.resolve(name) is None

    def test_symlink_escaping_the_root_is_rejected(self, audio_root, tmp_path):
        outside = tmp_path.parent / "outside.mp3"
        outside.write_bytes(b"\0")
        link = audio_root / "meditation_link.mp3"
        try:
            link.symlink_to(outside)
        except OSError:
            pytest.skip("symlinks unavailable")
        assert storage.resolve("meditation_link.mp3") is None


class TestPrune:
    def test_removes_files_past_the_ttl(self, audio_root, monkeypatch):
        monkeypatch.setattr(storage, "AUDIO_TTL_HOURS", 6)
        monkeypatch.setattr(storage, "AUDIO_MAX_MB", 1024)
        old = write(audio_root / "old.mp3", age_hours=10)
        fresh = write(audio_root / "fresh.mp3", age_hours=1)

        result = storage.prune()

        assert result["expired"] == 1
        assert not old.exists()
        assert fresh.exists()

    def test_enforces_the_size_budget_oldest_first(self, audio_root, monkeypatch):
        monkeypatch.setattr(storage, "AUDIO_TTL_HOURS", 999)
        monkeypatch.setattr(storage, "AUDIO_MAX_MB", 1)
        oldest = write(audio_root / "a.mp3", size=600 * 1024, age_hours=3)
        newest = write(audio_root / "b.mp3", size=600 * 1024, age_hours=1)

        result = storage.prune()

        assert result["over_budget"] == 1
        assert not oldest.exists()
        assert newest.exists()

    def test_gives_up_mixes_before_narrations(self, audio_root, monkeypatch):
        # A mix rebuilds from its narration in seconds; a narration only rebuilds
        # by paying for the script and the whole TTS render again.
        monkeypatch.setattr(storage, "AUDIO_TTL_HOURS", 999)
        monkeypatch.setattr(storage, "AUDIO_MAX_MB", 1)
        voice = write(audio_root / "voice_abcdef123456.mp3", size=600 * 1024, age_hours=5)
        mix = write(audio_root / "meditation_abcdef123456b50m35.mp3", size=600 * 1024, age_hours=1)

        storage.prune()

        assert voice.exists(), "the irreplaceable artifact should survive"
        assert not mix.exists(), "the rebuildable one should go first"

    def test_narrations_are_dropped_only_when_mixes_are_not_enough(self, audio_root, monkeypatch):
        monkeypatch.setattr(storage, "AUDIO_TTL_HOURS", 999)
        monkeypatch.setattr(storage, "AUDIO_MAX_MB", 1)
        old_voice = write(audio_root / "voice_aaaaaaaaaaaa.mp3", size=700 * 1024, age_hours=9)
        new_voice = write(audio_root / "voice_bbbbbbbbbbbb.mp3", size=700 * 1024, age_hours=1)

        storage.prune()

        assert not old_voice.exists()
        assert new_voice.exists()

    def test_leaves_everything_alone_when_within_limits(self, audio_root, monkeypatch):
        monkeypatch.setattr(storage, "AUDIO_TTL_HOURS", 999)
        monkeypatch.setattr(storage, "AUDIO_MAX_MB", 1024)
        kept = write(audio_root / "a.mp3", age_hours=1)

        assert storage.prune() == {"expired": 0, "over_budget": 0, "freed_bytes": 0}
        assert kept.exists()

    def test_empty_directory(self, audio_root):
        assert storage.prune()["expired"] == 0


class TestNewFilename:
    def test_names_are_unique(self):
        assert len({storage.new_filename() for _ in range(50)}) == 50

    def test_generated_names_pass_the_resolver_pattern(self, audio_root):
        name = storage.new_filename()
        write(audio_root / name)
        assert storage.resolve(name) is not None
