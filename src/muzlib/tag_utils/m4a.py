"""
M4A (MP4/AAC) metadata extraction and embedding utilities.

This module utilizes the `mutagen` library to read and completely overwrite MP4 
metadata atoms for M4A files. It maps standard application dictionary keys to their 
corresponding iTunes-style MP4 atoms (e.g., '\xa9nam' for title) and safely handles 
freeform tags for custom YouTube Music tracking. It also manages the encoding and 
decoding required to embed base64 cover art.
"""

import base64
from mutagen import MutagenError
from mutagen.mp4 import MP4, MP4Cover

def add_tag(audio_path: str, track_info: dict) -> None:
    """
    Overwrites the metadata tags of an M4A file with the provided track information.

    WARNING: This function is destructive to existing metadata. It completely 
    clears all current atoms on the file before writing the new ones provided 
    in the `track_info` dictionary.

    This function maps standard dictionary keys to MP4 atoms (e.g., '\xa9nam', 
    '\xa9ART'). It embeds custom tags as freeform MP4 tags 
    (----:com.apple.iTunes:<name>) and handles embedding cover art using MP4Cover.

    Args:
        audio_path (str): The file path to the target M4A file.
        track_info (dict): A dictionary containing the new metadata to embed. 
            Expected keys include:
                - 'ytm_id' (str): Custom YouTube Music ID.
                - 'ytm_title' (str): Custom YouTube Music title.
                - 'track_name' (str): Song title.
                - 'track_artists' (list of str): List of track artists.
                - 'album_artists' (list of str): List of album artists.
                - 'album_name' (str): Album title.
                - 'release_date' (str/int): Release date/year.
                - 'lyrics' (str): Lyrics string.
                - 'track_number' (str/int): Track position.
                - 'total_tracks' (str/int): Total tracks on album.
                - 'cover' (str): Base64-encoded string of the album art.

    Returns:
        None: The function modifies and saves the M4A file in-place.
    """

    # Load the M4A/MP4 file
    try:
        audio = MP4(audio_path)
    except (MutagenError, OSError) as e:
        print(f"Error loading file {audio_path}: {e}")
        return

    # Clear all existing tags
    audio.delete()

    # Add or update tags
    if track_info.get('ytm_id'):
        audio["----:com.apple.iTunes:ytm_id"] = [track_info['ytm_id'].encode('utf-8')]
        
    if track_info.get('ytm_title'):
        audio["----:com.apple.iTunes:ytm_title"] = [track_info['ytm_title'].encode('utf-8')]

    audio['\xa9nam'] = [track_info['track_name']]
    audio['\xa9ART'] = track_info['track_artists']
    audio['\xa9day'] = [str(track_info['release_date'])]
    audio['aART'] = track_info['album_artists']

    if track_info.get('album_name'):
        audio['\xa9alb'] = [track_info['album_name']]
        
        # Track number in MP4 is a list containing a tuple: [(track_number, total_tracks)]
        track_num = int(track_info.get('track_number') or 0)
        total_tracks = int(track_info.get('total_tracks') or 0)
        if track_num or total_tracks:
            audio['trkn'] = [(track_num, total_tracks)]

    if track_info.get('lyrics'):
        audio['\xa9lyr'] = [track_info['lyrics']]

    if track_info.get('cover'):
        try:
            cover_data = base64.b64decode(track_info['cover'])
            audio['covr'] = [
                MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)
            ]
        except (TypeError, ValueError) as e:
            print(f"Error embedding cover art: {e}")

    # Save changes
    audio.save()


def get_tag(audio_path: str) -> dict:
    """
    Extracts metadata and MP4 atoms from an M4A file into a structured dictionary.

    This function safely attempts to read an M4A file and parse its standard tags, 
    custom freeform tags, and embedded cover art. MP4 atoms natively store 
    all values as lists, so this function flattens single-value tags while 
    preserving multi-value tags. 

    Args:
        audio_path (str): The file path to the target M4A file.

    Returns:
        dict: A dictionary containing the extracted track information. Returns an 
            empty dictionary `{}` if the file fails to load.
    """

    # Load the M4A/MP4 file
    try:
        audio = MP4(audio_path)
    except (MutagenError, OSError) as e:
        print(f"Error loading file {audio_path}: {e}")
        return {}

    track_info = {}


    def get_first(key, default=''):
        """Return the first item of a list tag or a default value if the tag is missing or empty."""
        return audio[key][0] if key in audio and audio[key] else default

    # Helper to decode bytes from custom freeform tags
    def get_custom(key):
        full_key = f"----:com.apple.iTunes:{key}"
        if full_key in audio and audio[full_key]:
            try:
                return audio[full_key][0].decode('utf-8')
            except UnicodeDecodeError:
                return ''
        return ''

    track_info['ytm_id'] = get_custom('ytm_id')
    track_info['ytm_title'] = get_custom('ytm_title')
    
    track_info['track_name'] = get_first('\xa9nam')
    track_info['track_artists'] = audio.get('\xa9ART', [])
    track_info['track_artists_str'] = ", ".join(track_info['track_artists'])
    
    track_info['album_artists'] = audio.get('aART', [])
    
    date_str = get_first('\xa9day')
    track_info['release_date'] = date_str[:4] if date_str else ''
    
    track_info['album_name'] = get_first('\xa9alb')
    
    trkn = get_first('trkn', (0, 0))
    track_info['track_number'] = str(trkn[0]) if trkn[0] else ''
    track_info['total_tracks'] = str(trkn[1]) if trkn[1] else ''
    
    track_info['lyrics'] = get_first('\xa9lyr')

    # Cover Art
    track_info['cover'] = ''
    if 'covr' in audio and audio['covr']:
        try:
            track_info['cover'] = base64.b64encode(audio['covr'][0]).decode('utf-8')
        except (AttributeError, TypeError) as e:
            print(f"Error encoding cover art: {e}")

    return track_info