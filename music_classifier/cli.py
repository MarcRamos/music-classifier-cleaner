import argparse
import csv
import shutil

from mutagen import MutagenError
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError

from music_classifier.utils import (
    GENRE_FOLDERS,
    artist_from_audio,
    audio_files,
    classify,
    deduplicate,
    get_artist_genres_and_language,
    normalize_artist,
    recommend_top_tracks,
    resolve_library_path,
    tag_library_genres,
)


def classify_organize_main():
    """Scan library, classify artists by genre via MusicBrainz, reorganise into genre folders."""
    parser = argparse.ArgumentParser(description="Classify and organise a music library.")
    parser.add_argument("library", help="Path to the music library root")
    args = parser.parse_args()

    library = resolve_library_path(args.library)

    entries = sorted(library.iterdir())
    artist_folders = {}
    for entry in entries:
        if (entry.is_dir()
                and normalize_artist(entry.name) is not None
                and entry.name not in GENRE_FOLDERS):
            artist_folders[entry.name] = entry

    for mp3_file in audio_files(library):
        artist = artist_from_audio(mp3_file)
        if not artist:
            print(f"Skipping {mp3_file.name}: no artist tag")
            continue

        clean = normalize_artist(artist)
        if not clean:
            print(f"Skipping {mp3_file.name}: artist '{artist}' normalizes to empty")
            continue

        found = False
        for genre_name in GENRE_FOLDERS:
            genre_dir = library / genre_name
            if not genre_dir.is_dir():
                continue
            for subdir in genre_dir.iterdir():
                if subdir.is_dir() and normalize_artist(subdir.name) == clean:
                    shutil.move(str(mp3_file), str(subdir / mp3_file.name))
                    print(f"Moved '{mp3_file.name}' into {genre_name}/{subdir.name}/")
                    found = True
                    break
            if found:
                break

        if found:
            continue

        dest_name = artist
        if dest_name in GENRE_FOLDERS:
            dest_name = f"_{dest_name}"
        temp_dir = library / dest_name
        temp_dir.mkdir(exist_ok=True)
        shutil.move(str(mp3_file), str(temp_dir / mp3_file.name))
        if dest_name not in artist_folders:
            artist_folders[dest_name] = temp_dir

    if not artist_folders:
        print("No artist folders or MP3 files found")
        return

    raw_names = list(artist_folders.keys())
    canonical_list, mapping = deduplicate(raw_names)

    for raw_name in raw_names:
        canonical_name = mapping[raw_name]
        current_dir = artist_folders[raw_name]

        print(f"Processing {raw_name} -> {canonical_name}")

        if current_dir.name != canonical_name:
            target = current_dir.with_name(canonical_name)
            if target.exists():
                merge_into(current_dir, target)
                current_dir = target
            else:
                current_dir.rename(target)
                current_dir = target

        update_artist_tag_inner(current_dir, canonical_name)

        clean = normalize_artist(canonical_name)
        genres, language, matched = get_artist_genres_and_language(clean)
        category = classify(genres)

        genre_dir = library / category
        genre_dir.mkdir(exist_ok=True)

        dest = genre_dir / current_dir.name
        if category == "swing":
            # swing is categorized later using bpm
            dest = genre_dir
        if dest.exists():
            print(f"  -> Merging into existing {category}/ folder")
            merge_into(current_dir, dest)
        else:
            current_dir.rename(dest)

        print(f"  -> Moved to {category}/")


def update_artist_tag_inner(directory, artist_name):
    for mp3_file in audio_files(directory):
        try:
            audio = EasyID3(mp3_file)
            audio["artist"] = artist_name
            audio.save()
        except (ID3NoHeaderError, MutagenError):
            pass


def merge_into(src_dir, dst_dir):
    for item in src_dir.iterdir():
        dest = dst_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
            try:
                shutil.rmtree(item)
            except OSError:
                print(f"  Warning: could not remove {item}")
        else:
            shutil.move(str(item), str(dest))
    src_dir.rmdir()


def scan_library_main():
    """Scan library for artists with few songs, output a CSV for manual review."""
    parser = argparse.ArgumentParser(description="Scan library for artists with few songs.")
    parser.add_argument("library", help="Path to the music library root")
    parser.add_argument("-t", "--threshold", type=int, default=4,
                        help="Max song count to flag an artist (default: 4)")
    args = parser.parse_args()

    library = resolve_library_path(args.library)

    artists = _count_songs(library)

    sparse = {
        k: v
        for k, v in sorted(artists.items())
        if v["count"] < args.threshold
    }

    if not sparse:
        print(f"No artists with fewer than {args.threshold} songs found.")
        return

    csv_path = library / "artists_to_review.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["artist", "genre", "song_count", "path", "decision"])
        for clean, info in sparse.items():
            if info["genre"] == "root":
                display_path = f"{library.name}/"
            else:
                display_path = f"{library.name}/{info['genre']}/{info['display_name']}"
            writer.writerow([info["display_name"], info["genre"], info["count"], display_path, ""])

    print(f"Found {len(sparse)} artists with fewer than {args.threshold} songs.")
    print(f"CSV written to {csv_path}")
    print("Fill the 'decision' column with 'explore' or 'remove'.")


def _count_songs(library):
    artists = {}

    for genre in GENRE_FOLDERS:
        genre_dir = library / genre
        if not genre_dir.is_dir():
            continue
        for artist_dir in sorted(genre_dir.iterdir()):
            if not artist_dir.is_dir():
                continue
            files = sorted(artist_dir.rglob("*.mp3")) + sorted(artist_dir.rglob("*.flac"))
            count = len(files)
            if count == 0:
                path = f"{library.name}/{genre}/{artist_dir.name}"
                answer = input(f"'{path}' has 0 audio files. Delete folder? [y/N] ")
                if answer.lower() == "y":
                    try:
                        shutil.rmtree(artist_dir)
                        print(f"  Deleted {path}")
                    except OSError as e:
                        print(f"  Error deleting {path}: {e}")
                continue
            clean = normalize_artist(artist_dir.name)
            if not clean:
                continue
            if clean not in artists:
                artists[clean] = {
                    "display_name": artist_dir.name,
                    "genre": genre,
                    "count": 0,
                }
            artists[clean]["count"] += count

    for mp3 in audio_files(library):
        artist = artist_from_audio(mp3)
        if not artist:
            continue
        clean = normalize_artist(artist)
        if not clean:
            continue
        if clean not in artists:
            artists[clean] = {
                "display_name": artist,
                "genre": "root",
                "count": 0,
            }
        artists[clean]["count"] += 1

    return artists


def discover_from_library_main():
    """Process the review CSV — remove artist folders or explore top tracks via Deezer."""
    parser = argparse.ArgumentParser(description="Process artists_to_review.csv decisions.")
    parser.add_argument("csv", help="Path to the artists_to_review.csv file")
    args = parser.parse_args()
    process_csv(args.csv)


def process_csv(csv_path):
    csv_path = resolve_library_path(csv_path)
    library_root = csv_path.parent

    lines = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lines.append(row)

    if not lines:
        print("CSV is empty.")
        return

    removes = [r for r in lines if r.get("decision", "").strip().lower() == "remove"]
    explores = [r for r in lines if r.get("decision", "").strip().lower() == "explore"]

    if removes:
        print(f"Processing {len(removes)} 'remove' decision(s)...")
        for row in removes:
            genre = row.get("genre", "")
            artist = row.get("artist", "")
            if genre == "root":
                continue
            folder = library_root / genre / artist
            if folder.is_dir():
                try:
                    shutil.rmtree(folder)
                    print(f"  Removed {library_root.name}/{genre}/{artist}")
                except OSError as e:
                    print(f"  Error removing {library_root.name}/{genre}/{artist}: {e}")
            else:
                print(f"  Folder not found: {folder}")

    if explores:
        print(f"Processing {len(explores)} 'explore' decision(s)...")
        for row in explores:
            artist = row.get("artist", "")
            recommend_top_tracks(artist)

    print("Done.")


def tag_library_genres_main():
    """Tag all audio files with top 3 MusicBrainz genres + language tag, verifying artist match."""
    parser = argparse.ArgumentParser(
        description="Tag all audio files in the library with top 3 MusicBrainz genres."
    )
    parser.add_argument("library", help="Path to the music library root")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="Preview genres without writing tags")
    args = parser.parse_args()

    library = resolve_library_path(args.library)
    print(f"Library: {library}")
    print(f"Mode: {'dry-run (no changes)' if args.dry_run else 'live tagging'}")
    print()

    tag_library_genres(library, dry_run=args.dry_run)


def download_ytmusic_main():
    """Download audio from YouTube Music playlists as MP3."""
    parser = argparse.ArgumentParser(
        description="Download audio from YouTube Music playlists."
    )
    parser.add_argument(
        "urls",
        nargs="+",
        help="YouTube Music playlist URLs to download",
    )
    parser.add_argument(
        "--out",
        default=".",
        help="Output directory (default: current dir)",
    )
    args = parser.parse_args()

    from music_classifier.youtube import download_ytmusic_playlist
    download_ytmusic_playlist(args.urls, dest_dir=args.out)
