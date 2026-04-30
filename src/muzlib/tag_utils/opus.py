import base64
from mutagen.oggopus import OggOpus
from mutagen.flac import Picture

def add_tag(audio_path:str, track_info:dict) -> None:
    """
    Overwrites the metadata tags of an Ogg Opus file with the provided track information.

    WARNING: This function is destructive to existing metadata. It completely 
    clears all current Vorbis comments on the file before writing the new ones 
    provided in the `track_info` dictionary.

    This function maps standard dictionary keys to Vorbis comment fields (e.g., 
    'title', 'artist', 'album'). It also embeds custom tags for YouTube Music 
    IDs and handles the specialized base64 encoding required to embed cover art 
    into an Ogg/FLAC `metadata_block_picture` field.

    Args:
        audio_path (str): The file path to the target Ogg Opus file.
        track_info (dict): A dictionary containing the new metadata to embed. 
            Expected keys include:
                - 'ytm_id' (str): Custom YouTube Music ID.
                - 'ytm_title' (str): Custom YouTube Music title.
                - 'track_name' (str): Song title ('title').
                - 'track_artists' (list of str): List of track artists ('artist').
                - 'album_artists' (list of str): List of album artists ('albumartist').
                - 'album_name' (str): Album title ('album').
                - 'release_date' (str/int): Release date/year ('date').
                - 'lyrics' (str): Lyrics string ('lyrics').
                - 'track_number' (str/int): Track position ('tracknumber').
                - 'total_tracks' (str/int): Total tracks on album ('tracktotal').
                - 'cover' (str): Base64-encoded string of the album art.

    Returns:
        None: The function modifies and saves the Opus file in-place. It will 
        print an error to the console and return early if the file cannot be loaded.
    """
    
    # Load the Opus file
    try:
        audio = OggOpus(audio_path)
    except Exception as e:
        print(f"Error loading file {audio_path}: {e}")
        return


    # Clear all existing tags
    audio.delete()

    # Reload to ensure clean tag block
    audio = OggOpus(audio_path)

    if track_info.get('ytm_id'):
        audio['ytm_id'] = str(track_info['ytm_id'])

    if track_info.get('ytm_title'):
        audio['ytm_title'] = str(track_info['ytm_title'])

    if track_info.get('track_name'):
        audio['title'] = track_info['track_name']

    if track_info.get('track_artists'):
        audio['artist'] = track_info['track_artists']

    if track_info.get('album_artists'):
        audio['albumartist'] = track_info['album_artists']

    if track_info.get('album_name'):
        audio['album'] = track_info['album_name']

    if track_info.get('release_date'):
        audio['date'] = str(track_info['release_date'])

    if track_info.get('lyrics'):
        audio['lyrics'] = track_info['lyrics']

    if track_info.get('track_number'):
        audio['tracknumber'] = str(track_info['track_number'])

    if track_info.get('total_tracks'):
        audio['tracktotal'] = str(track_info['total_tracks'])

    if track_info.get('cover'):
        try:
            picture = Picture()
            picture.data = base64.b64decode(track_info['cover'])
            picture.type = 3  # Cover (front)
            picture.mime = "image/jpeg"
            picture.desc = "cover"
            picture.width = 0
            picture.height = 0
            picture.depth = 0

            picture_data = picture.write()
            encoded_data = base64.b64encode(picture_data).decode("ascii")

            audio["metadata_block_picture"] = [encoded_data]
        except Exception as e:
            print(f"Error embedding art: {e}")

    # Save changes
    audio.save()


def get_tag(audio_path:str) -> dict:
    """
    Extracts metadata and Vorbis comments from an Ogg Opus file into a structured dictionary.

    This function safely attempts to read an Opus file and parse its standard tags 
    (like title, artist, and album), custom tags (like YouTube Music IDs), and 
    embedded cover art. Since Vorbis comments natively store all values as lists, 
    this function flattens single-value tags (like title or ID) while preserving 
    multi-value tags (like artists). If the file cannot be read, it safely 
    returns an empty dictionary.

    Args:
        audio_path (str): The file path to the target Ogg Opus file.

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
    """

    # Load the Opus file
    try:
        audio = OggOpus(audio_path)
    except Exception:
        return {}

    track_info = {}
    tags = audio.tags if audio.tags else {}

    # Helper to safely get the first item of a list (Mutagen returns lists for all Vorbis tags)
    def get_first(key):
        return tags[key][0] if key in tags else ''

    track_info['ytm_id'] = get_first('ytm_id')
    track_info['ytm_title'] = get_first('ytm_title')
    track_info['track_name'] = get_first('title')
    track_info['track_artists'] = tags['artist'] if 'artist' in tags else []
    track_info['track_artists_str'] = ", ".join(track_info['track_artists'])
    track_info['album_artists'] = tags['albumartist'] if 'albumartist' in tags else []

    date_str = get_first('date')
    track_info['release_date'] = date_str[:4] if date_str else ''

    track_info['album_name'] = get_first('album')
    track_info['track_number'] = get_first('tracknumber')
    track_info['total_tracks'] = get_first('tracktotal')
    track_info['lyrics'] = get_first('lyrics')

    # Cover Art
    track_info['cover'] = ''
    if 'metadata_block_picture' in tags:
        try:
            track_info['cover'] = base64.b64encode(Picture(base64.b64decode(tags['metadata_block_picture'][0])).data).decode('utf-8')
        except Exception as e:
            print(f"Error encoding cover art: {e}")

    return track_info
