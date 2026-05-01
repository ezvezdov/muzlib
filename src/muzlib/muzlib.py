"""
Muzlib Downloader: A robust CLI utility for downloading and tagging music from YouTube Music.

This module provides a complete pipeline for searching, downloading, and managing 
a local music library. It leverages `ytmusicapi` to fetch accurate metadata and 
lyrics, `yt-dlp` to handle high-quality audio extraction, and `mutagen` to embed 
rich ID3 or Vorbis tags (including cover art) directly into the downloaded files.

Key Features:
    * Download scopes: Individual songs, full albums, or complete artist discographies.
    * Automatic metadata tagging, including synchronized lyrics and album art.
    * Smart file structuring (Artist/Album/Track) and duplicate detection.
    * Library state management (tracking downloaded files and handling backups).
    * Interactive CLI (via `rich` and `questionary`) and non-interactive automation modes.
"""

import os
import re
import sys
import json
import time
import shutil
import base64
import pathlib
import argparse
from enum import Enum

import requests
import yt_dlp
from ytmusicapi import YTMusic

from . import lyrics_utils
from .tag_utils import tag_utils
from . import logging_utils
from . import files_utils



def _trackname_remove_unnecessary(track_name:str) -> str:
    """
    Cleans a track name by removing common feature and producer text patterns.

    This function strips out variations of "(feat. ...)", "ft.", "(prod. ...)", 
    and similar metadata often appended to song titles. It also removes any 
    resulting trailing whitespace.

    Args:
        track_name (str): The original track name containing potential 
            unnecessary feature or producer tags.

    Returns:
        str: The cleaned track name.
        
    Examples:
        >>> _trackname_remove_unnecessary("Song Title (feat. Artist B)")
        'Song Title'
        >>> _trackname_remove_unnecessary("Another Track [prod. by DJ C]")
        'Another Track'
    """
    name = re.sub(r'\(feat.*?\)|\(ft.*?\)|feat.*|ft.*|\(Feat.*?\)|\(Ft.*?\)|\(prod.*?\)|\[prod.*?\]|\(Prod.*?\)', '', track_name)
    return name.rstrip()


def _get_feat_artists(track_name:str) -> list[str]:
    """
    Extracts a list of featured artists from a given track name.

    This function searches the track name for common "featuring" indicators 
    (such as "feat.", "ft.", "(feat ...)", etc., ignoring case) and parses out 
    the individual artist names. It splits multiple artists separated by 
    commas or ampersands ("&").

    Args:
        track_name (str): The full title of the music track.

    Returns:
        list of str: A list containing the names of the featured artists. 
            Returns an empty list if no featured artists are found.

    Examples:
        >>> _get_feat_artists("Cool Song (feat. Artist A & Artist B)")
        ['Artist A', 'Artist B']
        >>> _get_feat_artists("Another Track ft. Singer, Rapper")
        ['Singer', 'Rapper']
        >>> _get_feat_artists("Solo Track")
        []
    """
    match = re.search(r'\((?:feat|ft)\.*.*?\)|(?:feat|ft)\.*.*', track_name, re.IGNORECASE)

    if match:
        result = re.sub(r'.*?(feat|ft)\.*', '', match.group(0), flags=re.IGNORECASE).strip("() ")

        artists = re.split(r',|\s&\s', result)

        # Clean up whitespace
        artists = [artist.strip() for artist in artists]

        return artists

    return []

def _sanitize_filename(filename:str) -> str:
    """
    Sanitizes a string for use as a safe file or directory name.

    This function replaces characters that are forbidden in most file systems 
    (Linux, Windows, MacOS, Android) with visually similar full-width Unicode equivalents 
    or safe alternatives.

    Args:
        filename (str): The original, unsanitized filename string.

    Returns:
        str: The sanitized filename safe for writing to disk.

    Examples:
        >>> _sanitize_filename('My "Awesome" Track: Part 1/2?')
        "My ''Awesome'' Track： Part 1／2？"
        >>> _sanitize_filename("Title<With>Illegal*Chars|")
        'Title＜With＞Illegal＊Chars∣'
    """
    filename = re.sub(r'[:]', "：", filename)
    filename = re.sub(r'[?]', "？", filename)
    filename = re.sub(r'[*]', "＊", filename)
    filename = re.sub(r'[<]', "＜", filename)
    filename = re.sub(r'[>]', "＞", filename)
    filename = re.sub(r'[/]', "／", filename)
    filename = re.sub(r'["]', "\'\'", filename)
    filename = re.sub(r'[|]', "∣", filename)
    filename = re.sub(r'[\0]', "", filename)

    return filename


def _get_image(url:str, retries=3, delay=1) -> str:
    """
    Downloads an image from a URL and encodes it as a base64 string.

    This function attempts to fetch an image from the provided URL. If the 
    request fails (e.g., a non-200 HTTP status code), it will retry a specified 
    number of times with a delay between each attempt to handle temporary 
    network issues.

    Args:
        url (str): The direct URL to the image resource.
        retries (int, optional): The maximum number of attempted downloads. 
            Defaults to 3.
        delay (int, optional): The wait time in seconds between retry attempts. 
            Defaults to 1.

    Returns:
        str or dict: A base64-encoded string representation of the image if 
            successful. If all retries fail, it returns an empty dictionary `{}`.
    """
    for _ in range(retries):
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return base64.b64encode(response.content).decode('utf-8')

        time.sleep(delay)

    logging_utils.logging.warning(f"Failed to download image. Status code: {response.status_code}")
    return ''


def _init_track_info():
    """
    Initializes and returns a standardized dictionary for storing track metadata.

    This function creates a template dictionary to ensure consistent key structure 
    across the application. All fields are initialized with default empty values 
    (empty strings for text fields and empty lists for artist collections) before 
    being populated with actual data.

    Returns:
        dict: A dictionary template containing the following keys:
            - ytm_id (str): YouTube Music ID.
            - ytm_title (str): YouTube Music title.
            - track_name (str): The song's title.
            - track_artists (list): A list of track artists.
            - track_artists_str (str): Artists joined into a single string.
            - release_date (str): The release date or year.
            - album_name (str): The album's title.
            - album_artists (list): A list of album artists.
            - track_number (str): The track's number on the album.
            - total_tracks (str): Total tracks on the album.
            - lyrics (str): The track's lyrics.
            - cover (str): Album cover art data (typically base64).
    """
    track_info = {}
    track_info['ytm_id'] = ""
    track_info['ytm_title'] = ""
    track_info['track_name'] = ""
    track_info['track_artists'] = []
    track_info['track_artists_str'] = ""
    track_info['release_date'] = ""
    track_info['album_name'] = ""
    track_info['album_artists'] = []
    track_info['track_number'] = ""
    track_info['total_tracks'] = ""
    track_info['lyrics'] = ""
    track_info['cover'] = ""
    return track_info

class SearchType(str, Enum):
    """
    Enumeration defining the permitted search scopes for the music library.

    By inheriting from both `str` and `Enum`, these attributes behave as standard 
    strings. This allows for direct string comparison and seamless JSON serialization 
    while maintaining the strict type safety of an Enum. The values map directly to 
    the filter parameters expected by the underlying music API.

    Attributes:
        ARTIST (str): Represents a search scoped to musical artists. Value: "artists".
        ALBUM (str): Represents a search scoped to music albums. Value: "albums".
        SONG (str): Represents a search scoped to individual songs or tracks. Value: "songs".
        
    Examples:
        >>> SearchType.ARTIST == "artists"
        True
        >>> print(f"Searching for {SearchType.ALBUM}...")
        'Searching for albums...'
    """
    ARTIST = "artists"
    ALBUM = "albums"
    SONG = "songs"

class Muzlib():
    """
    Initializes the Muzlib downloader instance.

    Sets up the YouTube downloader options, database paths, and temporary 
    directories required for downloading and tagging music.

    Args:
        library_path (str): The root directory where downloaded music will be stored.
        codec (str, optional): The preferred audio codec (e.g., "opus", "mp3"). Defaults to "opus".
        skip_downloaded (bool, optional): If True, skips downloading tracks already present in the local database. Defaults to False.
    """
    def __init__(self, library_path: str, codec="opus", skip_downloaded=False):


        self.extension = "." + codec.lower()


        current_dir = os.path.dirname(os.path.abspath(__file__))

        self.ydl_opts = {
            'format': 'bestaudio',
            'outtmpl': '%(id)s.%(ext)s',
            'retries': 5,  # Retry 5 times for errors
            'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': codec,
                    'preferredquality': '0', # Best quality
            }],
            'noprogress': True,
            'quiet': True,
            'no_warnings': True,
            'cookiefile': os.path.join(current_dir, 'assets','cookies.txt')
        }

        self.use_db = skip_downloaded

        self.info_path = '.muzlib'
        self.tmp_path = files_utils.get_tmp_folder()

        self.library_path = library_path
        self.db_path = "db.json"
        self.artists_rename_path = "artists_rename.json"
        self._backup_path_prefix = "muzlib_backup_"
        self.missing_path = "missing.json"

        self._init_library()

        self.db = {}
        self.__load_db()

        self.ytmusic = YTMusic()
        self.ydl = yt_dlp.YoutubeDL(self.ydl_opts)



    def _init_library(self):
        """
        Initializes the library directory structure and required metadata files.

        Creates the main library folder and the `.muzlib` hidden folder. It also 
        initializes the tracking database and the artist renaming JSON files if 
        they do not already exist.
        """

        # Ensure the path ends with a slash (optional)
        self.library_path = os.path.join(self.library_path, '')

        # Create the directory
        try:
            os.makedirs(self.library_path, exist_ok=True)
            logging_utils.logging.debug(f"Folders created successfully at: {self.library_path}")
        except Exception as e:
            logging_utils.logging.error(f"Error creating folders: {e}")

        self.ydl_opts['outtmpl'] = os.path.join(self.tmp_path, self.ydl_opts['outtmpl'])

        # Database path
        self.info_path = os.path.join(self.library_path, self.info_path)
        os.makedirs(self.info_path, exist_ok=True)
        self.db_path = os.path.join(self.info_path, self.db_path)

        # Artists_rename
        self.artists_rename_path = os.path.join(self.info_path, self.artists_rename_path)
        if not os.path.exists(self.artists_rename_path):
            with open(self.artists_rename_path, "w", encoding="utf-8") as file:
                json.dump({}, file, indent=4, ensure_ascii=False)
            self.artists_rename = {}
        else:
            with open(self.artists_rename_path, "r", encoding="utf-8") as file:
                self.artists_rename = json.load(file)


    def _artist_rename(self, artist_name: str) -> str:
        """
        Renames an artist based on the custom mapping in `.muzlib/artists_rename.json`.

        Args:
            artist_name (str): The original artist name fetched from YouTube Music.

        Returns:
            str: The mapped custom artist name if it exists, otherwise the original name.
        """
        return self.artists_rename.get(artist_name, artist_name)

    def _get_album_metadata(self, ytm_album_id: str, single_id: str = None, single_name: str = None) -> dict:
        """
        Generator that yields detailed metadata for each track in an album or single.

        Args:
            ytm_album_id (str): The YouTube Music album browse ID.
            single_id (str, optional): The specific video ID if downloading a single track. Defaults to None.
            single_name (str, optional): The name of the single track. Defaults to None.

        Yields:
            dict: A `track_info` dictionary populated with the metadata for the current track.
        """

        album_details = self.ytmusic.get_album(ytm_album_id)
        for track in album_details['tracks']:
            track_info = _init_track_info()
            track_info['ytm_id'] = track['videoId']
            track_info['track_name'] = _trackname_remove_unnecessary(track['title'])

            # Single downloading
            if not single_name is None and not single_id is None and len(album_details['tracks']) > 1:
                if not track['title'] in single_name and track_info['ytm_id'] != single_id:
                    continue
                # TODO: add handling video clips + downloading songs from albums that have video clips as tracks
                # if track['title'] != single_name and track_info['ytm_id'] != single_id:
                #     continue

            song_artists = [artist['name'].strip() for artist in track['artists']] + _get_feat_artists(track['title'])
            track_info['track_artists'] = [self._artist_rename(artist) for artist in song_artists]
            track_info['track_artists_str'] = ", ".join(track_info['track_artists'])
            track_info['release_date'] = album_details['year'] if 'year' in album_details else ''

            # TODO: Set album and track number in singles too
            if album_details['trackCount'] > 1:
                track_info['album_name'] = _trackname_remove_unnecessary(album_details['title'])
                track_info['track_number'] = track['trackNumber']
                track_info['total_tracks'] = album_details['trackCount']

            album_artists = [artist['name'].strip() for artist in album_details['artists']] + _get_feat_artists(track_info['album_name'])
            track_info['album_artists'] = [self._artist_rename(artist) for artist in album_artists]
            track_info['lyrics'] = lyrics_utils.get_lyrics(track_info['track_name'], track_info['track_artists_str'], ytmusic=self.ytmusic, video_id=track_info['ytm_id'])
            track_info['cover'] = _get_image(album_details['thumbnails'][-1]['url'])
            track_info['ytm_title'] = f"{track_info['track_artists_str']} - {track['title']}"

            yield track_info

    def search(self, search_type: SearchType, *, artist_name: str = "", album_name: str = "", song_name: str = "") -> list[dict]:
        """
        Queries YouTube Music for artists, albums, or specific songs.

        Args:
            search_type (SearchType): The scope of the search (ARTIST, ALBUM, or SONG).
            artist_name (str, optional): The target artist's name. Defaults to "".
            album_name (str, optional): The target album's name. Defaults to "".
            song_name (str, optional): The target song's title. Defaults to "".

        Returns:
            list: A list of search result dictionaries returned by the ytmusicapi.
        """
        search_query = ""
        if search_type == SearchType.ARTIST:
            search_query = artist_name
        elif search_type == SearchType.ALBUM:
            search_query = f"{artist_name} – {album_name}"
        elif search_type == SearchType.SONG:
            search_query = f"{artist_name} – {song_name}"

        return self.ytmusic.search(search_query, filter=search_type.value, limit=20)

    def go_though_search_results(self, search_results: list[dict], search_type: SearchType) -> dict:
        """
        Formats and yields search results based on the search type.

        Updates the 'title' field of each raw API result to include relevant 
        artist information, making it clearer for display in interactive menus.

        Args:
            search_results (list): The raw search results from ytmusicapi.
            search_type (SearchType): The scope of the search performed.

        Yields:
            dict: The formatted search result.
        """
        for result in search_results:
            if search_type == SearchType.ARTIST:
                result['title'] = result['artist']
            elif search_type == SearchType.ALBUM:
                album_artists = [artist['name'] for artist in result['artists']]
                album_artists_str = ", ".join(album_artists)
                result['title'] = album_artists_str + " - " + result['title']
            elif search_type == SearchType.SONG:
                song_artists = [artist['name'] for artist in result['artists']]
                song_artists_str = ", ".join(song_artists)
                result['title'] = song_artists_str + " - " + result['title']
            else:
                logging_utils.logging.error(f"Invalid search type: {search_type}")
                print(f"Invalid search type: {search_type}")
                return None

            yield result

    def get_download_summary(self, search_result:dict, search_type: SearchType) -> int:
        """
        Calculates the total number of tracks to be downloaded based on the search scope.

        Args:
            search_result (dict): The specific search result object selected by the user.
            search_type (SearchType): The scope of the search.

        Returns:
            int: The total count of tracks included in the targeted download.
        """
        track_count = 0

        if search_type == SearchType.ARTIST:
            artist_details = self.ytmusic.get_artist(search_result['browseId'])
            for album_type in ["albums", "singles"]:
                if not album_type in artist_details:
                    continue

                albums = artist_details[album_type]['results']

                if artist_details[album_type]['browseId']:
                    albums = self.ytmusic.get_artist_albums(artist_details[album_type]['browseId'], params=None, limit=None)

                for album in albums:
                    album_details = self.ytmusic.get_album(album['browseId'])
                    track_count += album_details['trackCount']

        elif search_type == SearchType.ALBUM:
            album_details = self.ytmusic.get_album(search_result['browseId'])
            track_count = album_details['trackCount']
        elif search_type == SearchType.SONG:
            track_count = 1

        return track_count


    def get_track_info(self, search_result: dict, search_type: SearchType) -> dict:
        """
        Generator that routes the selected search result to the appropriate 
        metadata extraction method based on the download scope.

        Args:
            search_result (dict): The selected search result object.
            search_type (SearchType): The type of content to extract (ARTIST, ALBUM, SONG).

        Yields:
            dict: The populated `track_info` dictionary for each extracted track.
        """
        if search_type == SearchType.ARTIST:
            yield from self._get_discography_by_artist_id(search_result['browseId'])
        elif search_type == SearchType.ALBUM:
            yield from self._get_album_metadata(search_result['browseId'])
        elif search_type == SearchType.SONG:
            yield from self._get_album_metadata(search_result['album']['id'], single_id=search_result['videoId'], single_name=search_result['title'])
        else:
            logging_utils.logging.error(f"Invalid search type: {search_type}")
            print(f"Invalid search type: {search_type}")

    def _get_discography_by_artist_id(self, artist_id:str) -> dict:
        """
        Generator that yields metadata for an artist's entire discography.

        Iterates through all albums and singles associated with the given artist ID on YouTube Music.

        Args:
            artist_id (str): The YouTube Music artist browse ID.

        Yields:
            dict: A `track_info` dictionary for each track in the artist's discography.
        """
        artist_details = self.ytmusic.get_artist(artist_id)

        for audio_type in ["albums", "singles"]:
            if not audio_type in artist_details:
                continue

            albums = artist_details[audio_type]['results']

            if artist_details[audio_type]['browseId']:
                albums = self.ytmusic.get_artist_albums(artist_details[audio_type]['browseId'], params=None, limit=None)

            for album in albums:
                yield from self._get_album_metadata(album['browseId'])


    def backup_library(self) -> str:
        """
        Creates a JSON backup of the current library's track metadata.

        Scans the library for downloaded audio files, extracts their current tags, 
        and saves them to a timestamped backup file in the hidden `.muzlib` directory.

        Returns:
            str: The filepath of the generated backup JSON file.
        """
        track_metadata = []
        audio_files = files_utils.find_audio_files(self.library_path)
        for audio_path in audio_files:
            track_info = tag_utils.get_tag(str(audio_path))

            audio_rpath = os.path.relpath(str(audio_path), start=self.library_path)
            name, ext = os.path.splitext(audio_rpath)
            track_info['path'] = name

            track_metadata.append(track_info)


        formatted_timestamp = time.strftime('%Y%m%d%H%M%S', time.localtime())
        backup_path = os.path.join(self.info_path, f'{self._backup_path_prefix}{formatted_timestamp}.json')

        with open(backup_path, "w", encoding="utf-8") as file:
            json.dump(track_metadata, file, indent=4, ensure_ascii=False)

        return backup_path

    def restore_library(self, backup_filepath: str):
        """
        Restores music library from a backup file.

        Args:
            backup_filepath (str): The absolute or relative path to the backup JSON file.
        """
        if not os.path.exists(backup_filepath):
            print(f"File {backup_filepath} doesn't exist.")
            return
        if not os.path.isfile(backup_filepath):
            print(f"File {backup_filepath} is directory.")
            return

        track_metadata = []
        with open(backup_filepath, "r", encoding="utf-8") as file:
            track_metadata = json.load(file)

        for track_info in track_metadata:
            self.download_by_track_info(track_info)

    def download_by_track_info(self, track_info: dict):
        """
        Downloads a track using yt-dlp, applies ID3/Vorbis tags, and moves it 
        to the structured library folder.

        If the download fails, the track is logged in a `missing.json` file 
        for future review.

        Args:
            track_info (dict): The populated metadata dictionary for the target track.

        Returns:
            str or None: The final saved path of the audio file, or None if skipped/failed.
        """
        try:
            track_id = track_info.get('ytm_id','')
            if not track_id:
                return None

            if self.use_db and track_id in self.db:
                return None

            self.__download_track_youtube(track_id)

            file_path = os.path.join(self.tmp_path, f"{track_id}{self.extension}")

            # Add tag to the track
            tag_utils.add_tag(file_path,track_info)

            # Rename and move track
            new_path = self.__move_downloaded_track(track_id, track_info)

            # Save database
            self.db[track_id] = track_info['track_artists_str'] + " - " + track_info['track_name']
            self.__write_db()

            return new_path
        except Exception as e:
            missing_path = os.path.join(self.library_path, self.missing_path)

            if os.path.exists(missing_path):
                with open(missing_path, "r", encoding="utf-8") as file:
                    missing_track_metadata = json.load(file)
                missing_track_metadata.append(track_info)
            else:
                missing_track_metadata = [track_info]

            with open(missing_path, "w", encoding="utf-8") as file:
                json.dump(missing_track_metadata, file, indent=4, ensure_ascii=False)

            logging_utils.logging.error(f"Error downloading track {track_info.get('track_name','Unknown')} with id {track_info.get('ytm_id','Unknown')}: {e}")
            print(f"Error downloading track {track_info.get('track_name','Unknown')} with id {track_info.get('ytm_id','Unknown')}: {e}")

    def __move_downloaded_track(self, track_id: str, track_info: dict) -> str:
        """
        Moves and renames a downloaded track from the temp folder to its final location.

        Formats the filename and creates nested artist and album directories based on 
        the track metadata. Handles duplicates by placing them in a 'DUPLICATE' folder.

        Args:
            track_id (str): The YouTube Music ID used for the temporary filename.
            track_info (dict): The track's metadata to determine the folder structure.

        Returns:
            str: The final destination path of the sanitized file.
        """
        file_path = os.path.join(self.tmp_path, f"{track_id}{self.extension}")

        # Specify filename
        new_filename = _sanitize_filename(track_info['track_artists_str'] + " - " + track_info['track_name'])
        if track_info['track_number']:
            new_filename = f"{track_info['track_number']}. {new_filename}"

        artist_dir = _sanitize_filename(track_info['track_artists'][0])

        album_dir = ''
        if track_info['total_tracks']:
            album_dir = _sanitize_filename(f"[{track_info['release_date']}] {track_info['album_name']}")

        # Join path components
        new_path = os.path.join(artist_dir, album_dir, new_filename)

        # If file exists
        if os.path.exists(os.path.join(self.library_path,new_path + self.extension)):
            new_path = os.path.join("DUPLICATE", new_path)

        # If there is specified path in track_info
        if 'path' in track_info:
            new_path = os.path.normpath(track_info['path'])

        new_path = os.path.join(self.library_path, new_path + self.extension)

        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        shutil.move(file_path, new_path)

        return new_path


    def __download_track_youtube(self,track_id):
        """
        Executes the yt-dlp download for a specific YouTube Music track ID.

        Args:
            track_id (str): The unique YouTube Music video/track ID.
        """

        # Construct the URL for YouTube Music
        track_url = f"https://music.youtube.com/watch?v={track_id}"

        # Download using yt-dlp
        self.ydl.download([track_url])

    def __write_db(self):
        """
        Saves the current state of the downloaded tracks dictionary to the `.muzlib/db.json` file.
        """
        # write database to the db.json file
        with open(self.db_path, "w", encoding="utf-8") as file:
            json.dump(self.db, file, indent=4, ensure_ascii=False)

    def __load_db(self):
        """
        Loads the downloaded tracks database from `.muzlib/db.json`, creating the file if it doesn't exist.
        """
        # fetch database from db.json file
        if not os.path.exists(self.db_path) or not os.path.isfile(self.db_path):
            self.__write_db()

        with open(self.db_path, "r", encoding="utf-8") as file:
            self.db = json.load(file)

def main():
    """
    Main CLI entry point for the Muzlib Downloader application.

    This function parses command-line arguments using `argparse`, sets up a rich 
    terminal UI, prompts the user for interactive selections (unless non-interactive 
    mode is triggered), and orchestrates the search and download progress loops.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, ProgressColumn
    from rich.text import Text
    import questionary

    parser = argparse.ArgumentParser(description="Muzlib Downloader")
    parser.add_argument("-l", "--library_path", type=str, default="",
        help="Root directory to save downloaded music. Defaults to your OS standard Music folder.")
    parser.add_argument("-d", "--download_type", type=str, choices=['album', 'artist', 'song'],
        help="Scope of the download: 'artist' (full discography), 'album' (specific release), or 'song' (single track).")
    parser.add_argument("--artist", type=str, default="",
        help="Target artist's name. Highly recommended for all download types to ensure accurate search results.")
    parser.add_argument("--album", type=str, default="",
        help="Target album's title. Use alongside --artist when --download_type is 'album'.")
    parser.add_argument("--song", type=str, default="",
        help="Target song's title. Use alongside --artist when --download_type is 'song'.")
    parser.add_argument("--non_interactive", action="store_true",
        help="Bypass all user prompts and automatically download the top search result. Requires --download_type to be set.")
    args = parser.parse_args()

    if args.non_interactive and not args.download_type:
        print("Error: --non_interactive flag requires at least --download_type to be specified.")
        sys.exit(1)


    console = Console()

    console.print(Panel.fit("[bold cyan]🎵 Muzlib Downloader[/bold cyan]", border_style="cyan"))

    # Path input with validation
    default_music_dir = str(files_utils.get_default_music_directory())
    if not args.library_path and not args.non_interactive:
        while True:
            library_path = Prompt.ask("[green]Music library path[/green]", default=default_music_dir)
            if library_path.strip():
                break
            console.print("[red]Path cannot be empty.[/red]")
    else:
        library_path = args.library_path if args.library_path else default_music_dir

    # Try to init Muzlib
    try:
        ml = Muzlib(library_path.strip())
    except Exception as e:
        console.print(Panel(f"[red]Could not open library:[/red] {e}", border_style="red"))
        return

    # Interactive menu instead of free-text input
    if not args.download_type:
        search_type = questionary.select(
            "What do you want to download?",
            choices=[
                questionary.Choice("Complete discography", value=SearchType.ARTIST),
                questionary.Choice("Specific album",       value=SearchType.ALBUM),
                questionary.Choice("Specific song",       value=SearchType.SONG),
            ]
        ).ask()

        # If user pressed Ctrl+C
        if search_type is None:
            console.print("[yellow]Cancelled.[/yellow]")
            return
    else:
        search_type = SearchType(f"{args.download_type}s")

    artist_name, album_name, song_name = args.artist, args.album, args.song

    # Ask for artist name in all cases, and album/track name if needed
    if not args.non_interactive:
        if search_type in {SearchType.ARTIST, SearchType.ALBUM, SearchType.SONG} and not artist_name:
            artist_name = Prompt.ask("[green]Artist name[/green]")
        if search_type == SearchType.ALBUM and not album_name:
            album_name = Prompt.ask("[green]Album name[/green]")
        if search_type == SearchType.SONG and not song_name:
            song_name = Prompt.ask("[green]Track name[/green]")

    # Post-process inputs
    artist_name = artist_name.strip()
    album_name = album_name.strip()
    song_name = song_name.strip()


    search_results = ml.search(search_type, artist_name=artist_name, album_name=album_name, song_name=song_name)

    selected_result = None
    for selected_result in ml.go_though_search_results(search_results, search_type):
        if args.non_interactive:
            break
        if questionary.confirm(f"Is this the {search_type.name.lower()} you searched for?\n  {selected_result['title']}").ask():
            break

    with console.status("[cyan]Retrieving information…[/cyan]"):
        download_summary = ml.get_download_summary(selected_result, search_type)

    class TimeColumn(ProgressColumn):
        """
        A custom Rich progress column that displays elapsed and remaining time.

        This column formats the task's time metrics into a single string showing 
        both the elapsed time and the estimated time remaining in an "H:MM:SS" format. 
        The output is rendered as colored text.

        Format:
            [Elapsed Time < Remaining Time]
            Example: [0:01:45<0:00:15]

        Methods:
            render(task): Extracts and formats the time metrics from a Rich Task object.
        """
        def render(self, task):
            elapsed = task.finished_time if task.finished else task.elapsed
            remaining = task.time_remaining

            elapsed_str = f"{int(elapsed // 3600):01}:{int((elapsed % 3600) // 60):02}:{int(elapsed % 60):02}" if elapsed else "0:00:00"
            remaining_str = f"{int(remaining // 3600):01}:{int((remaining % 3600) // 60):02}:{int(remaining % 60):02}" if remaining else "?"

            return Text(f"[{elapsed_str}<{remaining_str}]", style="green")

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("[cyan][{task.completed}/{task.total}]"),
        TimeColumn(),
        TextColumn("[dim][{task.fields[track_name]}]"),
    ) as progress:
        task = progress.add_task("Downloading...", total=download_summary, track_name="")

        common_path = None
        for track_info in ml.get_track_info(selected_result, search_type):
            song_name = f"{track_info['track_artists_str']} - {track_info['track_name']}"
            progress.update(task, track_name=song_name)

            song_path_str = ml.download_by_track_info(track_info)

            song_path = pathlib.Path(song_path_str)
            song_uri = pathlib.Path(song_path).as_uri()
            progress.print(f"[green]Downloaded:[/green] [link={song_uri}]{song_name}[/link]")

            progress.update(task, advance=1, track_name="")

            if common_path is None:
                common_path = str(song_path.parent)
            else:
                common_path = os.path.commonpath([common_path, str(song_path.parent)])


        progress.update(task, track_name="Done!")

    common_uri = pathlib.Path(common_path).as_uri()
    console.print(f"Files are stored at [magenta][link={common_uri}]{common_path}[/link][/magenta]", highlight=False)
    console.print("[green]✓ Done![/green]")

if __name__ == "__main__":
    main()
