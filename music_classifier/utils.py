import glob
import os
import re
import shutil
import time
from pathlib import Path

import requests
from rapidfuzz import fuzz
from mutagen import MutagenError
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError
from mutagen.mp3 import MP3

from music_classifier.bpm_organizer import bpm_folder
from music_classifier.audio import extract_bpm

JUNK = {
    "na",
    "musicbee_library_db",
    "listas de reproducción",
    "musica moderna",
    "soundtrack",
}


def resolve_library_path(path_str):
    path_str = str(path_str).replace("\\", "/")
    if len(path_str) >= 3 and path_str[1] == ":" and path_str[2] == "/":
        drive = path_str[0].lower()
        path_str = f"/mnt/{drive}{path_str[2:]}"
    path_obj = Path(path_str).resolve()
    if not path_obj.exists():
        msg = f"'{path_str}' not found"
        raise FileNotFoundError(msg)
    return path_obj


def audio_files(directory):
    return sorted(directory.glob("*.mp3")) + sorted(directory.glob("*.flac"))


def normalize_artist(name):
    name = name.lower().strip()

    name = re.sub(r"\.(mp3|wav|flac)$", "", name)
    name = re.split(r"\b(?:feat|featuring|ft)\b", name)[0]
    name = name.split(" - ")[0]
    name = re.sub(r"[^\w\s&']", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    if name in JUNK or not name:
        return None

    return name


MB_HEADERS = {"User-Agent": "MusicClassifier/1.0 (opencode-project)"}


def _normalize_for_comparison(name):
    name = name.lower().strip()
    name = re.sub(r"[&]", " and ", name)
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if name.startswith("the "):
        name = name[4:]
    return name.strip()


def _mb_search_artist(name):
    time.sleep(1)
    url = "https://musicbrainz.org/ws/2/artist/"
    params = {"query": f"artist:{name}", "fmt": "json", "limit": 1}
    resp = requests.get(url, params=params, headers=MB_HEADERS)
    resp.raise_for_status()
    data = resp.json()
    return data["artists"][0] if data.get("artists") else None


def _mb_artist_tags(mbid):
    time.sleep(1)
    url = f"https://musicbrainz.org/ws/2/artist/{mbid}"
    params = {"inc": "tags", "fmt": "json"}
    resp = requests.get(url, params=params, headers=MB_HEADERS)
    resp.raise_for_status()
    data = resp.json()
    return data.get("tags", [])


def _lastfm_get_top_tags(artist_name):
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        return None
    time.sleep(0.5)
    url = "http://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "artist.gettoptags",
        "artist": artist_name,
        "api_key": api_key,
        "format": "json",
    }
    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        tags = data.get("toptags", {}).get("tag", [])
        if tags:
            return [t["name"] for t in tags]
    except Exception:
        pass
    return None


DZ_HEADERS = {"User-Agent": "MusicClassifier/1.0 (opencode-project)"}


def _deezer_search_artist(name):
    url = "https://api.deezer.com/search/artist"
    params = {"q": name, "limit": 1}
    resp = requests.get(url, params=params, headers=DZ_HEADERS)
    resp.raise_for_status()
    data = resp.json()
    return data["data"][0] if data.get("data") else None


def _deezer_top_tracks(artist_id, limit=5):
    url = f"https://api.deezer.com/artist/{artist_id}/top"
    params = {"limit": limit}
    resp = requests.get(url, params=params, headers=DZ_HEADERS)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


def recommend_top_tracks(artist_name):
    print(f"  Looking up '{artist_name}' on Deezer...")
    artist = _deezer_search_artist(artist_name)
    if not artist:
        print(f"  No Deezer results for '{artist_name}'")
        return

    matched = artist.get("name", "?")
    print(f"  Deezer matched: '{matched}'")
    time.sleep(0.5)

    tracks = _deezer_top_tracks(artist["id"])
    if not tracks:
        print(f"  No top tracks found.")
        return

    print(f"  Top tracks:")
    for i, track in enumerate(tracks, 1):
        title = track.get("title", "?")
        duration = track.get("duration", 0)
        mins, secs = divmod(duration, 60)
        print(f"    {i}. {title}  ({mins}:{secs:02d})")


FILTERED_TAGS = {
    "2008 universal fire victim",
}


GENRE_MAP = {
    "funk_disco": [
        "funk", "disco", "nu disco", "boogie",
        "disco house", "electro funk"
    ],
    "rock": [
        "rock", "garage rock", "hard rock",
        "alternative rock", "indie rock",
        "punk", "hardcore", "post-punk", "emo",
        "pop", "synthpop", "electropop"
    ],
    "metal": [
        "metal", "thrash metal", "doom metal"
    ],
    "electronic": [
        "electro", "edm", "house", "techno",
        "synthwave", "electronica", "ambient"
    ],
    "hiphop": [
        "hip hop", "rap", "trap"
    ],
    "jazz_soul_rnb": [
        "jazz", "soul", "r&b", "neo soul"
    ],
    "classical": [
        "classical", "baroque", "orchestra"
    ],
    "soundtrack": [
        "soundtrack", "score", "film score",
        "video game music", "game soundtrack",
        "movie soundtrack"
    ],
    "comedy_fun": [
        "comedy", "fun", "jokes", "humor",
        "parody", "novelty", "funny",
        "comedy rock", "comedy rap"
    ],
    "swing": [
        "swing", "big band", "traditional jazz",
        "dixieland", "ragtime", "vocal jazz",
        "easy listening", "lounge",
        "30s", "40s", "1930s", "1940s"
    ],
    "rock-n-roll": [
        "rock and roll", "rock n roll", "rock & roll",
        "rockabilly", "rock-a-billy",
        "doo wop", "doo-wop",
        "50s", "1950s", "fifties",
        "oldies", "rhythm and blues",
        "elvis", "buddy holly", "chuck berry",
        "little richard", "jerry lee lewis"
    ]
}

GENRE_FOLDERS = set(GENRE_MAP.keys()) | {"other"}


COMEDY_KEYWORDS = GENRE_MAP["comedy_fun"]


def classify(genres):
    genre_text = " ".join(genres).lower()

    if any(re.search(rf"\b{re.escape(kw)}\b", genre_text) for kw in COMEDY_KEYWORDS):
        return "comedy_fun"

    scores = {}
    for bucket, keywords in GENRE_MAP.items():
        score = sum(keyword in genre_text for keyword in keywords)
        scores[bucket] = score

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "other"
    return best


def deduplicate(artists, threshold=90):
    canonical = []
    mapping = {}

    for artist in artists:
        found = False

        for existing in canonical:
            score = fuzz.ratio(
                artist.lower(),
                existing.lower()
            )

            if score >= threshold:
                mapping[artist] = existing
                found = True
                break

        if not found:
            canonical.append(artist)
            mapping[artist] = artist

    return canonical, mapping


LANGUAGE_MAP = {
    "english": "eng", "anglais": "eng", "ingles": "eng",
    "french": "fra", "francais": "fra", "français": "fra",
    "spanish": "spa", "espanol": "spa", "español": "spa", "castellano": "spa",
    "german": "deu", "deutsch": "deu", "allemand": "deu",
    "italian": "ita", "italiano": "ita",
    "portuguese": "por", "portugues": "por", "português": "por",
    "dutch": "nld", "nederlands": "nld", "hollandais": "nld",
    "japanese": "jpn", "nihongo": "jpn", "日本語": "jpn",
    "chinese": "chi", "mandarin": "chi", "cantonese": "chi", "中文": "chi",
    "korean": "kor", "hangul": "kor", "한국어": "kor",
    "russian": "rus", "russkiy": "rus", "русский": "rus",
    "swedish": "swe", "svenska": "swe",
    "danish": "dan", "dansk": "dan",
    "norwegian": "nor", "norsk": "nor",
    "finnish": "fin", "suomi": "fin",
    "polish": "pol", "polski": "pol",
    "czech": "ces", "cestina": "ces", "čeština": "ces",
    "hungarian": "hun", "magyar": "hun",
    "greek": "ell", "ellinika": "ell", "ελληνικά": "ell",
    "turkish": "tur", "turkce": "tur", "türkçe": "tur",
    "arabic": "ara", "العربية": "ara",
    "hindi": "hin", "हिन्दी": "hin",
    "latin": "lat",
    "instrumental": "zxx",
}


def get_artist_genres_and_language(artist_name):
    artist = None
    try:
        artist = _mb_search_artist(artist_name)
    except Exception:
        pass

    if not artist:
        lf_tags = _lastfm_get_top_tags(artist_name)
        if lf_tags:
            return lf_tags, None, artist_name
        return [], None, None

    mbid = artist["id"]
    matched = artist.get("name", "?")

    if _normalize_for_comparison(matched) != _normalize_for_comparison(artist_name):
        lf_tags = _lastfm_get_top_tags(artist_name)
        if lf_tags:
            return lf_tags, None, artist_name
        return [], None, matched

    tags = None
    try:
        tags = _mb_artist_tags(mbid)
    except Exception:
        pass

    if not tags:
        lf_tags = _lastfm_get_top_tags(artist_name)
        if lf_tags:
            return lf_tags, None, matched or artist_name
        return [], None, matched

    sorted_tags = sorted(tags, key=lambda t: t.get("count", 0), reverse=True)
    genres = [t["name"] for t in sorted_tags
              if t["name"].strip().lower() not in FILTERED_TAGS]

    language = None
    for tag in sorted_tags:
        name = tag["name"].strip().lower()
        if name in LANGUAGE_MAP:
            language = LANGUAGE_MAP[name]
            break

    return genres, language, matched


def _read_existing_tags(file_path):
    file_path = Path(file_path)
    ext = file_path.suffix.lower()
    existing_genres = set()
    existing_language = None

    if ext == ".mp3":
        try:
            audio = EasyID3(file_path)
            genre_str = audio.get("genre", [""])[0]
            existing_genres = {g.strip().lower() for g in genre_str.split(",") if g.strip()}
        except (ID3NoHeaderError, MutagenError):
            pass
        try:
            from mutagen.id3 import ID3
            id3 = ID3(file_path)
            tlan = id3.get("TLAN")
            if tlan:
                existing_language = str(tlan.text[0]).strip().lower()
        except Exception:
            pass
    elif ext == ".flac":
        try:
            from mutagen.flac import FLAC
            audio = FLAC(file_path)
            existing_genres = {g.strip().lower() for g in audio.get("GENRE", [])}
            lang_list = audio.get("LANGUAGE", [])
            if lang_list:
                existing_language = lang_list[0].strip().lower()
        except Exception:
            pass

    return existing_genres, existing_language


def _file_already_tagged(file_path, genres, language):
    existing_genres, existing_language = _read_existing_tags(file_path)
    target_genres = {g.strip().lower() for g in genres[:3]}
    if target_genres and target_genres != existing_genres:
        return False
    if language and existing_language and existing_language != language.lower():
        return False
    return True


def tag_audio_file(file_path, genres, language=None):
    file_path = Path(file_path)
    genres = genres[:3]
    if not genres:
        return

    if _file_already_tagged(file_path, genres, language):
        return

    ext = file_path.suffix.lower()

    if ext == ".mp3":
        try:
            audio = EasyID3(file_path)
        except ID3NoHeaderError:
            audio = EasyID3()
        audio["genre"] = ", ".join(genres)
        audio.save(file_path)
        if language:
            from mutagen.id3 import ID3, TLAN
            try:
                id3 = ID3(file_path)
            except ID3NoHeaderError:
                id3 = ID3()
            id3["TLAN"] = TLAN(encoding=3, text=language)
            id3.save(file_path)
    elif ext == ".flac":
        from mutagen.flac import FLAC

        audio = FLAC(file_path)
        audio["GENRE"] = genres
        if language:
            audio["LANGUAGE"] = [language]
        audio.save()
    else:
        print(f"  Unsupported format: {file_path} ({ext})")


def artist_from_audio(file_path):
    try:
        audio = EasyID3(file_path)
        return audio.get("artist", [None])[0]
    except (ID3NoHeaderError, MutagenError):
        pass
    try:
        from mutagen.flac import FLAC
        audio = FLAC(file_path)
        artists = audio.get("ARTIST", [])
        return artists[0] if artists else None
    except Exception:
        return None


def tag_library_genres(library_path, dry_run=False):
    library = resolve_library_path(library_path)

    files = sorted(library.rglob("*.mp3")) + sorted(library.rglob("*.flac"))
    if not files:
        print("No audio files found.")
        return

    print(f"Found {len(files)} audio files")
    cache = {}

    for f in files:
        rel = f.relative_to(library)
        artist_name = artist_from_audio(f)
        if not artist_name:
            print(f"  No artist tag: {rel}")
            continue

        if artist_name not in cache:
            print(f"\n  Looking up: {artist_name}")
            genres, language, matched = get_artist_genres_and_language(artist_name)
            cache[artist_name] = (genres, language, matched)

        genres, language, matched = cache[artist_name]

        if matched and _normalize_for_comparison(matched) != _normalize_for_comparison(artist_name):
            print(f"  Skipping: MB matched '{matched}' != file artist '{artist_name}'")
            continue

        if not genres:
            continue

        top_genres = genres[:3]

        if dry_run:
            print(f"  Would tag: {rel}")
            print(f"    Artist: {artist_name}")
            print(f"    Genres: {', '.join(top_genres)}")
            print(f"    Language: {language or 'unknown'}")
            continue

        if _file_already_tagged(f, top_genres, language):
            continue

        try:
            tag_audio_file(f, top_genres, language)
            print(f"  Tagged: {rel}")
            print(f"    Artist: {artist_name}")
            print(f"    Genres: {', '.join(top_genres)}")
            print(f"    Language: {language or 'unknown'}")
        except Exception as e:
            print(f"  Error tagging {rel}: {e}")


def reorganize_by_bpm(folder, dry_run=False):
    mp3_files = glob.glob(os.path.join(folder, "*.mp3"))
    if not mp3_files:
        print(f"No MP3 files found in {folder}")
        return

    skipped_no_bpm = []
    moved = 0
    skipped_same = 0

    for mp3_path in sorted(mp3_files):
        basename = os.path.basename(mp3_path)
        bpm = extract_bpm(basename)

        if bpm is None:
            skipped_no_bpm.append(basename)
            continue

        target_dir = os.path.join(folder, bpm_folder(bpm))
        target_path = os.path.join(target_dir, basename)

        if os.path.abspath(mp3_path) == os.path.abspath(target_path):
            skipped_same += 1
            continue

        if dry_run:
            print(f"  move: {basename} -> {bpm_folder(bpm)}/")
        else:
            os.makedirs(target_dir, exist_ok=True)
            shutil.move(mp3_path, target_path)

        moved += 1

    print(f"\nMoved: {moved}")
    print(f"Already in place: {skipped_same}")
    print(f"No BPM tag: {len(skipped_no_bpm)}")
    if skipped_no_bpm:
        for name in skipped_no_bpm:
            print(f"  {name}")
