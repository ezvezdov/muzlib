"""Files utilities for Muzlib."""
import os
import sys
from pathlib import Path
import tempfile

def get_default_music_directory():
    """
    Retrieves the platform-specific default music directory for the 'Muzlib' application.

    This function intelligently determines the correct user Music folder based on 
    the operating system (Linux, macOS, Windows). It queries the Linux XDG user directories
    or Windows Registry to find the exact mapped folder, ensuring accuracy 
    even if the user has customized or moved their default Music folder. If the OS 
    query fails or the platform is unsupported, it safely falls back to a standard 
    '~/Music/Muzlib' structure.

    Returns:
        pathlib.Path: A Path object pointing to the 'Muzlib' folder inside the 
            user's system-defined Music directory.

    Examples:
        >>> get_default_music_directory()
        PosixPath('/home/username/Music/Muzlib')  # Example on Linux/macOS

        >>> get_default_music_directory()
        WindowsPath('C:/Users/Username/Music/Muzlib')  # Example on Windows
    """

    # Linux
    if sys.platform == 'linux':
        import subprocess
        try:
            # Query the standard XDG user directory system
            result = subprocess.check_output(['xdg-user-dir', 'MUSIC'])
            return Path(result.decode('utf-8').strip()) / "Muzlib"
        except Exception:
            pass

    # macOS (Darwin)
    elif sys.platform == 'darwin':
        # macOS heavily enforces the ~/Music structure, so this is safe
        return Path.home() / "Music" / "Muzlib"

    # Windows
    elif sys.platform == 'win32':
        import winreg
        try:
            # Query the Windows Registry for the actual mapped folder
            sub_key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                music_path = winreg.QueryValueEx(key, "My Music")[0]
                return Path(music_path) / "Muzlib"
        except Exception:
            pass

    # Default fallback for anything else
    return Path.home() / "Music" / "Muzlib"

def get_tmp_folder():
    """
    Retrieves or creates a dedicated temporary directory for the 'muzlib' application.

    This function locates the operating system's default temporary storage 
    directory (e.g., '/tmp' on Linux/macOS or 'C:\\...\\Temp' on Windows) and 
    ensures a subdirectory named 'muzlib' exists within it. This keeps 
    application-specific temporary files organized and isolated from other 
    system processes.

    Returns:
        str: The absolute path to the 'muzlib' temporary directory.

    Examples:
        >>> get_tmp_folder()
        '/tmp/muzlib'  # Example output on Linux/macOS
        
        >>> get_tmp_folder()
        'C:\\Users\\Username\\AppData\\Local\\Temp\\muzlib'  # Example output on Windows
    """
    tmp_folder = tempfile.gettempdir()
    muzlib_tmp_folder = os.path.join(tmp_folder, "muzlib")
    os.makedirs(muzlib_tmp_folder, exist_ok=True)

    return muzlib_tmp_folder

def find_audio_files(directory: str) -> list[Path]:
    """
    Recursively searches a directory and its subdirectories for audio files.

    This function scans the specified directory tree and returns a list of 
    all files matching the supported audio extensions. 

    Args:
        directory (str): The root directory path to begin the search.

    Returns:
        list of pathlib.Path: A list of Path objects corresponding to the 
            found audio files. Returns an empty list if no files are found.

    Examples:
        >>> files = find_audio_files("./my_music")
        >>> print(files)
        [PosixPath('my_music/song1.mp3'), PosixPath('my_music/albums/song2.opus')]
    """

    # """"Find audio files in the given directory and its subdirectories."""
    extensions = {'.mp3', '.opus'}

    return [
        p for p in Path(directory).rglob("*")
        if p.suffix.lower() in extensions
    ]
