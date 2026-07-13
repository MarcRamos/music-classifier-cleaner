# Changelog

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
