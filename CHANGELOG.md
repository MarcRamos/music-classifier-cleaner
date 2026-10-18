# Changelog

## [1.0.4] - 2026-10-18
### Fixed
- `classify-organize` crashed with `FileNotFoundError [WinError 2]` on
  Windows when an artist tag's capitalization differed from the artist
  folder name (e.g. tag `King Gizzard & The Lizard Wizard` vs folder
  `King Gizzard & the Lizard Wizard`). On case-insensitive filesystems
  the loose-file pass registered the same directory twice, so the second
  entry tried to rename a folder that had already been moved into a
  genre folder. Artist folders are now matched case-insensitively and
  reused instead of duplicated
- `classify-organize` no longer treats a case-only rename as a merge:
  `target.exists()` is true for a case variant of the source folder on
  Windows, which made it merge a folder into itself and delete its
  contents. A `samefile` check now routes this to a plain rename
- `classify-organize` skips (with a warning) artist folders that no
  longer exist instead of crashing mid-run
- 8 new tests in `tests/test_cli.py` (166 total)
- `classify-organize` silently skipped FLAC files when rewriting the
  `artist` tag after a folder rename — `update_artist_tag_inner` only
  used EasyID3, which cannot read FLAC. It now delegates to
  `_set_artist_tag`, which handles MP3 and FLAC
- `archive-download` and `music-tapper` never skipped already-processed
  files across runs: both called `load_processed_set()` without the CSV
  path, so the set was always empty despite `processed.csv` being
  written. The output CSV path is now passed (the filename/path checks
  in `pipeline.py` still compare against the `id` column and remain
  inert; only archive identifiers are matched)
### Changed
- Removed the duplicated MP3 tag-writing block by merging
  `update_artist_tag_inner` into `_set_artist_tag`
- Removed the unused `MP3` import from `utils.py` and a single-element
  loop in `archive.py`
- 3 new tests in `tests/test_cli.py` (166 → 169 total)

## [1.0.3] - 2026-10-14
### Fixed
- CLI commands (`music-tapper`, `classify-organize`, `scan-library`,
  `discover-from-library`, `tag-library-genres`) now accept native Windows
  paths (e.g. `C:\Music`). `resolve_library_path` tries the path as given
  before falling back to the WSL `/mnt/<drive>` form, so the same argument
  works on Windows, WSL, and Linux/macOS

## [1.0.2] - 2026-07-27
### Added
- `--tag-only` flag on `classify-organize` — tags genres and normalizes artist names in-place without moving folders into genre directories
### Fixed
- YouTube downloads with missing artist rename files from `NA - title.mp3` to `title.mp3`


## [1.0.1] - 2026-07-12
### Fixed
- Link to changelog
- Version in changelog

## [1.0.0] - 2026-07-12

### Added
- `extract_bpm()` in `audio.py` — extracts BPM from `(BPM)` prefix in filenames
- `reorganize_by_bpm()` in `utils.py` — reorganize MP3s into BPM range folders
- 10 new tests for `extract_bpm()` and `reorganize_by_bpm()` (135 total)
- `.gitignore` — properly ignores `__pycache__/`, `.coverage`, `*:Zone.Identifier`
- `ui.png` screenshot in README BPM tapping controls section
- `ffmpeg`/`ffprobe` check in `youtube.py` — clear error with install instructions if missing
- `deno` added to requirements — YouTube downloads now require a JS runtime

### Changed
- Flattened `tapper/` sub-package into `music_classifier/` (removed sub-package)
- Renamed `audio_utils.py` → `audio.py`
- `shutil.move` replaces `os.rename` in `audio.py` for cross-device moves
- `music-tapper` now defaults `--out` to the input folder
- README: updated commands table, project structure, test counts, and BPM UI screenshot

### Fixed
- Removed broken `is_duplicate()` from `csv_store.py` (undefined `SequenceMatcher`)
- Fixed empty `downloaded` list in `youtube.py`
- Fixed missing `continue` after processed check in `pipeline.py`

### Removed
- `scripts/reorganize_by_bpm.py` — functionality moved to `utils.reorganize_by_bpm()`
- `STOPWORDS`, `get_artist_genres()`, `get_artist_language()`, `get_metadata()`, `classify_artists()`, `artist_from_mp3()` from `utils.py`
- All `[DEBUG]` prints from `utils.py` and `cli.py`
- `tap-bpm` entry point (replaced by standalone `music-tapper` command)
