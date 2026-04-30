"""Unit tests for the Muzlib tag dispatcher utilities."""

from unittest.mock import patch
import pytest

# Import the dispatcher function
# Adjust the import path based on your actual file structure
from muzlib.tag_utils.tag_utils import add_tag, get_tag

class TestAddTag:
    """Test suite for the add_tag format dispatcher."""

    @pytest.fixture
    def sample_info(self):
        """Returns a standard track info dictionary for testing."""
        return {
            'track_name': 'Test Song',
            'track_artists': ['Test Artist'],
            'ytm_id': 'abc123'
        }

    @patch("muzlib.tag_utils.mp3.add_tag")
    def test_dispatch_to_mp3(self, mock_mp3_add, sample_info):
        """Test that .mp3 files are routed to the mp3 submodule."""
        path = "music/song.mp3"

        add_tag(path, sample_info)

        # Verify mp3.add_tag was called once with the correct arguments
        mock_mp3_add.assert_called_once_with(path, sample_info)

    @patch("muzlib.tag_utils.opus.add_tag")
    def test_dispatch_to_opus(self, mock_opus_add, sample_info):
        """Test that .opus files are routed to the opus submodule."""
        path = "music/audio.opus"

        add_tag(path, sample_info)

        # Verify opus.add_tag was called once with the correct arguments
        mock_opus_add.assert_called_once_with(path, sample_info)

    @patch("muzlib.tag_utils.mp3.add_tag")
    @patch("muzlib.tag_utils.opus.add_tag")
    def test_unsupported_format_ignored(self, mock_opus_add, mock_mp3_add, sample_info):
        """Test that unsupported extensions do nothing and don't crash."""
        path = "music/report.pdf"

        add_tag(path, sample_info)

        # Neither handler should be called
        mock_mp3_add.assert_not_called()
        mock_opus_add.assert_not_called()

    @patch("muzlib.tag_utils.mp3.add_tag")
    def test_case_sensitivity(self, mock_mp3_add, sample_info):
        """
        Check behavior for uppercase extensions. 
        Note: Your current function uses .endswith('.mp3') which is case-sensitive.
        """
        path = "music/SONG.MP3"

        add_tag(path, sample_info)

        # Based on your current code, .endswith('.mp3') will return False for '.MP3'
        mock_mp3_add.assert_not_called()

class TestGetTag:
    """Test suite for the get_tag format dispatcher."""

    @patch("muzlib.tag_utils.mp3.get_tag")
    def test_get_tag_dispatch_to_mp3(self, mock_mp3_get):
        """Test that .mp3 files are routed to the mp3 submodule and return its result."""
        # Arrange
        path = "music/song.mp3"
        expected_result = {'track_name': 'Test MP3 Song', 'ytm_id': '123'}
        mock_mp3_get.return_value = expected_result

        # Act
        result = get_tag(path)

        # Assert
        mock_mp3_get.assert_called_once_with(path)
        assert result == expected_result

    @patch("muzlib.tag_utils.opus.get_tag")
    def test_get_tag_dispatch_to_opus(self, mock_opus_get):
        """Test that .opus files are routed to the opus submodule and return its result."""
        # Arrange
        path = "music/audio.opus"
        expected_result = {'track_name': 'Test Opus Song', 'ytm_id': '456'}
        mock_opus_get.return_value = expected_result

        # Act
        result = get_tag(path)

        # Assert
        mock_opus_get.assert_called_once_with(path)
        assert result == expected_result

    @patch("muzlib.tag_utils.mp3.get_tag")
    @patch("muzlib.tag_utils.opus.get_tag")
    def test_get_tag_unsupported_format(self, mock_opus_get, mock_mp3_get):
        """Test that unsupported extensions return an empty dictionary."""
        # Arrange
        path = "music/document.pdf"

        # Act
        result = get_tag(path)

        # Assert
        assert not result
        mock_mp3_get.assert_not_called()
        mock_opus_get.assert_not_called()

    @patch("muzlib.tag_utils.mp3.get_tag")
    def test_get_tag_case_sensitivity(self, mock_mp3_get):
        """
        Check behavior for uppercase extensions. 
        Because it uses .endswith('.mp3'), uppercase extensions will fail and return {}.
        """
        # Arrange
        path = "music/SONG.MP3"

        # Act
        result = get_tag(path)

        # Assert
        assert not result
        mock_mp3_get.assert_not_called()
