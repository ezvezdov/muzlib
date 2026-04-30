# File was generated using LLM
import base64
from mutagen.oggopus import OggOpus
from mutagen.flac import Picture

def add_tag(audio_path, track_info):
    """
    Adds or updates Vorbis Comment tags for an Opus file.

    Args:
        audio_path (str): Path to the Opus file.
        track_info (dict): Dictionary containing track metadata.
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


def get_tag(audio_path):
    """
    Reads Vorbis Comment tags from an Opus file.
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
