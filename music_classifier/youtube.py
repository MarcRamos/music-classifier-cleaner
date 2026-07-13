import os

import yt_dlp


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

    with yt_dlp.YoutubeDL(opts) as ydl:
        for url in urls:
            print(f"Downloading: {url}")
            try:
                ydl.download([url])
                downloaded.append(url)
            except Exception as e:
                print(f"  Error downloading {url}: {e}")

    return downloaded
