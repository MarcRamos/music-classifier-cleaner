import time
import os
import glob

import click

from music_classifier.archive import (
    build_search_query,
    search_items,
    get_mp3_files,
    download_mp3,
)
from music_classifier.audio import normalize_mp3_name_meta, save_bpm_to_mp3, has_bpm
from music_classifier.bpm_ui import measure_bpm_ui
from music_classifier.csv_store import load_processed_set, append_entry
from music_classifier.bpm_organizer import bpm_folder
from music_classifier.utils import resolve_library_path


def _split_csv(value):
    """Convert comma-separated string into list (or return None)."""
    if value is None:
        return None
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return value


def _process_archive_files(query, out_folder):
    processed = load_processed_set()
    DEST_DIR = os.path.join("download", "raw")
    os.makedirs(DEST_DIR, exist_ok=True)

    page = 1
    total_items = None
    running = True
    while running:
        response = search_items(page, query)

        if total_items is None:
            total_items = response["numFound"]
            click.echo(f"Items found: {total_items}")

        items = response["docs"]
        if not items:
            break

        click.echo(f"Page {page}, items: {len(items)}")

        for item in items:
            identifier = item["identifier"]
            if identifier in processed:
                click.echo(f"Object already processed: {identifier}, skipping.")
                continue
            file_names = get_mp3_files(identifier)
            for file_name in file_names:
                if file_name in processed:
                    click.echo(f"Skipping duplicate: {file_name}")
                    continue
                click.echo(f"MP3 file: {file_name}")
                mp3_path = download_mp3(identifier, file_name, DEST_DIR)
                if has_bpm(mp3_path):
                    click.echo(f"Already has BPM, skipping: {file_name}")
                    continue
                time.sleep(0.5)  # be nice to archive.org
                bpm, running = measure_bpm_ui(mp3_path)
                if bpm is None:
                    if not running:
                        click.echo("Cancelled by the user")
                        break
                    click.echo("Skipped by the user")
                    continue

                save_bpm_to_mp3(mp3_path, bpm)
                object_mp3 = normalize_mp3_name_meta(
                    mp3_path, os.path.join("library", bpm_folder(bpm))
                )
                object_mp3.update(
                    {
                        "id": identifier,
                        "csv_path": os.path.join(out_folder, "library.csv"),
                    }
                )
                append_entry(**object_mp3)
                click.echo("Successfully processed\n")
            if not running:
                break


def _process_local_folder(folder_path, out_folder="library/"):
    mp3_files = glob.glob(os.path.join(resolve_library_path(folder_path), "*.mp3"))
    processed = load_processed_set()
    for mp3_path in mp3_files:
        click.echo(f"Processing {os.path.basename(mp3_path)}")
        if has_bpm(mp3_path):
            click.echo(f"Already has BPM, skipping: {os.path.basename(mp3_path)}")
            continue
        if mp3_path in processed:
            click.echo(f"Skipping duplicate: {mp3_path}")
            continue
        bpm, running = measure_bpm_ui(mp3_path)
        if bpm is None:
            if not running:
                click.echo("Cancelled by the user")
                break
            click.echo("Skipped by the user")
            continue
        save_bpm_to_mp3(mp3_path, bpm)
        bpm_out_folder = os.path.join(out_folder, bpm_folder(bpm))
        object_mp3 = normalize_mp3_name_meta(mp3_path, bpm_out_folder)
        object_mp3.update(
            {"id": None, "csv_path": os.path.join(out_folder, "library.csv")}
        )
        append_entry(**object_mp3)
        click.echo("Successfully processed\n")


@click.command()
@click.option("--text", help="Free text search (e.g. song title or keywords).")
@click.option("--artist", help="Artist or creator name (e.g. 'Count Basie').")
@click.option("--genres", help="Comma-separated genres (e.g. 'Jazz,Swing,Big Band').")
@click.option("--subjects", help="Comma-separated subjects/tags from archive.org.")
@click.option("--year-from", type=int, help="Start year (e.g. 1930).")
@click.option("--year-to", type=int, help="End year (e.g. 1945).")
@click.option("--out", default="library/", show_default=True, help="Output folder.")
def archive_download(text, artist, genres, subjects, year_from, year_to, out):
    """Download songs from archive.org, measure BPM and store them locally."""
    query = build_search_query(
        text=text,
        artist=artist,
        genres=_split_csv(genres),
        subjects=_split_csv(subjects),
        year_from=year_from,
        year_to=year_to,
    )
    click.echo(f"Query:\n{query}\n")
    _process_archive_files(query, out_folder=out)


@click.command()
@click.argument("folder")
@click.option("--out", default=None, help="Output folder (default: same as input).")
def music_tapper(folder, out):
    """Tap BPM for MP3s in a local folder and organize by BPM range."""
    folder = resolve_library_path(folder)
    if out is None:
        out = str(folder)
    click.echo(f"Processing folder: {folder}")
    click.echo(f"Output library: {out}\n")
    _process_local_folder(str(folder), out_folder=out)
