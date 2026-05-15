"""Unit tests for the M4A metadata manipulation utilities."""

import base64
from unittest.mock import MagicMock, patch, ANY, PropertyMock
import pytest

from mutagen import MutagenError
from mutagen.mp4 import MP4Cover
from muzlib.tag_utils.m4a import add_tag, get_tag


class TestAddTagM4A:
    """Test suite for the add_tag MP4/M4A manipulation function."""

    @pytest.fixture
    def full_track_info(self):
        """Returns a fully populated track_info dictionary."""
        return {
            'ytm_id': 'xyz123',
            'ytm_title': 'Never Gonna Give You Up (Official)',
            'track_name': 'Never Gonna Give You Up',
            'track_artists': ['Rick Astley'],
            'release_date': '1987',
            'album_artists': ['Rick Astley'],
            'album_name': 'Whenever You Need Somebody',
            'track_number': 1,
            'total_tracks': 10,
            'lyrics': 'We are no strangers to love...',
            'cover': base64.b64encode(b"fake_image_data").decode('utf-8')
        }

    @pytest.fixture
    def minimal_track_info(self):
        """Returns a minimal dictionary with empty optional fields."""
        return {
            'ytm_id': 'xyz123',
            'ytm_title': '',
            'track_name': 'Unknown Song',
            'track_artists': ['Unknown Artist'],
            'release_date': '2020',
            'album_artists': ['Unknown Artist'],
            'album_name': '',
            'track_number': None,
            'total_tracks': None,
            'lyrics': '',
            'cover': ''
        }

    @patch("muzlib.tag_utils.m4a.MP4")
    def test_add_tag_success_all_fields(self, mock_mp4_class, full_track_info):
        """Test that all MP4 atoms are correctly assigned when full data is provided."""

        # Arrange
        mock_audio = MagicMock()
        mock_mp4_class.return_value = mock_audio

        # Act
        add_tag("fake_path.m4a", full_track_info)

        # Assert
        mock_mp4_class.assert_called_once_with("fake_path.m4a")
        mock_audio.delete.assert_called_once()

        assigned_keys = [call.args[0] for call in mock_audio.__setitem__.call_args_list]
        expected_keys = [
            '----:com.apple.iTunes:ytm_id', '----:com.apple.iTunes:ytm_title', 
            '\xa9nam', '\xa9ART', '\xa9day', 'aART', '\xa9alb', 'trkn', '\xa9lyr', 'covr'
        ]

        for key in expected_keys:
            assert key in assigned_keys, f"Expected MP4 atom {key} was not set."

        # Verify specific freeform tag byte encoding
        mock_audio.__setitem__.assert_any_call('----:com.apple.iTunes:ytm_id', [b'xyz123'])

        mock_audio.save.assert_called_once()

    @patch("muzlib.tag_utils.m4a.MP4")
    def test_add_tag_success_minimal_fields(self, mock_mp4_class, minimal_track_info):
        """Test that optional MP4 atoms are skipped when data is empty or None."""

        # Arrange
        mock_audio = MagicMock()
        mock_mp4_class.return_value = mock_audio

        # Act
        add_tag("fake_path.m4a", minimal_track_info)

        # Assert
        assigned_keys = [call.args[0] for call in mock_audio.__setitem__.call_args_list]

        expected_keys = ['----:com.apple.iTunes:ytm_id', '\xa9nam', '\xa9ART', '\xa9day', 'aART']
        for key in expected_keys:
            assert key in assigned_keys

        skipped_keys = ['----:com.apple.iTunes:ytm_title', '\xa9alb', 'trkn', '\xa9lyr', 'covr']
        for key in skipped_keys:
            assert key not in assigned_keys

        mock_audio.save.assert_called_once()

    @patch("builtins.print")
    @patch("muzlib.tag_utils.m4a.MP4")
    def test_add_tag_exception_handling(self, mock_mp4_class, mock_print):
        """Test that it catches file loading errors and aborts safely."""

        # Arrange
        mock_mp4_class.side_effect = MutagenError("Corrupt file data")
        mock_audio = MagicMock()

        # Act
        add_tag("corrupt_file.m4a", {'ytm_id': '123'})

        # Assert
        mock_print.assert_called_once()
        assert "Error loading file corrupt_file.m4a" in mock_print.call_args[0][0]

        # It should exit before deleting or saving
        mock_audio.delete.assert_not_called()
        mock_audio.save.assert_not_called()

    @patch("builtins.print")
    @patch("muzlib.tag_utils.m4a.MP4")
    def test_add_tag_cover_exception_handling(self, mock_mp4_class, mock_print, full_track_info):
        """Test that invalid base64 data for cover art does not crash the function."""
        
        # Arrange
        mock_audio = MagicMock()
        mock_mp4_class.return_value = mock_audio
        full_track_info['cover'] = 'invalid_base64_data!!'

        # Act
        add_tag("fake_path.m4a", full_track_info)

        # Assert
        mock_print.assert_called_once()
        assert "Error embedding cover art" in mock_print.call_args[0][0]
        mock_audio.save.assert_called_once()


class TestGetTagM4A:
    """Test suite for the get_tag MP4/M4A extraction function."""

    @patch("muzlib.tag_utils.m4a.MP4")
    def test_get_tag_success_full_metadata(self, mock_mp4_class):
        """Test extraction when all atoms and cover art are present."""

        # 1. Arrange: Create a mock audio object that behaves like a dict
        mock_audio = MagicMock()

        # MP4 atoms store values in lists
        mock_data = {
            '----:com.apple.iTunes:ytm_id': [b'vid123'],
            '----:com.apple.iTunes:ytm_title': [b'YTM Title'],
            '\xa9nam': ['Song Title'],
            '\xa9ART': ['Artist A', 'Artist B'],
            '\xa9day': ['2024-01-01'],
            '\xa9alb': ['Album Name'],
            'aART': ['Album Artist'],
            'trkn': [(5, 12)],
            '\xa9lyr': ['Sample Lyrics'],
            'covr': [b"fake_binary_image"]
        }

        mock_audio.__contains__.side_effect = mock_data.__contains__
        mock_audio.__getitem__.side_effect = mock_data.__getitem__
        mock_audio.get.side_effect = mock_data.get

        mock_mp4_class.return_value = mock_audio

        # 2. Act
        result = get_tag("fake_path.m4a")

        # 3. Assert
        assert result['ytm_id'] == 'vid123'
        assert result['track_name'] == 'Song Title'
        assert result['track_artists'] == ['Artist A', 'Artist B']
        assert result['track_artists_str'] == 'Artist A, Artist B'
        assert result['release_date'] == '2024'  # Should extract first 4 chars
        assert result['track_number'] == '5'
        assert result['total_tracks'] == '12'
        assert result['lyrics'] == 'Sample Lyrics'
        # Check base64 encoding
        expected_cover = base64.b64encode(b"fake_binary_image").decode('utf-8')
        assert result['cover'] == expected_cover

    @patch("muzlib.tag_utils.m4a.MP4")
    def test_get_tag_empty_file(self, mock_mp4_class):
        """Test that missing atoms return empty strings instead of crashing."""

        # Arrange
        mock_audio = MagicMock()
        mock_audio.__contains__.return_value = False
        mock_audio.get.return_value = []
        mock_mp4_class.return_value = mock_audio

        # Act
        result = get_tag("empty.m4a")

        # Assert
        assert result['track_name'] == ''
        assert result['track_artists'] == []
        assert result['track_artists_str'] == ''
        assert result['release_date'] == ''
        assert result['cover'] == ''

    @patch("builtins.print")
    @patch("muzlib.tag_utils.m4a.MP4")
    def test_get_tag_load_error(self, mock_mp4_class, mock_print):
        """Test behavior when the file cannot be loaded."""

        # Arrange
        mock_mp4_class.side_effect = OSError("File not found or invalid")

        # Act
        result = get_tag("invalid.txt")

        # Assert
        assert not result
        mock_print.assert_called_once()
        assert "Error loading file" in mock_print.call_args[0][0]

    @patch("builtins.print")
    @patch("muzlib.tag_utils.m4a.MP4")
    def test_get_tag_cover_encoding_error(self, mock_mp4_class, mock_print):
        """Test that a failure in cover art encoding doesn't crash the whole function."""

        # Arrange
        mock_audio = MagicMock()
        mock_audio.__contains__.side_effect = lambda k: k == 'covr'
        
        # Give 'covr' something that can't be b64 encoded properly
        mock_audio.__getitem__.side_effect = lambda k: [None] if k == 'covr' else []
        mock_mp4_class.return_value = mock_audio

        # Act
        result = get_tag("cover_error.m4a")

        # Assert
        assert result['cover'] == ''
        print_output = mock_print.call_args[0][0]
        assert "Error encoding cover art" in print_output
