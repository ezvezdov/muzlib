import os
import re
import json
import time
import base64
import requests
from pathlib import Path
from enum import Enum

import yt_dlp
from ytmusicapi import YTMusic
import questionary

from . import lyrics_utils
from .tag_utils import tag_utils
from . import logging_utils



def _trackname_remove_unnecessary(track_name):
    name = re.sub(r'\(feat.*?\)|\(ft.*?\)|feat.*|ft.*|\(Feat.*?\)|\(Ft.*?\)|\(prod.*?\)|\[prod.*?\]|\(Prod.*?\)', '', track_name)
    return name.rstrip()


def _get_feat_artists(track_name):
    match = re.search(r'\((?:feat|ft)\.*.*?\)|(?:feat|ft)\.*.*', track_name, re.IGNORECASE)

    if match:
        result = re.sub(r'.*?(feat|ft)\.*', '', match.group(0), flags=re.IGNORECASE).strip("() ")

        artists = re.split(r',|\s&\s', result)

        # Clean up whitespace
        artists = [artist.strip() for artist in artists]

        return artists

    return []

def _replace_slash(str):
    return str.replace("/","⁄")

def _sanitize_filename(filename, replacement="_"):
    """
    Remove or replace unsupported characters in a filename.
    :param filename: Original filename.
    :param replacement: Character to replace unsupported characters.
    :return: Sanitized filename.
    """
    # Define invalid characters for different platforms
    # if os.name == 'nt':  # Windows
    #     invalid_chars = r'[\0]'  # Windows-specific invalid characters
        
    filename = re.sub(r'[:]', "：", filename)
    filename = re.sub(r'[?]', "？", filename)
    filename = re.sub(r'[*]', "＊", filename)
    filename = re.sub(r'[<]', "＜", filename)
    filename = re.sub(r'[>]', "＞", filename)
    filename = re.sub(r'[/]', "／", filename)
    filename = re.sub(r'["]', "\'\'", filename)
    filename = re.sub(r'[|]', "∣", filename)

    # else:  # macOS/Linux
    invalid_chars = r'[\0]'
    
    # Replace invalid characters
    sanitized = re.sub(invalid_chars, replacement, filename)
    
    # Handle reserved names in Windows (optional)
    reserved_names = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
                      'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3',
                      'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
    if os.name == 'nt' and sanitized.upper().split('.')[0] in reserved_names:
        sanitized = f"{replacement}{sanitized}"
    
    return sanitized

def _get_image(url, retries=3, delay=2):
    for attempt in range(retries):
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return base64.b64encode(response.content).decode('utf-8')
        else:
            time.sleep(delay)

    logging_utils.logging.warning(f"Failed to download image. Status code: {response.status_code}")
    return {}

def _find_audio_files(directory):
    extensions = {'.mp3', '.opus'}
    
    return [
        p for p in Path(directory).rglob("*") 
        if p.suffix.lower() in extensions
    ]

def _init_track_info():
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
    ARTIST = "artists"
    ALBUM = "albums"
    SONG = "songs"

class Muzlib():
    def __init__(self, library_path, codec="opus", skip_downloaded=False):
        """
        Docstring for __init__
        
        :param library_path: path to the music library
        :param codec: preferred codec for downloaded audio (opus, mp3, m4a)
        :param skip_downloaded: whether to skip already downloaded tracks based on the database
        """

        self.extension = "." + codec.lower()

        self.ydl_opts = {
            'format': 'bestaudio',
            'outtmpl': '%(id)s.%(ext)s',
            'retries': 5,  # Retry 5 times for errors
            'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': codec,
                    'preferredquality': '0', # Best quality
            }],
            'quiet': True,
            'cookiefile': 'assets/cookies.txt'
        }

        self.use_db = skip_downloaded

        self.info_path = '.muzlib'

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

        # Ensure the path ends with a slash (optional)
        self.library_path = os.path.join(self.library_path, '')

        # Create the directory
        try:
            os.makedirs(self.library_path, exist_ok=True)
            logging_utils.logging.debug(f"Folders created successfully at: {self.library_path}")
        except Exception as e:
            logging_utils.logging.error(f"Error creating folders: {e}")

        self.ydl_opts['outtmpl'] = os.path.join(self.library_path, self.ydl_opts['outtmpl'])

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

        
    def _artist_rename(self, artist_name):
        if artist_name in self.artists_rename: return self.artists_rename[artist_name]
        return artist_name
    
    def _get_album_metadata(self, ytm_album_id, single_id=None, single_name=None):
        album_metadata = []

        album_details = self.ytmusic.get_album(ytm_album_id)
        for track in album_details['tracks']:
            track_info = _init_track_info()
            track_info['ytm_id'] = track['videoId']
            track_info['track_name'] = _trackname_remove_unnecessary(track['title'])

            # Single downloading
            if not single_name is None and not single_id is None and len(album_details['tracks']) > 1:
                if track['title'] != single_name and track_info['ytm_id'] != single_id:
                    continue

            track_info['track_artists'] = [_replace_slash(self._artist_rename(artist['name'])) for artist in track['artists']] + _get_feat_artists(track['title'])
            track_info['track_artists_str'] = ", ".join(track_info['track_artists'])
            track_info['release_date'] = album_details['year'] if 'year' in album_details else ''

            # TODO: Set album and track number in singles too
            if album_details['trackCount'] > 1:
                track_info['album_name'] = _trackname_remove_unnecessary(album_details['title'])
                track_info['track_number'] = track['trackNumber']
                track_info['total_tracks'] = album_details['trackCount']

            track_info['album_artists'] = [_replace_slash(self._artist_rename(artist['name'])) for artist in album_details['artists']] + _get_feat_artists(track_info['album_name'])
            track_info['lyrics'] = lyrics_utils.get_lyrics(track_info['track_name'], track_info['track_artists_str'], ytmusic=self.ytmusic, id=track_info['ytm_id'])
            track_info['cover'] = _get_image(album_details['thumbnails'][-1]['url'])
            track_info['ytm_title'] = f"{track_info['track_artists_str']} - {track['title']}"

            # Download the track
            self._download_by_track_info(track_info)

            album_metadata.append(track_info)
        
        return album_metadata
    
    def search(self, search_term, search_type: SearchType):
        return self.ytmusic.search(search_term, filter=search_type.value, limit=20)
    
    def search_artist(self, artist_name):
        return self.search(artist_name, SearchType.ARTIST)
    
    def search_album(self, artist_name, album_name):
        return self.search(f"{artist_name} - {album_name}", SearchType.ALBUM)
    
    def search_song(self, artist_name, track_name):
        return self.search(f"{artist_name} - {track_name}", SearchType.SONG)

    def go_though_search_results(self, search_results, search_type: SearchType):
        for result in search_results:
            if search_type == SearchType.ARTIST:
                full_name = result['artist']
            elif search_type == SearchType.ALBUM:
                album_artists = [artist['name'] for artist in result['artists']]
                album_artists_str = ", ".join(album_artists)
                full_name = album_artists_str + " - " + result['title']
            elif search_type == SearchType.SONG:
                song_artists = [artist['name'] for artist in result['artists']]
                song_artists_str = ", ".join(song_artists)
                full_name = song_artists_str + " - " + result['title']
            else:
                logging_utils.logging.error(f"Invalid search type: {search_type}")
                print(f"Invalid search type: {search_type}")
                return None
            
            if questionary.confirm(f"Is this the {search_type.name} you searched for?\n  {full_name}").ask():
                return result
            
    
    def download_by_search_result(self, search_result, search_type: SearchType):
        if search_type == SearchType.ARTIST:
            self._get_discography_by_artist_id(search_result['browseId'])
        elif search_type == SearchType.ALBUM:
            self._get_album_metadata(search_result['browseId'])
        elif search_type == SearchType.SONG:
            self._get_album_metadata(search_result['album']['id'], single_id=search_result['videoId'], single_name=search_result['title'])
        else:
            logging_utils.logging.error(f"Invalid search type: {search_type}")
            print(f"Invalid search type: {search_type}")

    def _get_artist_id(self, artist_name, download_top_result=False):
        search_results = self.ytmusic.search(artist_name, filter="artists")
        if not search_results: return ''

        for artist in search_results:
            if not download_top_result:
                artist_name = artist['artist']
                answer = input(f"Did you search artist {artist_name}? [y/n]: ")

                # Skip current album
                if answer.lower()[0] != 'y': continue

            return artist['browseId']
    
        return ''

    def _get_discography_by_artist_id(self,artist_id):
        
        artist_details = self.ytmusic.get_artist(artist_id)

        for type in ["albums", "singles"]:
            if not type in artist_details: continue

            albums = artist_details[type]['results']

            if artist_details[type]['browseId']:
                albums = self.ytmusic.get_artist_albums(artist_details[type]['browseId'], params=None, limit=None)
            
            for album in albums:
                self._get_album_metadata(album['browseId'])

    
    def download_artist_discography(self, artist_name, download_top_result=False):
        artist_id = self._get_artist_id(artist_name, download_top_result=download_top_result)
        if not artist_id: return

        print(f"Downloading the complete discography of the artist: {self.artists_rename.get(artist_name, artist_name)}")

        self._get_discography_by_artist_id(artist_id)

    
    def download_album_by_name(self, search_querry, download_top_result=False):
        results = self.ytmusic.search(query=f"{search_querry}", filter="albums", limit=20)

        album = []

        for album in results:
            if not download_top_result:
                album_name = album['title']
                album_artists = [artist['name'] for artist in album['artists']]
                album_artists_str = ", ".join(album_artists)
                album_full_name = album_artists_str + " - " + album_name
                answer = input(f"Did you search album {album_full_name}? [y/n]: ")

                # Skip current album
                if answer.lower()[0] != 'y': continue
            
            self._get_album_metadata(album['browseId'])
            break


    def download_track_by_name(self, search_term, download_top_result=False):
        results = self.ytmusic.search(search_term, filter="songs")

        for song in results:

            if not download_top_result:
                song_name = song['title']
                song_artists = [artist['name'] for artist in song['artists']]
                song_artists_str = ", ".join(song_artists)
                song_full_name = song_artists_str + " - " + song_name
                answer = input(f"Did you search track {song_full_name}? [y/n]: ")

                # Skip current album
                if answer.lower()[0] != 'y': continue

            song_id = song['videoId']
            song_name = song['title']
            self._get_album_metadata(song['album']['id'], single_id=song_id, single_name=song_name)
            break


    def backup_library(self):
        track_metadata = []
        audio_files = _find_audio_files(self.library_path)
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
            
    def restore_library(self, backup_filepath):
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
            self._download_by_track_info(track_info)   

    def _download_by_track_info(self, track_info):
        try:
            id = track_info.get('ytm_id','')
            if not id: return

            if self.use_db and id in self.db: return

            self.__download_track_youtube(id)
            
            file_path = os.path.join(self.library_path, f"{id}{self.extension}")

            # Add tag to the track
            tag_utils.add_tag(file_path,track_info)

            # Rename and move track
            self.__move_downloaded_track(id, track_info)
            
            # Save database
            self.db[id] = track_info['track_artists_str'] + " - " + track_info['track_name']
            self.__write_db()
        except Exception as e:
            missing_path = os.path.join(self.library_path, self.missing_path)

            if os.path.exists(missing_path):
                with open(missing_path, "r", encoding="utf-8") as file:
                    missing_track_metadata = json.load(file)
                missing_track_metadata.append(track_info)
            else:
                missing_track_metadata = [track_info]
            
            json.dump(missing_track_metadata, open(missing_path, "w", encoding="utf-8"), indent=4, ensure_ascii=False)
            logging_utils.logging.error(f"Error downloading track {track_info.get('track_name','Unknown')} with id {track_info.get('ytm_id','Unknown')}: {e}")
            print(f"Error downloading track {track_info.get('track_name','Unknown')} with id {track_info.get('ytm_id','Unknown')}: {e}")            

    def __move_downloaded_track(self, id, track_info):
        file_path = os.path.join(self.library_path, f"{id}{self.extension}")

        # Specify filename
        new_filename = _sanitize_filename(_replace_slash(track_info['track_artists_str'] + " - " + track_info['track_name']))
        if track_info['track_number']:
            new_filename = f"{track_info['track_number']}. {new_filename}"

        artist_dir = _sanitize_filename(track_info['track_artists'][0])

        album_dir = ''
        if track_info['total_tracks']:
            album_dir = _sanitize_filename(_replace_slash(f"[{track_info['release_date']}] {track_info['album_name']}"))

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
        os.rename(file_path, new_path)
        print(f"Successfully downloaded {new_path}")


    def __download_track_youtube(self,track_id):
        # Construct the URL for YouTube Music
        track_url = f"https://music.youtube.com/watch?v={track_id}"

        # Download using yt-dlp
        self.ydl.download([track_url])
    
    def __write_db(self):
        # write database to the db.json file
        with open(self.db_path, "w", encoding="utf-8") as file:
            json.dump(self.db, file, indent=4, ensure_ascii=False)

    def __load_db(self):
        # fetch database from db.json file
        if not os.path.exists(self.db_path) or not os.path.isfile(self.db_path):
            self.__write_db()

        with open(self.db_path, "r", encoding="utf-8") as file:
            self.db = json.load(file)

def main():
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich import print as rprint

    console = Console()

    console.print(Panel.fit("[bold cyan]🎵 Muzlib Downloader[/bold cyan]", border_style="cyan"))

    # Path input with validation
    while True:
        library_path = Prompt.ask("[green]Music library path[/green]")
        if library_path.strip():
            break
        console.print("[red]Path cannot be empty.[/red]")

    # Try to init Muzlib
    try:
        ml = Muzlib(library_path.strip())
    except Exception as e:
        console.print(Panel(f"[red]Could not open library:[/red] {e}", border_style="red"))
        return

    # Interactive menu instead of free-text input
    download_type = questionary.select(
        "What do you want to download?",
        choices=[
            questionary.Choice("Complete discography", value=SearchType.ARTIST),
            questionary.Choice("Specific album",       value=SearchType.ALBUM),
            questionary.Choice("Specific song",       value=SearchType.SONG),
        ]
    ).ask()

    # If user pressed Ctrl+C
    if download_type is None:
        console.print("[yellow]Cancelled.[/yellow]")
        return

    # Ask for artist name in all cases, and album/track name if needed
    artist_name = Prompt.ask("[green]Artist name[/green]").strip()

    search_query = None
    if download_type == SearchType.ARTIST:
        search_query = artist_name
    elif download_type == SearchType.ALBUM:
        album_name = Prompt.ask("[green]Album name[/green]").strip()
        search_query = f"{artist_name} – {album_name}"
    elif download_type == SearchType.SONG:
        track_name = Prompt.ask("[green]Track name[/green]").strip()
        search_query = f"{artist_name} – {track_name}"

        
    search_results = ml.search(search_query, download_type)
    selected_result = ml.go_though_search_results(search_results, download_type)

    with console.status(f"[cyan]Downloading {search_query}…[/cyan]"):
        ml.download_by_search_result(selected_result, download_type)
        console.print(f"[green]✓ Done![/green]")

if __name__ == "__main__":
    main()
