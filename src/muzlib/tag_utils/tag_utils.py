"""
Format-agnostic metadata tagging dispatcher.

This module acts as a unified routing utility for extracting and embedding audio 
metadata. It checks the file extension of the target audio file and delegates the 
read/write operations to the appropriate format-specific submodules (`mp3` or `opus`), 
providing a single interface for all tag manipulation in the application.
"""

def add_tag(audio_path:str, track_info:dict) -> None:
    """
    Embeds metadata tags into an audio file by routing to the appropriate format handler.

    This function acts as a dispatcher. It checks the file extension of the 
    provided `audio_path` and delegates the actual tagging logic to either 
    the `mp3` or `opus` submodules. If the file format is unsupported 
    (neither .mp3 nor .opus), the function exits silently without making changes.

    Args:
        audio_path (str): The file path to the target audio file. Must end 
            in either '.mp3' or '.opus' to be processed.
        track_info (dict): A standardized dictionary containing track metadata. 
            It is used consistently across both extraction (get_tag) and embedding 
            (add_tag) functions for both MP3 and Opus files.

            Expected Keys:
                - 'ytm_id' (str): The unique YouTube Music video/track ID.
                - 'ytm_title' (str): The original, unparsed title from YouTube Music.
                - 'track_name' (str): The cleaned title of the song.
                - 'track_artists' (list of str): A list of the individual track artists.
                - 'track_artists_str' (str): A comma-and-space separated string of the 
                track artists (e.g., "Artist A, Artist B").
                - 'release_date' (str): The release date (usually just the 4-digit year).
                - 'album_name' (str): The title of the album.
                - 'album_artists' (list of str): A list of the artists credited for the 
                overall album.
                - 'track_number' (str or int): The position of the track on the album.
                - 'total_tracks' (str or int): The total number of tracks on the album.
                - 'lyrics' (str): The unsynchronized lyrics (or LRC-formatted synced 
                lyrics) as a single string containing newlines.
                - 'cover' (str): A Base64-encoded string of the album artwork (usually 
                JPEG format). Defaults to an empty string if no art is present.

    Returns:
        None: The function delegates the in-place modification of the file and 
        does not return a value.
    """

    if audio_path.endswith('.mp3'):
        from . import mp3
        mp3.add_tag(audio_path, track_info)
    elif audio_path.endswith('.opus'):
        from . import opus
        opus.add_tag(audio_path, track_info)

def get_tag(audio_path:str) -> dict:
    """
    Reads and extracts metadata tags from an audio file based on its format.

    This function acts as a dispatcher. It checks the file extension of the 
    provided `audio_path` and dynamically delegates the metadata extraction 
    to either the `mp3` or `opus` submodules. This lazy-loading approach 
    prevents unnecessary imports. If the file format is unsupported (neither 
    .mp3 nor .opus), the function implicitly returns `None`.

    Args:
        audio_path (str): The file path to the target audio file. Expected 
            to end in either '.mp3' or '.opus'.

    Returns:
        dict: A dictionary containing the extracted track information. Returns an 
            empty dictionary `{}` if the file fails to load. Otherwise, it 
            contains the following keys (defaulting to '' or [] if missing):
                - 'ytm_id' (str): Custom YouTube Music ID.
                - 'ytm_title' (str): Custom YouTube Music title.
                - 'track_name' (str): The song title ('title').
                - 'track_artists' (list of str): List of track artists ('artist').
                - 'track_artists_str' (str): Artists joined by a comma and space.
                - 'album_artists' (list of str): List of album artists ('albumartist').
                - 'release_date' (str): The 4-digit release year ('date').
                - 'album_name' (str): The album title ('album').
                - 'track_number' (str): The track's number on the album ('tracknumber').
                - 'total_tracks' (str): Total number of tracks on the album ('tracktotal').
                - 'lyrics' (str): Lyrics string ('lyrics').
                - 'cover' (str): Base64-encoded string of the album art.

    Examples:
        >>> tags = get_tag("./music/song.mp3")
        >>> print(tags.get('track_name'))
        'Bohemian Rhapsody'
    """

    if audio_path.endswith('.mp3'):
        from . import mp3
        return mp3.get_tag(audio_path)
    if audio_path.endswith('.opus'):
        from . import opus
        return opus.get_tag(audio_path)
    
    return {}