from unittest.mock import patch, MagicMock

import struct

import pytest
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TBPM

from music_classifier.bpm_organizer import bpm_folder
from music_classifier.csv_store import load_processed_set, append_entry
from music_classifier.audio import has_bpm, save_bpm_to_mp3, sanitize, extract_bpm


def _make_mp3(path, bpm=None):
    """Create a minimal valid MP3 file with ID3 tags."""
    # Minimal MPEG1 Layer3 128kbps 44100Hz frame (417 bytes)
    header = b"\xff\xfb\x90\x00"
    frame = header + b"\x00" * 413
    with open(path, "wb") as f:
        f.write(frame * 3)  # a few frames so mutagen reads it
    audio = MP3(path, ID3=ID3)
    audio.add_tags()
    if bpm is not None:
        audio.tags.add(TBPM(text=str(bpm)))
    audio.save()
    return audio


# ---------------------------------------------------------------------------
# bpm_folder
# ---------------------------------------------------------------------------


class TestBpmFolder:
    def test_lower_bound(self):
        assert bpm_folder(60) == "60s"

    def test_upper_bound_of_decade(self):
        assert bpm_folder(69) == "60s"

    def test_next_decade(self):
        assert bpm_folder(70) == "70s"

    def test_100s(self):
        assert bpm_folder(105) == "100s"

    def test_200s(self):
        assert bpm_folder(200) == "200s"

    def test_250s(self):
        assert bpm_folder(259) == "250s"

    def test_high_bpm(self):
        assert bpm_folder(323) == "320s"

    def test_zero(self):
        assert bpm_folder(0) == "0s"

    def test_single_digit(self):
        assert bpm_folder(9) == "0s"


# ---------------------------------------------------------------------------
# csv_store
# ---------------------------------------------------------------------------


class TestCsvStore:
    def test_load_from_nonexistent_file(self):
        assert load_processed_set("/nonexistent/path.csv") == set()

    def test_load_from_empty_path(self):
        assert load_processed_set("") == set()

    def test_append_and_load(self, tmp_path):
        csv_path = str(tmp_path / "test.csv")
        append_entry(
            artist="Artist",
            title="Title",
            bpm="120",
            duration=180,
            filename="(120) Artist - Title.mp3",
            id="abc123",
            csv_path=csv_path,
        )
        result = load_processed_set(csv_path)
        assert "abc123" in result

    def test_append_multiple_entries(self, tmp_path):
        csv_path = str(tmp_path / "test.csv")
        for i in range(3):
            append_entry(
                artist=f"Artist {i}",
                title=f"Title {i}",
                bpm=str(100 + i),
                duration=180,
                filename=f"({100 + i}) Artist {i} - Title {i}.mp3",
                id=f"id_{i}",
                csv_path=csv_path,
            )
        result = load_processed_set(csv_path)
        assert result == {"id_0", "id_1", "id_2"}

    def test_load_returns_set_of_ids(self, tmp_path):
        csv_path = str(tmp_path / "test.csv")
        append_entry(
            artist="A", title="T", bpm="100", duration=60,
            filename="f.mp3", id="x1", csv_path=csv_path,
        )
        append_entry(
            artist="B", title="U", bpm="110", duration=90,
            filename="g.mp3", id="x2", csv_path=csv_path,
        )
        result = load_processed_set(csv_path)
        assert isinstance(result, set)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# has_bpm
# ---------------------------------------------------------------------------


class TestHasBpm:
    def test_returns_false_for_nonexistent_file(self):
        assert has_bpm("/nonexistent/file.mp3") is False

    def test_returns_true_for_filename_with_bpm_tag(self, tmp_path):
        f = tmp_path / "song [BPM].mp3"
        _make_mp3(str(f))
        assert has_bpm(str(f)) is True

    def test_returns_true_for_filename_bpm_lowercase(self, tmp_path):
        f = tmp_path / "song [bpm].mp3"
        _make_mp3(str(f))
        assert has_bpm(str(f)) is True

    def test_returns_true_when_tbpm_tag_present(self, tmp_path):
        mp3_path = str(tmp_path / "song.mp3")
        _make_mp3(mp3_path, bpm=120)
        assert has_bpm(mp3_path) is True

    def test_returns_false_when_no_tbpm_and_no_filename_match(self, tmp_path):
        mp3_path = str(tmp_path / "song.mp3")
        _make_mp3(mp3_path)
        assert has_bpm(mp3_path) is False

    def test_filename_bpm_overrides_empty_tag(self, tmp_path):
        mp3_path = str(tmp_path / "track [BPM].mp3")
        _make_mp3(mp3_path)
        assert has_bpm(mp3_path) is True


# ---------------------------------------------------------------------------
# save_bpm_to_mp3
# ---------------------------------------------------------------------------


class TestSaveBpmToMp3:
    def test_saves_bpm_tag(self, tmp_path):
        mp3_path = str(tmp_path / "test.mp3")
        _make_mp3(mp3_path)
        save_bpm_to_mp3(mp3_path, 140)
        reloaded = MP3(mp3_path, ID3=ID3)
        assert reloaded.get("TBPM", [""])[0] == "140"

    def test_saves_string_bpm(self, tmp_path):
        mp3_path = str(tmp_path / "test.mp3")
        _make_mp3(mp3_path)
        save_bpm_to_mp3(mp3_path, "120")
        reloaded = MP3(mp3_path, ID3=ID3)
        assert reloaded.get("TBPM", [""])[0] == "120"


# ---------------------------------------------------------------------------
# sanitize
# ---------------------------------------------------------------------------


class TestSanitize:
    def test_removes_forbidden_chars(self):
        result = sanitize('a/b\\c:d<e>f"g|h?i*j')
        for char in r'<>:"/\|?*':
            assert char not in result

    def test_capitalizes_words(self):
        assert sanitize("hello world") == "Hello World"

    def test_collapses_whitespace(self):
        assert sanitize("  many   spaces  ") == "Many Spaces"

    def test_preserves_normal_text(self):
        assert sanitize("Count Basie") == "Count Basie"


# ---------------------------------------------------------------------------
# extract_bpm
# ---------------------------------------------------------------------------


class TestExtractBpm:
    def test_extracts_bpm_from_filename(self):
        assert extract_bpm("(120) Artist - Title.mp3") == 120

    def test_returns_none_when_no_bpm_prefix(self):
        assert extract_bpm("Artist - Title.mp3") is None

    def test_extracts_large_bpm(self):
        assert extract_bpm("(250) Song.mp3") == 250

    def test_extracts_single_digit_bpm(self):
        assert extract_bpm("(5) Slow.mp3") == 5

    def test_returns_none_for_empty_string(self):
        assert extract_bpm("") is None


# ---------------------------------------------------------------------------
# measure_bpm_ui
# ---------------------------------------------------------------------------


class TestMeasureBpmUi:
    def _make_mp3_for_ui(self, tmp_path):
        path = str(tmp_path / "test.mp3")
        _make_mp3(path, bpm=120)
        return path

    def _run_ui_with_events(self, mp3_path, events, time_values):
        import music_classifier.bpm_ui as ui
        import pygame

        call_count = [0]

        def fake_get_events():
            if call_count[0] < len(events):
                e = events[call_count[0]]
                call_count[0] += 1
                return [e]
            return [pygame.event.Event(pygame.QUIT)]

        mock_screen = MagicMock()
        mock_font = MagicMock()
        mock_label = MagicMock()
        mock_label.get_width.return_value = 100
        mock_font.render.return_value = mock_label

        with (
            patch.object(ui, "pygame") as mock_pg,
            patch("time.time", side_effect=time_values),
        ):
            mock_pg.init.return_value = None
            mock_pg.mixer.init.return_value = None
            mock_pg.display.set_mode.return_value = mock_screen
            mock_pg.display.set_caption.return_value = None
            mock_pg.display.flip.return_value = None
            mock_pg.time.Clock.return_value.tick.return_value = None
            mock_pg.font.SysFont.return_value = mock_font
            mock_pg.event.get.side_effect = fake_get_events
            mock_pg.K_SPACE = pygame.K_SPACE
            mock_pg.K_RETURN = pygame.K_RETURN
            mock_pg.K_ESCAPE = pygame.K_ESCAPE
            mock_pg.QUIT = pygame.QUIT
            mock_pg.KEYDOWN = pygame.KEYDOWN
            mock_pg.MOUSEBUTTONDOWN = pygame.MOUSEBUTTONDOWN
            mock_pg.Rect = pygame.Rect
            mock_pg.draw.rect.return_value = None
            mock_pg.mouse.get_pos.return_value = (0, 0)

            return ui.measure_bpm_ui(mp3_path)

    def test_returns_bpm_on_enter(self, tmp_path):
        mp3_path = self._make_mp3_for_ui(tmp_path)
        import pygame

        events = [
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN),
        ]
        bpm, running = self._run_ui_with_events(mp3_path, events, [0, 0.5, 1.0, 1.5])
        assert bpm is not None
        assert isinstance(bpm, int)

    def test_returns_none_on_escape(self, tmp_path):
        mp3_path = self._make_mp3_for_ui(tmp_path)
        import pygame

        events = [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)]
        bpm, running = self._run_ui_with_events(mp3_path, events, [0, 0.5])
        assert bpm is None
        assert running is False

    def test_returns_none_on_quit_event(self, tmp_path):
        mp3_path = self._make_mp3_for_ui(tmp_path)
        import pygame

        events = [pygame.event.Event(pygame.QUIT)]
        bpm, running = self._run_ui_with_events(mp3_path, events, [0])
        assert bpm is None
        assert running is False

    def test_skip_button_returns_none_running_true(self, tmp_path):
        mp3_path = self._make_mp3_for_ui(tmp_path)
        import pygame

        # Skip button is 4th: x = btn_start_x + 3*(100+20) + 50
        btn_start_x = (800 - (100 * 4 + 20 * 3)) // 2
        skip_x = btn_start_x + 3 * 120 + 50
        events = [pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(skip_x, 320))]
        bpm, running = self._run_ui_with_events(mp3_path, events, [0])
        assert bpm is None
        assert running is True
