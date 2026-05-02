import re

def trackname_remove_unnecessary(track_name:str) -> str:
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
        >>> trackname_remove_unnecessary("Song Title (feat. Artist B)")
        'Song Title'
        >>> trackname_remove_unnecessary("Another Track [prod. by DJ C]")
        'Another Track'
    """
    name = re.sub(r'\(feat.*?\)|\(ft.*?\)|feat.*|ft.*|\(Feat.*?\)|\(Ft.*?\)|\(prod.*?\)|\[prod.*?\]|\(Prod.*?\)', '', track_name)
    return name.rstrip()

def get_feat_artists(track_name:str) -> list[str]:
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
        >>> get_feat_artists("Cool Song (feat. Artist A & Artist B)")
        ['Artist A', 'Artist B']
        >>> get_feat_artists("Another Track ft. Singer, Rapper")
        ['Singer', 'Rapper']
        >>> get_feat_artists("Solo Track")
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

def sanitize_filename(filename:str) -> str:
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
        >>> sanitize_filename('My "Awesome" Track: Part 1/2?')
        "My ''Awesome'' Track： Part 1／2？"
        >>> sanitize_filename("Title<With>Illegal*Chars|")
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