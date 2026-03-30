"""Files utilities for Muzlib."""
import sys
from pathlib import Path

def get_default_music_directory():
    """"Get the default music directory for the current platform."""
    # WINDOWS
    if sys.platform == 'win32':
        import winreg
        try:
            # Query the Windows Registry for the actual mapped folder
            sub_key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                music_path = winreg.QueryValueEx(key, "My Music")[0]
                return Path(music_path) / "Muzlib"
        except Exception:
            pass

    # LINUX
    elif sys.platform == 'linux':
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

    # Default fallback for anything else
    return Path.home() / "Music" / "Muzlib"


def find_audio_files(directory):
    """"Find audio files in the given directory and its subdirectories."""
    extensions = {'.mp3', '.opus'}

    return [
        p for p in Path(directory).rglob("*")
        if p.suffix.lower() in extensions
    ]
