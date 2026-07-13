from unittest.mock import MagicMock, patch

import pytest

from music_classifier.utils import (
    JUNK,
    GENRE_MAP,
    LANGUAGE_MAP,
    FILTERED_TAGS,
    _normalize_for_comparison,
    normalize_artist,
    get_artist_genres_and_language,
    _lastfm_get_top_tags,
    classify,
    deduplicate,
    _read_existing_tags,
    _file_already_tagged,
    tag_audio_file,
    artist_from_audio,
)

# ---------------------------------------------------------------------------
# normalize_artist
# ---------------------------------------------------------------------------


class TestNormalizeArtist:
    def test_lowercases_and_strips(self):
        assert normalize_artist("  The Beatles  ") == "the beatles"

    def test_removes_mp3_extension(self):
        assert normalize_artist("Radiohead.mp3") == "radiohead"

    def test_removes_wav_extension(self):
        assert normalize_artist("Miles Davis.wav") == "miles davis"

    def test_removes_flac_extension(self):
        assert normalize_artist("Nirvana.flac") == "nirvana"

    def test_removes_featuring(self):
        assert normalize_artist("Jay Z feat Linkin Park") == "jay z"

    def test_removes_feat(self):
        assert normalize_artist("Mark Ronson feat Bruno Mars") == "mark ronson"

    def test_removes_ft(self):
        assert normalize_artist("DJ Khaled ft Drake") == "dj khaled"

    def test_removes_track_after_dash(self):
        assert normalize_artist("Queen - Bohemian Rhapsody") == "queen"

    def test_removes_non_alphanumeric_except_ampersand_and_apostrophe(self):
        assert normalize_artist("AC/DC (live)") == "ac dc live"

    def test_collapses_whitespace(self):
        assert normalize_artist("  too    many   spaces  ") == "too many spaces"

    def test_preserves_ampersand(self):
        assert normalize_artist("Simon & Garfunkel") == "simon & garfunkel"

    def test_preserves_apostrophe(self):
        assert normalize_artist("O'Connor") == "o'connor"

    def test_returns_none_for_junk(self):
        assert normalize_artist("MusicBee_Library_DB") is None

    def test_returns_none_for_junk_after_cleaning(self):
        assert normalize_artist("  soundtrack  ") is None

    def test_all_junk_values(self):
        for junk in JUNK:
            assert normalize_artist(junk) is None, f"{junk!r} should be None"

    def test_artist_with_dash_no_track(self):
        assert normalize_artist("Pink Floyd") == "pink floyd"

    def test_artist_with_only_special_chars(self):
        assert normalize_artist("!!!") is None


# ---------------------------------------------------------------------------
# _lastfm_get_top_tags
# ---------------------------------------------------------------------------


class TestLastfmGetTopTags:
    @patch.dict("os.environ", {"LASTFM_API_KEY": "testkey"})
    @patch("music_classifier.utils.requests.get")
    def test_returns_tags_when_api_responds(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "toptags": {"tag": [{"name": "rock", "count": 100}, {"name": "indie", "count": 50}]}
        }
        mock_get.return_value = mock_resp
        assert _lastfm_get_top_tags("Radiohead") == ["rock", "indie"]

    @patch.dict("os.environ", {"LASTFM_API_KEY": "testkey"})
    @patch("music_classifier.utils.requests.get")
    def test_returns_none_when_no_tags(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"toptags": {"tag": []}}
        mock_get.return_value = mock_resp
        assert _lastfm_get_top_tags("Nobody") is None

    @patch.dict("os.environ", {"LASTFM_API_KEY": "testkey"})
    @patch("music_classifier.utils.requests.get")
    def test_returns_none_on_api_error(self, mock_get):
        mock_get.side_effect = Exception("timeout")
        assert _lastfm_get_top_tags("Anyone") is None

    def test_returns_none_when_no_api_key(self):
        with patch.dict("os.environ", clear=True):
            assert _lastfm_get_top_tags("Radiohead") is None


# ---------------------------------------------------------------------------
# FILTERED_TAGS
# ---------------------------------------------------------------------------


class TestFilteredTags:
    def test_contains_known_junk_tag(self):
        assert "2008 universal fire victim" in FILTERED_TAGS

    @patch.dict("os.environ", {"LASTFM_API_KEY": "testkey"})
    @patch("music_classifier.utils.requests.get")
    def test_filtered_tag_excluded_from_results(self, mock_get):
        artist_resp = MagicMock()
        artist_resp.json.side_effect = [
            {"artists": [{"id": "abc", "name": "John Williams"}]},
            {"tags": [
                {"name": "soundtrack", "count": 100},
                {"name": "2008 universal fire victim", "count": 50},
                {"name": "classical", "count": 40},
            ]},
        ]
        mock_get.return_value = artist_resp
        genres, lang, matched = get_artist_genres_and_language("John Williams")
        assert "2008 universal fire victim" not in genres
        assert genres == ["soundtrack", "classical"]


# ---------------------------------------------------------------------------
# _normalize_for_comparison
# ---------------------------------------------------------------------------


class TestNormalizeForComparison:
    def test_lowercases(self):
        assert _normalize_for_comparison("Radiohead") == "radiohead"

    def test_strips_whitespace(self):
        assert _normalize_for_comparison("  Radiohead  ") == "radiohead"

    def test_replaces_ampersand(self):
        assert _normalize_for_comparison("Simon & Garfunkel") == "simon and garfunkel"

    def test_removes_special_chars(self):
        assert _normalize_for_comparison("AC/DC (live)") == "acdc live"

    def test_removes_leading_the(self):
        assert _normalize_for_comparison("The Beatles") == "beatles"

    def test_removes_leading_the_with_extra_spaces(self):
        assert _normalize_for_comparison("  The  Beatles  ") == "beatles"

    def test_all_transformations_together(self):
        assert _normalize_for_comparison("  The Black & White Band!  ") == "black and white band"

    def test_no_change_for_plain_name(self):
        assert _normalize_for_comparison("nirvana") == "nirvana"


# ---------------------------------------------------------------------------
# get_artist_genres_and_language
# ---------------------------------------------------------------------------


class TestGetArtistGenresAndLanguage:
    @patch("music_classifier.utils.requests.get")
    def test_returns_genres_and_language(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.side_effect = [
            {"artists": [{"id": "abc", "name": "Radiohead"}]},
            {"tags": [{"name": "alternative rock", "count": 50}, {"name": "english", "count": 40}]},
        ]
        mock_get.return_value = mock_resp
        genres, lang, matched = get_artist_genres_and_language("Radiohead")
        assert genres == ["alternative rock", "english"]
        assert lang == "eng"
        assert matched == "Radiohead"

    @patch("music_classifier.utils.requests.get")
    def test_returns_empty_on_fetch_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.side_effect = [
            {"artists": [{"id": "abc", "name": "Artist"}]},
            Exception("bad json"),
        ]
        mock_get.return_value = mock_resp
        genres, lang, matched = get_artist_genres_and_language("Artist")
        assert genres == []
        assert lang is None
        assert matched == "Artist"

    @patch("music_classifier.utils.requests.get")
    def test_returns_empty_on_search_error(self, mock_get):
        mock_get.side_effect = Exception("timeout")
        genres, lang, matched = get_artist_genres_and_language("Artist")
        assert genres == []
        assert lang is None
        assert matched is None

    @patch("music_classifier.utils.requests.get")
    def test_returns_empty_when_artist_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"artists": []}
        mock_get.return_value = mock_resp
        genres, lang, matched = get_artist_genres_and_language("NoOne")
        assert genres == []
        assert lang is None
        assert matched is None

    @patch("music_classifier.utils.requests.get")
    def test_returns_empty_when_no_tags(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.side_effect = [
            {"artists": [{"id": "abc", "name": "Artist"}]},
            {"tags": []},
        ]
        mock_get.return_value = mock_resp
        genres, lang, matched = get_artist_genres_and_language("Artist")
        assert genres == []
        assert lang is None
        assert matched == "Artist"

    @patch.dict("os.environ", {"LASTFM_API_KEY": "testkey"})
    @patch("music_classifier.utils.requests.get")
    def test_falls_back_to_lastfm_on_name_mismatch(self, mock_get):
        artist_resp = MagicMock()
        artist_resp.json.return_value = {
            "artists": [{"id": "abc", "name": "John Williams"}]
        }
        lf_resp = MagicMock()
        lf_resp.json.return_value = {
            "toptags": {"tag": [{"name": "ragtime", "count": 10}]}
        }
        mock_get.side_effect = [artist_resp, lf_resp]
        genres, lang, matched = get_artist_genres_and_language("Clarence Williams")
        assert genres == ["ragtime"]
        assert lang is None
        assert matched == "Clarence Williams"

    @patch.dict("os.environ", {"LASTFM_API_KEY": "testkey"})
    @patch("music_classifier.utils.requests.get")
    def test_uses_mb_when_name_matches(self, mock_get):
        artist_resp = MagicMock()
        artist_resp.json.side_effect = [
            {"artists": [{"id": "abc", "name": "Radiohead"}]},
            {"tags": [{"name": "alternative rock", "count": 50}]},
        ]
        mock_get.return_value = artist_resp
        genres, lang, matched = get_artist_genres_and_language("Radiohead")
        assert genres == ["alternative rock"]
        assert matched == "Radiohead"

    @patch.dict("os.environ", {"LASTFM_API_KEY": "testkey"})
    @patch("music_classifier.utils.requests.get")
    def test_returns_empty_on_name_mismatch_when_lastfm_also_fails(self, mock_get):
        artist_resp = MagicMock()
        artist_resp.json.return_value = {
            "artists": [{"id": "abc", "name": "John Williams"}]
        }
        lf_resp = MagicMock()
        lf_resp.json.return_value = {"toptags": {"tag": []}}
        mock_get.side_effect = [artist_resp, lf_resp]
        genres, lang, matched = get_artist_genres_and_language("Clarence Williams")
        assert genres == []
        assert lang is None
        assert matched == "John Williams"

    @patch.dict("os.environ", {"LASTFM_API_KEY": "testkey"})
    @patch("music_classifier.utils.requests.get")
    def test_normalized_leading_the_matches(self, mock_get):
        artist_resp = MagicMock()
        artist_resp.json.side_effect = [
            {"artists": [{"id": "abc", "name": "The Beatles"}]},
            {"tags": [{"name": "rock", "count": 100}]},
        ]
        mock_get.return_value = artist_resp
        genres, lang, matched = get_artist_genres_and_language("Beatles")
        assert genres == ["rock"]
        assert matched == "The Beatles"

    @patch.dict("os.environ", {"LASTFM_API_KEY": "testkey"})
    @patch("music_classifier.utils.requests.get")
    def test_normalized_ampersand_matches(self, mock_get):
        artist_resp = MagicMock()
        artist_resp.json.side_effect = [
            {"artists": [{"id": "abc", "name": "Simon & Garfunkel"}]},
            {"tags": [{"name": "folk rock", "count": 80}]},
        ]
        mock_get.return_value = artist_resp
        genres, lang, matched = get_artist_genres_and_language("Simon and Garfunkel")
        assert genres == ["folk rock"]
        assert matched == "Simon & Garfunkel"


# ---------------------------------------------------------------------------
# get_artist_genres_and_language — Last.fm fallback
# ---------------------------------------------------------------------------


class TestGetArtistGenresAndLanguageLastfmFallback:
    @patch.dict("os.environ", {"LASTFM_API_KEY": "testkey"})
    @patch("music_classifier.utils.requests.get")
    def test_falls_back_when_mb_artist_not_found(self, mock_get):
        mb_resp = MagicMock()
        mb_resp.json.return_value = {"artists": []}
        lf_resp = MagicMock()
        lf_resp.json.return_value = {
            "toptags": {"tag": [{"name": "blues", "count": 10}]}
        }
        mock_get.side_effect = [mb_resp, lf_resp]
        genres, lang, matched = get_artist_genres_and_language("NoOne")
        assert genres == ["blues"]
        assert lang is None
        assert matched == "NoOne"

    @patch.dict("os.environ", {"LASTFM_API_KEY": "testkey"})
    @patch("music_classifier.utils.requests.get")
    def test_falls_back_when_mb_tags_empty(self, mock_get):
        mb_artist = MagicMock()
        mb_artist.json.side_effect = [
            {"artists": [{"id": "abc", "name": "Artist"}]},
            {"tags": []},
        ]
        lf_resp = MagicMock()
        lf_resp.json.return_value = {
            "toptags": {"tag": [{"name": "folk", "count": 10}]}
        }
        mock_get.side_effect = [mb_artist, mb_artist, lf_resp]
        genres, lang, matched = get_artist_genres_and_language("Artist")
        assert genres == ["folk"]
        assert lang is None
        assert matched == "Artist"

    @patch.dict("os.environ", {"LASTFM_API_KEY": "testkey"})
    @patch("music_classifier.utils.requests.get")
    def test_falls_back_to_lastfm_when_mb_returns_no_artist(self, mock_get):
        mb_resp = MagicMock()
        mb_resp.json.return_value = {"artists": []}
        lf_resp = MagicMock()
        lf_resp.json.return_value = {
            "toptags": {"tag": [{"name": "electronic", "count": 10}]}
        }
        mock_get.side_effect = [mb_resp, lf_resp]
        genres, lang, matched = get_artist_genres_and_language("NoOne")
        assert genres == ["electronic"]

    @patch.dict("os.environ", {"LASTFM_API_KEY": "testkey"})
    @patch("music_classifier.utils.requests.get")
    def test_returns_empty_when_both_fail(self, mock_get):
        mb_resp = MagicMock()
        mb_resp.json.return_value = {"artists": []}
        lf_resp = MagicMock()
        lf_resp.json.return_value = {"toptags": {"tag": []}}
        mock_get.side_effect = [mb_resp, lf_resp]
        genres, lang, matched = get_artist_genres_and_language("NoOne")
        assert genres == []

    @patch("music_classifier.utils.requests.get")
    def test_no_fallback_when_no_api_key(self, mock_get):
        mb_resp = MagicMock()
        mb_resp.json.return_value = {"artists": []}
        mock_get.return_value = mb_resp
        with patch.dict("os.environ", clear=True):
            genres, lang, matched = get_artist_genres_and_language("NoOne")
            assert genres == []


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------


class TestClassify:
    def test_returns_bucket_for_matching_genre(self):
        assert classify(["rock"]) == "rock"

    def test_returns_other_for_empty_list(self):
        assert classify([]) == "other"

    def test_returns_other_for_unrecognized_genres(self):
        assert classify(["gospel", "country"]) == "other"

    def test_returns_best_match_multiple_candidates(self):
        result = classify(["rock", "indie rock", "pop"])
        assert result == "rock"

    def test_prefers_higher_scoring_bucket(self):
        result = classify(["disco", "boogie", "techno", "house"])
        assert result == "funk_disco"

    def test_classical_genre(self):
        assert classify(["classical", "baroque"]) == "classical"

    def test_hiphop_genre(self):
        assert classify(["hip hop", "rap"]) == "hiphop"

    def test_partial_keyword_does_not_match(self):
        assert classify(["metallica"]) == "metal"

    def test_case_insensitive(self):
        assert classify(["Rock", "Pop"]) == "rock"

    def test_substring_match_still_counted(self):
        assert classify(["electronic rock"]) == "rock"

    def test_soundtrack_category(self):
        assert classify(["soundtrack", "cinematic"]) == "soundtrack"

    def test_comedy_fun_priority(self):
        assert classify(["comedy", "rock"]) == "comedy_fun"

    def test_comedy_fun_beats_pop(self):
        assert classify(["pop", "parody"]) == "comedy_fun"

    def test_comedy_fun_beats_hiphop(self):
        assert classify(["comedy rap", "hip hop"]) == "comedy_fun"

    def test_funk_does_not_match_comedy(self):
        assert classify(["funk"]) == "funk_disco"


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------


class TestDeduplicate:
    def test_empty_list(self):
        canonical, mapping = deduplicate([])
        assert canonical == []
        assert mapping == {}

    def test_single_artist(self):
        canonical, mapping = deduplicate(["Green Day"])
        assert canonical == ["Green Day"]
        assert mapping == {"Green Day": "Green Day"}

    def test_no_duplicates(self):
        canonical, mapping = deduplicate(["Radiohead", "Nirvana", "Queen"])
        assert canonical == ["Radiohead", "Nirvana", "Queen"]
        assert mapping == {
            "Radiohead": "Radiohead",
            "Nirvana": "Nirvana",
            "Queen": "Queen",
        }

    def test_identical_artists_deduplicated(self):
        canonical, mapping = deduplicate(["Green Day", "Green Day"])
        assert canonical == ["Green Day"]
        assert mapping == {"Green Day": "Green Day"}

    def test_similar_passes_threshold(self):
        canonical, mapping = deduplicate(["Green Day", "Greenday"])
        assert len(canonical) == 1
        assert mapping["Greenday"] == "Green Day"

    def test_dissimilar_below_threshold_stays_separate(self):
        canonical, mapping = deduplicate(
            ["Radiohead", "Rihanna"], threshold=90
        )
        assert canonical == ["Radiohead", "Rihanna"]
        assert mapping == {"Radiohead": "Radiohead", "Rihanna": "Rihanna"}

    def test_custom_threshold_prevents_match(self):
        canonical, mapping = deduplicate(
            ["Green Day", "Greenday"], threshold=99
        )
        assert len(canonical) == 2
        assert mapping["Green Day"] == "Green Day"
        assert mapping["Greenday"] == "Greenday"

    def test_multiple_similar_groups(self):
        canonical, mapping = deduplicate(
            ["Blink 182", "Blink182", "Green Day", "Greenday"]
        )
        assert len(canonical) == 2
        assert mapping["Blink182"] == "Blink 182"
        assert mapping["Greenday"] == "Green Day"

    def test_canonical_preserves_first_occurrence(self):
        canonical, mapping = deduplicate(["Greenday", "Green Day"])
        assert canonical == ["Greenday"]
        assert mapping["Green Day"] == "Greenday"


# ---------------------------------------------------------------------------
# LANGUAGE_MAP
# ---------------------------------------------------------------------------


class TestLanguageMap:
    def test_contains_expected_languages(self):
        assert LANGUAGE_MAP["english"] == "eng"
        assert LANGUAGE_MAP["french"] == "fra"
        assert LANGUAGE_MAP["spanish"] == "spa"
        assert LANGUAGE_MAP["german"] == "deu"
        assert LANGUAGE_MAP["instrumental"] == "zxx"

    def test_includes_aliases(self):
        assert LANGUAGE_MAP["francais"] == "fra"
        assert LANGUAGE_MAP["espanol"] == "spa"
        assert LANGUAGE_MAP["deutsch"] == "deu"


# ---------------------------------------------------------------------------
# _read_existing_tags
# ---------------------------------------------------------------------------


class TestReadExistingTags:
    @patch("music_classifier.utils.EasyID3")
    def test_mp3_reads_genre_and_no_language(self, mock_easyid3):
        mock_audio = MagicMock()
        mock_audio.get.return_value = ["Rock, Electronic"]
        mock_easyid3.return_value = mock_audio
        genres, lang = _read_existing_tags("/f.mp3")
        assert genres == {"rock", "electronic"}
        assert lang is None

    @patch("music_classifier.utils.EasyID3")
    @patch("mutagen.id3.ID3")
    def test_mp3_reads_language_when_present(self, mock_id3, mock_easyid3):
        mock_audio = MagicMock()
        mock_audio.get.return_value = ["Jazz"]
        mock_easyid3.return_value = mock_audio
        mock_id3_instance = MagicMock()
        tlan = MagicMock()
        tlan.text = ["eng"]
        mock_id3_instance.get.return_value = tlan
        mock_id3.return_value = mock_id3_instance
        genres, lang = _read_existing_tags("/f.mp3")
        assert genres == {"jazz"}
        assert lang == "eng"

    @patch("music_classifier.utils.EasyID3")
    def test_mp3_handles_no_id3_header(self, mock_easyid3):
        from mutagen.id3 import ID3NoHeaderError
        mock_easyid3.side_effect = ID3NoHeaderError
        genres, lang = _read_existing_tags("/f.mp3")
        assert genres == set()
        assert lang is None

    @patch("mutagen.flac.FLAC")
    def test_flac_reads_tags(self, mock_flac):
        mock_audio = MagicMock()
        mock_audio.get.side_effect = (
            lambda key, default=None: {"GENRE": ["Funk", "Soul"], "LANGUAGE": ["eng"]}.get(key, default)
        )
        mock_flac.return_value = mock_audio
        genres, lang = _read_existing_tags("/f.flac")
        assert genres == {"funk", "soul"}
        assert lang == "eng"

    @patch("mutagen.flac.FLAC")
    def test_flac_handles_no_language(self, mock_flac):
        mock_audio = MagicMock()
        mock_audio.get.side_effect = (
            lambda key, default=None: {"GENRE": ["Blues"]}.get(key, default)
        )
        mock_flac.return_value = mock_audio
        genres, lang = _read_existing_tags("/f.flac")
        assert genres == {"blues"}
        assert lang is None

    def test_unsupported_extension_returns_empty(self):
        genres, lang = _read_existing_tags("/f.ogg")
        assert genres == set()
        assert lang is None


# ---------------------------------------------------------------------------
# _file_already_tagged
# ---------------------------------------------------------------------------


class TestFileAlreadyTagged:
    @patch("music_classifier.utils._read_existing_tags")
    def test_returns_true_when_tags_match(self, mock_read):
        mock_read.return_value = ({"rock", "pop"}, "eng")
        assert _file_already_tagged("/f.mp3", ["rock", "pop"], "eng") is True

    @patch("music_classifier.utils._read_existing_tags")
    def test_returns_false_when_genres_differ(self, mock_read):
        mock_read.return_value = ({"jazz"}, "eng")
        assert _file_already_tagged("/f.mp3", ["rock"], "eng") is False

    @patch("music_classifier.utils._read_existing_tags")
    def test_returns_false_when_language_differs(self, mock_read):
        mock_read.return_value = ({"rock"}, "spa")
        assert _file_already_tagged("/f.mp3", ["rock"], "eng") is False

    @patch("music_classifier.utils._read_existing_tags")
    def test_returns_true_when_no_genres_in_target(self, mock_read):
        mock_read.return_value = (set(), None)
        assert _file_already_tagged("/f.mp3", [], None) is True

    @patch("music_classifier.utils._read_existing_tags")
    def test_ignores_language_when_existing_is_none(self, mock_read):
        mock_read.return_value = ({"rock"}, None)
        assert _file_already_tagged("/f.mp3", ["rock"], "eng") is True


# ---------------------------------------------------------------------------
# tag_audio_file
# ---------------------------------------------------------------------------


class TestTagAudioFile:
    @patch("music_classifier.utils._file_already_tagged", return_value=True)
    @patch("music_classifier.utils.EasyID3")
    def test_skips_already_tagged(self, mock_easyid3, mock_checked):
        tag_audio_file("/f.mp3", ["rock"], "eng")
        mock_easyid3.assert_not_called()

    @patch("music_classifier.utils._file_already_tagged", return_value=False)
    @patch("music_classifier.utils.EasyID3")
    def test_writes_mp3_genre(self, mock_easyid3, mock_checked):
        tag_audio_file("/f.mp3", ["rock", "pop"], None)
        mock_easyid3.return_value.__setitem__.assert_called_once()
        mock_easyid3.return_value.save.assert_called_once()

    @patch("music_classifier.utils._file_already_tagged", return_value=False)
    @patch("music_classifier.utils.EasyID3")
    def test_handles_no_id3_header_for_mp3(self, mock_easyid3, mock_checked):
        from mutagen.id3 import ID3NoHeaderError
        mock_second = MagicMock()
        mock_easyid3.side_effect = [ID3NoHeaderError, mock_second]
        tag_audio_file("/f.mp3", ["jazz"])
        assert mock_easyid3.call_count == 2
        mock_second.save.assert_called_once()

    @patch("music_classifier.utils._file_already_tagged", return_value=False)
    @patch("music_classifier.utils.EasyID3")
    @patch("mutagen.id3.TLAN")
    @patch("mutagen.id3.ID3")
    def test_writes_language_for_mp3(self, mock_id3, mock_tlan, mock_easyid3, mock_checked):
        tag_audio_file("/f.mp3", ["rock"], "eng")
        mock_id3.return_value.__setitem__.assert_called_once()

    @patch("music_classifier.utils._file_already_tagged", return_value=False)
    @patch("mutagen.flac.FLAC")
    def test_writes_flac_tags(self, mock_flac, mock_checked):
        tag_audio_file("/f.flac", ["funk", "soul"], "eng")
        mock_flac.return_value.__setitem__.assert_called()
        mock_flac.return_value.save.assert_called_once()

    @patch("music_classifier.utils._file_already_tagged", return_value=False)
    @patch("mutagen.flac.FLAC")
    def test_writes_flac_genre_only(self, mock_flac, mock_checked):
        tag_audio_file("/f.flac", ["blues"], None)
        mock_flac.return_value.__setitem__.assert_called_once()
        mock_flac.return_value.save.assert_called_once()

    def test_does_nothing_for_empty_genres(self):
        tag_audio_file("/f.mp3", [])

    @patch("music_classifier.utils._file_already_tagged", return_value=False)
    def test_prints_for_unsupported_format(self, mock_checked, capsys):
        tag_audio_file("/f.ogg", ["rock"], "eng")
        captured = capsys.readouterr()
        assert "Unsupported" in captured.out


# ---------------------------------------------------------------------------
# artist_from_audio
# ---------------------------------------------------------------------------


class TestArtistFromAudio:
    @patch("music_classifier.utils.EasyID3")
    def test_returns_artist_from_mp3(self, mock_easyid3):
        mock_audio = MagicMock()
        mock_audio.get.return_value = ["Radiohead"]
        mock_easyid3.return_value = mock_audio
        assert artist_from_audio("/f.mp3") == "Radiohead"

    @patch("music_classifier.utils.EasyID3")
    def test_returns_none_when_no_artist_in_mp3(self, mock_easyid3):
        mock_audio = MagicMock()
        mock_audio.get.return_value = [None]
        mock_easyid3.return_value = mock_audio
        assert artist_from_audio("/f.mp3") is None

    @patch("music_classifier.utils.EasyID3")
    def test_falls_back_to_flac_when_mp3_fails(self, mock_easyid3):
        from mutagen.id3 import ID3NoHeaderError
        mock_easyid3.side_effect = ID3NoHeaderError
        with patch("mutagen.flac.FLAC") as mock_flac:
            mock_audio = MagicMock()
            mock_audio.get.return_value = ["Miles Davis"]
            mock_flac.return_value = mock_audio
            assert artist_from_audio("/f.flac") == "Miles Davis"

    @patch("music_classifier.utils.EasyID3")
    def test_returns_none_when_all_fail(self, mock_easyid3):
        from mutagen import MutagenError
        mock_easyid3.side_effect = MutagenError
        with patch("mutagen.flac.FLAC") as mock_flac:
            mock_flac.side_effect = Exception("not a flac")
            assert artist_from_audio("/f.unknown") is None


# ---------------------------------------------------------------------------
# reorganize_by_bpm
# ---------------------------------------------------------------------------


class TestReorganizeByBpm:
    def test_moves_files_into_bpm_folders(self, tmp_path):
        mp3 = tmp_path / "(120) Song.mp3"
        mp3.touch()
        from music_classifier.utils import reorganize_by_bpm
        reorganize_by_bpm(str(tmp_path))
        assert (tmp_path / "120s" / "(120) Song.mp3").exists()

    def test_skips_files_without_bpm(self, tmp_path):
        mp3 = tmp_path / "Song.mp3"
        mp3.touch()
        from music_classifier.utils import reorganize_by_bpm
        reorganize_by_bpm(str(tmp_path))
        assert mp3.exists()
        assert not (tmp_path / "0s").exists()

    def test_dry_run_does_not_move(self, tmp_path):
        mp3 = tmp_path / "(120) Song.mp3"
        mp3.touch()
        from music_classifier.utils import reorganize_by_bpm
        reorganize_by_bpm(str(tmp_path), dry_run=True)
        assert mp3.exists()
        assert not (tmp_path / "120s").exists()

    def test_handles_multiple_files(self, tmp_path):
        (tmp_path / "(120) A.mp3").touch()
        (tmp_path / "(130) B.mp3").touch()
        (tmp_path / "(125) C.mp3").touch()
        from music_classifier.utils import reorganize_by_bpm
        reorganize_by_bpm(str(tmp_path))
        assert (tmp_path / "120s" / "(120) A.mp3").exists()
        assert (tmp_path / "130s" / "(130) B.mp3").exists()
        assert (tmp_path / "120s" / "(125) C.mp3").exists()

    def test_skips_already_in_place(self, tmp_path):
        bpm_dir = tmp_path / "120s"
        bpm_dir.mkdir()
        (bpm_dir / "(120) Song.mp3").touch()
        from music_classifier.utils import reorganize_by_bpm
        reorganize_by_bpm(str(tmp_path))
        assert (bpm_dir / "(120) Song.mp3").exists()
