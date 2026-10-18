import sys
from unittest.mock import patch

import pytest

from music_classifier import cli
from music_classifier.cli import (
    _artist_folder_key,
    classify_organize_main,
)


def _make_mp3(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def _run_cli(monkeypatch, library, tag, genre="rock"):
    monkeypatch.setattr(cli, "artist_from_audio", lambda f: tag)
    monkeypatch.setattr(
        cli, "get_artist_genres_and_language",
        lambda name: ([genre], "english", True),
    )
    monkeypatch.setattr(cli, "update_artist_tag_inner", lambda d, n: None)
    monkeypatch.setattr(sys, "argv", ["classify-organize", str(library)])
    classify_organize_main()


def _dirs_in(path):
    return sorted(p.name for p in path.iterdir() if p.is_dir())


# ---------------------------------------------------------------------------
# _artist_folder_key
# ---------------------------------------------------------------------------


class TestArtistFolderKey:
    def test_returns_key_ignoring_case(self):
        folders = {"King Gizzard & the Lizard Wizard": "path"}
        key = _artist_folder_key(
            folders, "King Gizzard & The Lizard Wizard")
        assert key == "King Gizzard & the Lizard Wizard"

    def test_returns_none_when_absent(self):
        assert _artist_folder_key({"Radiohead": "path"}, "Pink Floyd") is None

    def test_returns_none_for_empty_mapping(self):
        assert _artist_folder_key({}, "Radiohead") is None


# ---------------------------------------------------------------------------
# classify_organize_main
# ---------------------------------------------------------------------------


class TestClassifyOrganize:
    def test_loose_file_creates_artist_folder(
            self, tmp_path, monkeypatch):
        _make_mp3(tmp_path / "song.mp3")
        _run_cli(monkeypatch, tmp_path, tag="Pink Floyd")
        dest = tmp_path / "rock" / "Pink Floyd" / "song.mp3"
        assert dest.is_file()

    def test_case_variant_tag_reuses_existing_folder(
            self, tmp_path, monkeypatch):
        """Regression: tag case differing from the artist folder name used
        to register the same directory twice (on case-insensitive
        filesystems), then crash with FileNotFoundError on rename."""
        folder = tmp_path / "King Gizzard & the Lizard Wizard"
        folder.mkdir()
        _make_mp3(tmp_path / "song.mp3")
        _run_cli(
            monkeypatch, tmp_path,
            tag="King Gizzard & The Lizard Wizard",
        )
        dest = (tmp_path / "rock"
                / "King Gizzard & the Lizard Wizard" / "song.mp3")
        assert dest.is_file()
        assert _dirs_in(tmp_path) == ["rock"]
        assert _dirs_in(tmp_path / "rock") == [
            "King Gizzard & the Lizard Wizard"]

    def test_case_only_canonical_rename(self, tmp_path, monkeypatch):
        folder = tmp_path / "ACDC"
        _make_mp3(folder / "song.mp3")
        mapping = {name: "acdc" for name in ("ACDC",)}
        monkeypatch.setattr(
            cli, "deduplicate",
            lambda names, threshold=90: (["acdc"], mapping),
        )
        _run_cli(monkeypatch, tmp_path, tag="ACDC")
        dest = tmp_path / "rock" / "acdc" / "song.mp3"
        assert dest.is_file()
        assert _dirs_in(tmp_path) == ["rock"]

    def test_two_folders_same_canonical_merge(
            self, tmp_path, monkeypatch):
        _make_mp3(tmp_path / "Radiohead" / "a.mp3")
        _make_mp3(tmp_path / "Radio head" / "b.mp3")
        _run_cli(monkeypatch, tmp_path, tag="Radiohead")
        # sorted() puts "Radio head" first, so it becomes the canonical
        dest = tmp_path / "rock" / "Radio head"
        assert (dest / "a.mp3").is_file()
        assert (dest / "b.mp3").is_file()
        assert _dirs_in(tmp_path) == ["rock"]

    def test_missing_folder_is_skipped(self, tmp_path, monkeypatch):
        """A folder that disappears after the scan must not crash
        the run."""
        folder = tmp_path / "Some Artist"
        _make_mp3(folder / "song.mp3")

        def dedupe_and_remove(names, threshold=90):
            import shutil
            shutil.rmtree(folder)
            return ["some artist"], {n: "some artist" for n in names}

        monkeypatch.setattr(cli, "deduplicate", dedupe_and_remove)
        _run_cli(monkeypatch, tmp_path, tag="Some Artist")
        assert not (tmp_path / "rock").exists()


# ---------------------------------------------------------------------------
# update_artist_tag_inner
# ---------------------------------------------------------------------------


class TestUpdateArtistTagInner:
    @patch("music_classifier.cli.EasyID3")
    def test_updates_mp3_artist_tag(self, mock_easyid3, tmp_path):
        (tmp_path / "a.mp3").write_bytes(b"")
        cli.update_artist_tag_inner(tmp_path, "New Name")
        mock_easyid3.return_value.__setitem__.assert_called_once_with(
            "artist", "New Name")
        mock_easyid3.return_value.save.assert_called_once()

    @patch("music_classifier.cli.EasyID3")
    def test_skips_mp3_without_id3_header(self, mock_easyid3, tmp_path):
        from mutagen.id3 import ID3NoHeaderError
        (tmp_path / "a.mp3").write_bytes(b"")
        mock_easyid3.side_effect = ID3NoHeaderError
        cli.update_artist_tag_inner(tmp_path, "New Name")
        mock_easyid3.return_value.__setitem__.assert_not_called()

    @patch("mutagen.flac.FLAC")
    def test_updates_flac_artist_tag(self, mock_flac, tmp_path):
        """Regression: FLAC files used to be silently skipped when the
        folder was renamed to its canonical artist name."""
        (tmp_path / "a.flac").write_bytes(b"")
        cli.update_artist_tag_inner(tmp_path, "New Name")
        mock_flac.return_value.__setitem__.assert_called_once_with(
            "ARTIST", ["New Name"])
        mock_flac.return_value.save.assert_called_once()
