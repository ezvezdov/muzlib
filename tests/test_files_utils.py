import os
import sys
import pytest
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from muzlib.files_utils import get_default_music_directory, find_audio_files, get_tmp_folder


class TestGetDefaultMusicDirectory:
    """Test suite for OS-specific default music directory retrieval."""

    # ---------------------------------------------------------
    # LINUX TESTS
    # ---------------------------------------------------------
    @patch("muzlib.files_utils.sys.platform", "linux")
    @patch("subprocess.check_output")
    def test_linux_success(self, mock_check_output):
        """Test Linux behavior when XDG user directory is successfully found."""
        # Arrange: subprocess returns bytes, just like the real OS call
        mock_check_output.return_value = b"/mocked/linux/music\n"
        
        # Act
        result = get_default_music_directory()
        
        # Assert
        assert result == Path("/mocked/linux/music/Muzlib")
        mock_check_output.assert_called_once_with(['xdg-user-dir', 'MUSIC'])

    @patch("muzlib.files_utils.sys.platform", "linux")
    @patch("subprocess.check_output")
    @patch("muzlib.files_utils.Path.home")
    def test_linux_fallback_on_exception(self, mock_path_home, mock_check_output):
        """Test Linux fallback if the XDG command fails or isn't installed."""
        # Arrange
        mock_check_output.side_effect = Exception("xdg-user-dir command not found")
        mock_path_home.return_value = Path("/fake/home")
        
        # Act
        result = get_default_music_directory()
        
        # Assert
        assert result == Path("/fake/home/Music/Muzlib")

    # ---------------------------------------------------------
    # MACOS TESTS
    # ---------------------------------------------------------
    @patch("muzlib.files_utils.sys.platform", "darwin")
    @patch("muzlib.files_utils.Path.home")
    def test_macos_success(self, mock_path_home):
        """Test macOS behavior which safely defaults to the home directory."""
        # Arrange
        mock_path_home.return_value = Path("/Users/FakeUser")
        
        # Act
        result = get_default_music_directory()
        
        # Assert
        assert result == Path("/Users/FakeUser/Music/Muzlib")

    # ---------------------------------------------------------
    # WINDOWS TESTS
    # ---------------------------------------------------------
    @patch("muzlib.files_utils.sys.platform", "win32")
    @patch.dict("sys.modules", {"winreg": MagicMock()})
    def test_windows_success(self):
        """Test Windows behavior when the Registry key is successfully read."""
        # Arrange: Grab the fake winreg module we just injected into sys.modules
        mock_winreg = sys.modules["winreg"]
        
        # Mock the context manager (the 'with' statement) and the registry query
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = ("C:/Mocked/Windows/Music", 1)
        
        # Act
        result = get_default_music_directory()

        expected_path = Path("C:/Mocked/Windows/Music") / "Muzlib"

        # Assert
        assert result == expected_path
        mock_winreg.OpenKey.assert_called_once()
        mock_winreg.QueryValueEx.assert_called_once_with(mock_key, "My Music")

    @patch("muzlib.files_utils.sys.platform", "win32")
    @patch.dict("sys.modules", {"winreg": MagicMock()})
    @patch("muzlib.files_utils.Path.home")
    def test_windows_fallback_on_exception(self, mock_path_home):
        """Test Windows fallback if reading the Registry fails."""
        # Arrange
        mock_winreg = sys.modules["winreg"]
        mock_winreg.OpenKey.side_effect = Exception("Registry key not found")
        mock_path_home.return_value = Path("C:/Users/FakeUser")
        
        # Act
        result = get_default_music_directory()
        
        # Assert
        assert result == Path("C:/Users/FakeUser/Music/Muzlib")

    # ---------------------------------------------------------
    # UNKNOWN OS TEST
    # ---------------------------------------------------------
    @patch("muzlib.files_utils.sys.platform", "freebsd")
    @patch("muzlib.files_utils.Path.home")
    def test_unknown_os_fallback(self, mock_path_home):
        """Test fallback behavior for unsupported operating systems."""
        # Arrange
        mock_path_home.return_value = Path("/fake/home")
        
        # Act
        result = get_default_music_directory()
        
        # Assert
        assert result == Path("/fake/home/Music/Muzlib")


class TestGetTmpFolder:
    """Test suite for the get_tmp_folder function."""

    # ---------------------------------------------------------
    # THE MOCKING TEST (Unit Test)
    # ---------------------------------------------------------
    @patch("os.makedirs")
    @patch("tempfile.gettempdir")
    def test_get_tmp_folder_logic(self, mock_gettempdir, mock_makedirs):
        """Test that the function calculates the right path and calls os.makedirs."""
        
        # Arrange: Fake the system's temp directory path
        fake_temp_dir = '/fake/sys/tmp' if os.name == 'posix' else 'C:\\fake\\temp'
        mock_gettempdir.return_value = fake_temp_dir
        expected_path = os.path.join(fake_temp_dir, 'muzlib')
        
        # Act
        result = get_tmp_folder()
        
        # Assert
        assert result == expected_path
        mock_makedirs.assert_called_once_with(expected_path, exist_ok=True)

    # ---------------------------------------------------------
    # THE FILE SYSTEM TEST (Integration Test)
    # ---------------------------------------------------------
    def test_get_tmp_folder_creation(self):
        """Test that the directory is actually created on the file system."""
        
        # Act
        result_path = get_tmp_folder()

        # Assert
        assert isinstance(result_path, str)
        assert os.path.basename(result_path) == "muzlib"
        assert os.path.exists(result_path), "The folder was not created."
        assert os.path.isdir(result_path), "The path exists but is not a directory."

        # Cleanup: Remove the folder after testing so we don't leave junk behind
        shutil.rmtree(result_path, ignore_errors=True)


class TestFindAudioFiles:
    """Test suite for the find_audio_files function."""

    def test_find_audio_files_with_matches(self, tmp_path):
        """Test that it correctly finds .mp3 and .opus files."""

        # Set up a temporary directory with various files
        (tmp_path / "song1.mp3").touch()
        (tmp_path / "song2.opus").touch()
        (tmp_path / "ignore_me.txt").touch()  # Should be ignored
        
        # Create a subdirectory with more files
        sub_dir = tmp_path / "albums"
        sub_dir.mkdir()
        (sub_dir / "song3.mp3").touch()
        (sub_dir / "cover.jpg").touch()       # Should be ignored
        (sub_dir / "song4.OPUS").touch()      # Should handle uppercase extension

        # Run the function on the temporary directory
        result = find_audio_files(str(tmp_path))

        assert len(result) == 4
        assert (tmp_path / "song1.mp3") in result
        assert (tmp_path / "song2.opus") in result
        assert (sub_dir / "song3.mp3") in result
        assert (sub_dir / "song4.OPUS") in result

    def test_find_audio_files_empty_directory(self, tmp_path):
        """Test behavior when the directory has no matching files."""

        # Setup directory with no audio files
        (tmp_path / "document.pdf").touch()
        
        assert find_audio_files(str(tmp_path)) == []

    def test_find_audio_files_nonexistent_directory(self):
        """Test behavior with a directory that doesn't exist."""

        assert find_audio_files("/path/that/definitely/does/not/exist_12345") == []