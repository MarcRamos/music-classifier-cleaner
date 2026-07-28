import os

import pytest

from music_classifier.youtube import _strip_na_prefix


class TestStripNaPrefix:
    def test_renames_na_prefixed_file(self, tmp_path):
        (tmp_path / "NA - Song.mp3").touch()
        _strip_na_prefix(str(tmp_path))
        assert (tmp_path / "Song.mp3").exists()
        assert not (tmp_path / "NA - Song.mp3").exists()

    def test_ignores_regular_file(self, tmp_path):
        (tmp_path / "Artist - Song.mp3").touch()
        _strip_na_prefix(str(tmp_path))
        assert (tmp_path / "Artist - Song.mp3").exists()

    def test_ignores_non_mp3(self, tmp_path):
        (tmp_path / "NA - Song.flac").touch()
        _strip_na_prefix(str(tmp_path))
        assert (tmp_path / "NA - Song.flac").exists()

    def test_no_crash_on_empty_dir(self, tmp_path):
        _strip_na_prefix(str(tmp_path))
