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
 
Muzlib can be run directly from the command line. When launched without arguments, it starts an interactive prompt guiding you through the download process. You can also pass arguments to skip prompts entirely.
 
```
usage: muzlib-cli [-h] [-l LIBRARY_PATH] [-d {album,artist,song}]
              [--artist ARTIST] [--album ALBUM] [--song SONG]
              [--non_interactive]
```
 
## Arguments
 
| Argument | Short | Description |
|---|---|---|
| `--help` | `-h` | Show help message and exit. |
| `--library_path PATH` | `-l` | Root directory to save downloaded music. Defaults to your OS standard Music folder. |
| `--download_type {album,artist,song}` | `-d` | Scope of the download: `artist` (full discography), `album` (specific release), or `song` (single track). |
| `--artist ARTIST` | | Target artist's name. Highly recommended for all download types to ensure accurate search results. |
| `--album ALBUM` | | Target album's title. Use alongside `--artist` when `--download_type` is `album`. |
| `--song SONG` | | Target song's title. Use alongside `--artist` when `--download_type` is `song`. |
| `--non_interactive` | | Bypass all user prompts and automatically download the top search result. Requires `--download_type` to be set. |
 
## Examples
 
### Interactive mode
launches a menu to guide you through the download
```bash
muzlib-cli
```
![Example of usage ](assets/usage.gif)
 
### Download an artist's full discography non-interactively
```bash
muzlib-cli -d artist --artist "Ludwig Göransson" --non_interactive
```
 
### Download a specific album
```bash
muzlib-cli -d album --artist "Ludwig Göransson" --album "Oppenheimer" --non_interactive
```
 
### Download a single song into a custom library folder
```bash
muzlib-cli -l ~/Music -d song --artist "Ludwig Göransson" --song "Can You Hear The Music" --non_interactive
```
 
> [!NOTE]
> `--non_interactive` requires `--download_type` to be specified, otherwise muzlib will exit with an error.
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