# Muzlib

Muzlib is a Python script that allows you to create your own music library.
Music is downloaded from YouTube, and music tags are constructed using data from YouTube, Lrclib, NetEase.

# Instalation

## Arch Linux \[AUR\]
You can install `python-muzlib` from AUR using your favorite AUR helper, for example:
```bash
yay -S python-muzlib
```

## From PyPI
Ensure that you have installed [FFmpeg](https://ffmpeg.org/download.html).

```bash
python -m venv .venv
source .venv/bin/activate
pip install muzlib
```

# Usage

You can simply download discography of artist (YouTube API by default).
![Examople of usage ](assets/usage.gif)

This script creates a simple database (`.muzlib/db.json`) to track downloaded tracks, allowing you to update an artist's discography without re-downloading existing tracks.

## Available clases

There is only one (for now ) classe that can be used:
1. `muzlib(library_path: str, skip_downloaded=False)`: library class that uses YouTube Music metadata (100% accuracy, but sometimes poor quality metadata)

## Available methods

### Downloading artist's discography
`Muzlib.download_artist_discography(artist_name: str, download_top_result=False)`
+ `artist_name`: Name of artist as a string.
+ `download_top_result`: If set to True, choose the first matching artist automatically. By default (False), it will prompt you to confirm if the match is correct.

### Downloading album
`Muzlib.download_album_by_name(search_term: str, download_top_result=False)`
+ `search_term`: The search query as a string. It is recommended to use the format: "artist1, artist2 - album_name".
+ `download_top_result`: If set to True, downloads the first matching result automatically. By default (False), it will prompt you to confirm if the match is correct.

### Download track
`Muzlib.download_track_by_name(search_term: str, download_top_result=False)`
+ `search_term`: The search query as a string. It is recommended to use the format: "artist1, artist2 - track_name".
+ `download_top_result`: If set to True, downloads the first matching result automatically. By default (False), it will prompt you to confirm if the match is correct.

### Backup library
`Muzlib.backup_library() -> str`

This function creates backup of library (even with user-changed tags).
Creates file `.muzlib/muzlib_backup_***.json` and returns path to it.


### Restore library
This function downloads track and set metadata from bacup file.

`Muzlib.backup_library(backup_filepath: str)`
+ `backup_filepath`: path of the file created by `Muzlib.backup_library()`.


## Example of use

You can use `Muzlib`/`` class in source code this way
```python
import muzlib
ml = muzlib.Muzlib("Music")
ml.download_track_by_name("Ludwig Göransson - Can You Hear The Music")
ml.download_track_by_name("Ludwig Göransson - Destroyer Of Worlds", download_top_result=True)
# ml.download_artist_discography("Ludwig Göransson") 
backup_path = ml.backup_library()

ml2 = muzlib.Muzlib("Music2")
ml2.restore_library(backup_path)
```
After running this code, the `Music` and `Music2` folders will be identical, each containing two tracks by Ludwig Göransson.


# Troubleshooting

> [!WARNING]
> If you encounter issues with yt-dlp, you can replace default cookies at `assets/cookies.txt` as described at [this guide](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp).