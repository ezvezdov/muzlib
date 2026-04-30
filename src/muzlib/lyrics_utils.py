import os
import syncedlyrics

from . import logging_utils
from .tag_utils import tag_utils

def _convert_to_timestamp(ms: int) -> str:
    """
    Converts a duration in milliseconds to a formatted timestamp string.

    This function calculates the minutes, seconds, and remaining milliseconds 
    from the total milliseconds provided, and formats them into a standard 
    "MM:SS.mmm" string with appropriate zero-padding.

    Args:
        ms (int): The total duration in milliseconds.

    Returns:
        str: The formatted timestamp string in "MM:SS.mmm" format.

    Examples:
        >>> _convert_to_timestamp(65432)
        '01:05.432'
        >>> _convert_to_timestamp(9000)
        '00:09.000'
        >>> _convert_to_timestamp(123456)
        '02:03.456'
    """
    ms = int(ms)

    seconds = ms // 1000
    milliseconds = ms % 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02}:{seconds:02}.{milliseconds:03}"


def get_lyrics_ytm(ytmusic, videoId: str):
    """
    Fetches and formats lyrics for a specific YouTube Music track.

    This function queries YouTube Music for the lyrics associated with a given 
    video ID. If lyrics are found, it checks if they include synchronization 
    timestamps. Timestamped lyrics are formatted into standard LRC syntax 
    (e.g., "[01:23.456]Lyric line text"), while unsynchronized lyrics are 
    returned as plain text.

    Args:
        ytmusic (ytmusicapi.YTMusic): An initialized instance of the YTMusic client.
        videoId (str): The unique YouTube Music video ID for the track.

    Returns:
        dict or None: A dictionary containing the lyrics data if found, or 
            None if no lyrics are available for the track.
            The dictionary contains:
                - 'lyrics' (str): The full lyrics string, either plain text 
                  or timestamped lines separated by newlines.
                - 'hasTimestamps' (bool): True if the lyrics are timestamped, 
                  False otherwise.

    Examples:
        >>> get_lyrics_ytm(ytm_client, "dQw4w9WgXcQ")
        {
            'lyrics': '[00:18.000]We\\'re no strangers to love\\n[00:22.000]...',
            'hasTimestamps': True
        }
    """
    
    lyrics_object = {}

    watch_playlist = ytmusic.get_watch_playlist(videoId)

    lyrics_browseId = watch_playlist.get('lyrics',None)
    if lyrics_browseId is None: return None

    lyrics = ytmusic.get_lyrics(lyrics_browseId)


    if lyrics is None: return None

    if lyrics['hasTimestamps']:
        lyrics_object['lyrics'] = "\n".join(f"[{_convert_to_timestamp(line.start_time)}]{line.text}" for line in lyrics['lyrics'])
        lyrics_object['hasTimestamps'] = True
    else:
        lyrics_object['lyrics'] = lyrics['lyrics']
        lyrics_object['hasTimestamps'] = False
    
    return lyrics_object
    

def get_lyrics(track_name: str, artists_names: str, ytmusic=None, id=None) -> str:
    """
    Retrieves the best available lyrics for a track, prioritizing synchronized formats.

    This function uses a cascading fallback strategy to find lyrics:
    1. Synchronized lyrics from YouTube Music (if ytmusic and id are provided).
    2. Synchronized lyrics from external providers (Lrclib, NetEase).
    3. Plain text lyrics from YouTube Music (cached from step 1).
    4. Plain text lyrics from external providers (Genius, Lrclib, NetEase).
    
    It stops and returns the lyrics as soon as a match is found at any step in 
    the hierarchy.

    Args:
        track_name (str): The title of the music track.
        artists_names (str): The name(s) of the artist(s) associated with the track.
        ytmusic (ytmusicapi.YTMusic, optional): An initialized YouTube Music client. 
            Defaults to None.
        id (str, optional): The unique YouTube Music video ID for the track. 
            Defaults to None.

    Returns:
        str or None: The lyrics as a string (either timestamped LRC format or 
            plain text), stripped of trailing whitespace. Returns None if no 
            lyrics could be found across any provider.
    """
    lyrics_object = {}

    # Search for synced lyrics from YTM
    if not ytmusic is None and not id is None:
        lyrics_object = get_lyrics_ytm(ytmusic, id)
        if lyrics_object and lyrics_object['hasTimestamps']:
            logging_utils.logging.debug(f"Lyrics: synchronized lyrics saved for {artists_names} - {track_name}. Source: YTM.")
            return lyrics_object['lyrics'].rstrip()

    # Search for synced lyrics from Lrclib, NetEase
    lrc = syncedlyrics.search(f"{artists_names} {track_name}", providers=['Lrclib', 'NetEase'],enhanced=True)
    if not lrc is None:
        logging_utils.logging.debug(f"Lyrics: synchronized lyrics saved for {artists_names} - {track_name}. Source: Musixmatch, Lrclib, NetEase.")
        return lrc.rstrip()

    # Return plain lyrics from YTM
    if lyrics_object:
        logging_utils.logging.debug(f"Lyrics: plain lyrics saved for {artists_names} - {track_name}. Source: YTM.")
        return lyrics_object['lyrics'].rstrip()

    # Search for plain lyrics from Genius, Lrclib, NetEase
    lrc = syncedlyrics.search(f"{artists_names} {track_name}", providers=['Genius', 'Lrclib', 'NetEase'])
    if not lrc is None:
        logging_utils.logging.debug(f"Lyrics: plain lyrics saved for {artists_names} - {track_name}. Source: Genius, Lrclib, NetEase.")
        return lrc.rstrip()

    # There is no lyrics for this track
    logging_utils.logging.debug(f"Lyrics: there is no lyrics for {artists_names} - {track_name}")
    return None

def add_lyrics(audio_path:str):
    """
    Fetches and embeds lyrics into song file's metadata if they don't already exist.

    This function reads the existing tags (specifically track name and artist) 
    from the provided audio file. If the file lacks this basic identifying 
    information, or if it already contains lyrics, the function logs the 
    event and exits without making changes. Otherwise, it attempts to fetch 
    the best available lyrics and writes them directly back to the file.

    Args:
        audio_path (str): The file path to the target audio file.

    Returns:
        None: This function modifies the audio file in-place and does not 
        return a value.
    """

    # Extract track name (title) and artist
    track_info = tag_utils.get_tag_mp3(audio_path)
    track_name = track_info['track_name']
    artists_names = track_info['track_artists_str']
    
    # Skip if there is no information about track
    if not track_name or not artists_names:
        logging_utils.logging.error("ERROR: Unknown title or Artist!")
        return
    
    #  Lyrics already exists
    if 'lyrics' in track_info and track_info['lyrics']: return

    # Get lyrics
    lrc = get_lyrics(track_name, artists_names)
    
    # There is no lyrics for this track
    if lrc is None: return


    track_info['lyrics'] = lrc

    tag_utils.add_tag_mp3(audio_path,track_info)


def add_lyrics_library(library_path:str) -> None:
    """
    Recursively scans a music library and embeds missing lyrics into all supported audio files.

    This function acts as a bulk-processing utility. It uses `find_audio_files` 
    to locate every valid audio file within the given directory tree. It then 
    iterates through the results, passing each file's path to `add_lyrics` 
    so that lyrics can be fetched and saved directly into the track's metadata.

    Args:
        library_path (str): The absolute or relative path to the root directory 
            of the music library to be processed.

    Returns:
        None: This function processes the audio files in-place and does not 
        return a value.
    """
