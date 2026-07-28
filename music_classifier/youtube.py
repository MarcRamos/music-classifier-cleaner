import os
import shutil

import yt_dlp


def _check_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError(
            "ffmpeg and ffprobe are required for audio conversion.\n"
            "Install them:\n"
            "  Ubuntu/Debian: sudo apt install ffmpeg\n"
            "  macOS:         brew install ffmpeg\n"
            "  Windows:       choco install ffmpeg"
        )


def _check_js_runtime():
    if not shutil.which("deno"):
        raise RuntimeError(
            "A JavaScript runtime (deno) is required for YouTube downloads.\n"
            "Install deno:\n"
            "  curl -fsSL https://deno.land/install.sh | sh\n"
            "Or visit: https://deno.land/#installation"
        )


DEFAULT_YDL_OPTS = {
    "format": "bestaudio/best",
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }
    ],
    "outtmpl": "%(artist)s - %(title)s.%(ext)s",
    "noplaylist": False,
    "cachedir": False,
    "ignoreerrors": True,
    "rm-cache-dir": True,
    "extractor-args": "youtube:player-client=default,mweb",
}


def _strip_na_prefix(dest_dir):
    for filename in os.listdir(dest_dir):
        if filename.lower().endswith(".mp3") and filename.startswith("NA - "):
            new_name = filename[len("NA - "):]
            old_path = os.path.join(dest_dir, filename)
            new_path = os.path.join(dest_dir, new_name)
            if not os.path.exists(new_path):
                os.rename(old_path, new_path)


def download_ytmusic_playlist(urls, dest_dir=".", extra_opts=None):
    """
    Download audio from YouTube Music playlists as MP3.

    Parameters
    ----------
    urls : list of str
        YouTube Music playlist URLs to download.
    dest_dir : str, optional
        Destination directory for downloaded files. Default is current dir.
    extra_opts : dict, optional
        Additional yt-dlp options merged onto the defaults.

    Returns
    -------
    list of str
        Filenames of successfully downloaded files.
    """
    opts = {**DEFAULT_YDL_OPTS}
    if dest_dir != ".":
        opts["outtmpl"] = os.path.join(dest_dir, "%(artist)s - %(title)s.%(ext)s")
    if extra_opts:
        opts.update(extra_opts)

    os.makedirs(dest_dir, exist_ok=True)
    downloaded = []

    _check_ffmpeg()
    _check_js_runtime()

    with yt_dlp.YoutubeDL(opts) as ydl:
        for url in urls:
            print(f"Downloading: {url}")
            try:
                ydl.download([url])
                downloaded.append(url)
            except Exception as e:
                print(f"  Error downloading {url}: {e}")

    _strip_na_prefix(dest_dir)

    return downloaded
