import base64
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TPE2, TALB, TDRC, TRCK, USLT, APIC, TXXX



def add_tag(audio_path: str, track_info: dict) -> None:
    """
    Writes the ID3 metadata tags of an MP3 file with the provided track information.

    WARNING: This function is destructive to existing metadata. It completely 
    clears all current ID3 tags on the file before writing the new ones provided 
    in the `track_info` dictionary. 

    The function writes standard ID3v2 tags (Title, Artist, Album, etc.), custom 
    TXXX tags for YouTube Music IDs, and decodes base64 image data to embed 
    front cover art.

    Args:
        audio_path (str): The file path to the target MP3 file.
        track_info (dict): A dictionary containing the new metadata to embed. 
            Expected keys include:
                - 'ytm_id' (str): YouTube Music ID (required).
                - 'ytm_title' (str): YouTube Music Title (optional).
                - 'track_name' (str): Song title (required).
                - 'track_artists' (list of str): List of artists (required).
                - 'release_date' (str): Release year/date (required).
                - 'album_artists' (list of str): List of album artists (required).
                - 'album_name' (str): Album title (optional).
                - 'track_number' (str/int): Track position (optional).
                - 'total_tracks' (str/int): Total tracks on album (optional).
                - 'lyrics' (str): Unsynchronized lyrics string (optional).
                - 'cover' (str): Base64-encoded string of the album art (optional).

    Returns:
        None: The function modifies and saves the MP3 file in-place.
    """

    # Load the MP3 file
    try:
        audio = MP3(audio_path, ID3=ID3)
    except Exception as e:
        print(f"Error loading file {audio_path}: {e}")
        return
    

    # Clear all existing tags
    audio.delete()

    # Add or update tags
    audio["TXXX:ytm_id"] = TXXX(encoding=3, desc="ytm_id", text=track_info['ytm_id'])

    if track_info['ytm_title']:
        audio["TXXX:ytm_title"] = TXXX(encoding=3, desc="ytm_title", text=track_info['ytm_title'])
    
    audio['TIT2'] = TIT2(encoding=3, text=track_info['track_name'])  # Track Name
    audio['TPE1'] = TPE1(encoding=3, text=track_info['track_artists'])  # Track Artists
    audio['TDRC'] = TDRC(encoding=3, text=track_info['release_date'])  # Release Date
    audio['TPE2'] = TPE2(encoding=3, text=track_info['album_artists'])  # Album Artists


    if track_info['album_name']:
        audio['TALB'] = TALB(encoding=3, text=track_info['album_name'])  # Album Name
        if track_info['track_number']:
            audio['TRCK'] = TRCK(encoding=3, text=f"{track_info['track_number']}/{track_info['total_tracks']}")  # Track Number / Total Tracks
    
    if track_info['lyrics']:
        audio['USLT'] = USLT(encoding=3, lang='XXX', desc='', text=track_info['lyrics'])  # Lyrics

    if track_info['cover']:
        audio['APIC'] = APIC(
                encoding=3,  # UTF-8 encoding
                mime='image/jpeg',  # MIME type
                type=3,  # Cover (front)
                desc='cover',
                data=base64.b64decode(track_info['cover']),  # Image data
            )
        
    # Save changes
    audio.save()


def get_tag(audio_path: str) -> dict:
    """
    Extracts metadata and ID3 tags from an MP3 file into a structured dictionary.

    This function reads standard ID3 tags (like title, artist, and album) as well 
    as custom user-defined tags (specifically YouTube Music IDs and titles). If a 
    specific tag is missing from the file, its corresponding value in the returned 
    dictionary will default to an empty string. Album art is automatically encoded 
    into a base64 string.

    Args:
        audio_path (str): The file path to the target MP3 file.

    Returns:
        dict: A dictionary containing the extracted track information. 
            The dictionary contains the following keys:
                - ytm_id (str): Custom YouTube Music ID (TXXX:ytm_id).
                - ytm_title (str): Custom YouTube Music title (TXXX:ytm_title).
                - track_name (str): The song title (TIT2).
                - track_artists (list of str): List of track artists (TPE1).
                - track_artists_str (str): Artists joined by a comma and space.
                - release_date (str): The release year (TDRC).
                - album_name (str): The album title (TALB).
                - album_artists (list of str): List of album artists (TPE2).
                - track_number (str): The track's number on the album (TRCK).
                - total_tracks (str): Total number of tracks on the album (TRCK).
                - lyrics (str): Unsynchronized lyrics (USLT).
                - cover (str): Base64-encoded string of the album art (APIC:cover).

    Examples:
        >>> tags = get_tag("./music/song.mp3")
        >>> print(tags['track_name'])
        'Bohemian Rhapsody'
        >>> print(tags['track_artists_str'])
        'Queen'
    """

    # Load the MP3 file
    try:
        audio = MP3(audio_path, ID3=ID3)
    except Exception as e:
        print(f"Error loading file {audio_path}: {e}")
        return

    track_info = {}

    # Fetch info from tag
    track_info['ytm_id'] = audio["TXXX:ytm_id"].text[0] if 'TXXX:ytm_id' in audio else '' # YTM id
    track_info['ytm_title'] = audio['TXXX:ytm_title'].text[0] if 'TXXX:ytm_title' in audio else ''
    track_info['track_name'] = audio['TIT2'].text[0] if 'TIT2' in audio else '' # Track Name
    track_info['track_artists'] = audio['TPE1'].text if 'TPE1' in audio else '' # Track Artists
    track_info['track_artists_str'] = ", ".join(track_info['track_artists']) # Track Artists str
    track_info['release_date'] = str(audio['TDRC'].text[0].year) if 'TDRC' in audio else ''  # Release Date
    track_info['album_name'] = audio['TALB'].text[0]  if 'TALB' in audio else '' # Album Name
    track_info['album_artists'] = audio['TPE2'].text if 'TPE2' in audio else '' # Album artist
    track_info['track_number'] = audio['TRCK'][0].split('/')[0] if 'TRCK' in audio else '' # Track Number
    track_info['total_tracks'] = audio['TRCK'][0].split('/')[-1] if 'TRCK' in audio else '' # Total Tracks
    track_info['lyrics'] = audio['USLT::XXX'].text if 'USLT::XXX' in audio else '' # Lyrics
    track_info['cover'] = base64.b64encode(audio['APIC:cover'].data).decode('utf-8') if 'APIC:cover' in audio else ''
    
    return track_info