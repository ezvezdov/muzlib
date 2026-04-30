import pytest
import base64
from unittest.mock import MagicMock, patch, ANY, PropertyMock

from muzlib.tag_utils.mp3 import add_tag, get_tag

class TestAddTagMP3:
    """Test suite for the add_tag ID3 manipulation function."""

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

    @patch("os.path.exists")
    @patch("muzlib.tag_utils.mp3.MP3")
    def test_add_tag_success_all_fields(self, mock_mp3_class, mock_exists, full_track_info):
        """Test that all ID3 tags are correctly assigned when full data is provided."""
        
        # Arrange
        mock_exists.return_value = True  # Fake the file existing on disk
        mock_audio = MagicMock()
        mock_mp3_class.return_value = mock_audio

        # Act
        add_tag("fake_path.mp3", full_track_info)

        # Assert
        mock_mp3_class.assert_called_once_with("fake_path.mp3", ID3=ANY)
        mock_audio.delete.assert_called_once()

        assigned_keys = [call.args[0] for call in mock_audio.__setitem__.call_args_list]
        expected_keys = [
            'TXXX:ytm_id', 'TXXX:ytm_title', 'TIT2', 'TPE1', 'TDRC', 
            'TPE2', 'TALB', 'TRCK', 'USLT', 'APIC'
        ]
        
        for key in expected_keys:
            assert key in assigned_keys, f"Expected ID3 frame {key} was not set."

        mock_audio.save.assert_called_once()

    @patch("os.path.exists")
    @patch("muzlib.tag_utils.mp3.MP3")
    def test_add_tag_success_minimal_fields(self, mock_mp3_class, mock_exists, minimal_track_info):
        """Test that optional ID3 tags are skipped when data is empty or None."""
        
        # Arrange
        mock_exists.return_value = True
        mock_audio = MagicMock()
        mock_mp3_class.return_value = mock_audio

        # Act
        add_tag("fake_path.mp3", minimal_track_info)

        # Assert
        assigned_keys = [call.args[0] for call in mock_audio.__setitem__.call_args_list]
        
        expected_keys = ['TXXX:ytm_id', 'TIT2', 'TPE1', 'TDRC', 'TPE2']
        for key in expected_keys:
            assert key in assigned_keys
            
        skipped_keys = ['TXXX:ytm_title', 'TALB', 'TRCK', 'USLT', 'APIC']
        for key in skipped_keys:
            assert key not in assigned_keys

        mock_audio.save.assert_called_once()

    @patch("builtins.print")
    @patch("os.path.exists")
    @patch("muzlib.tag_utils.mp3.MP3")
    def test_add_tag_exception_handling(self, mock_mp3_class, mock_exists, mock_print):
        """Test that it catches file loading errors (like corrupt files) and aborts safely."""
        
        # Arrange
        mock_exists.return_value = True  # File exists...
        mock_mp3_class.side_effect = Exception("Corrupt file data")  # ...but it's corrupted!
        mock_audio = MagicMock()

        # Act
        add_tag("corrupt_file.mp3", {'ytm_id': '123'})

        # Assert
        mock_print.assert_called_once()
        assert "Error loading file corrupt_file.mp3" in mock_print.call_args[0][0]
        
        # It should exit before deleting or saving
        mock_audio.delete.assert_not_called()
        mock_audio.save.assert_not_called()

class TestGetTagMP3:
    """Test suite for the get_tag ID3 extraction function."""

    @patch("muzlib.tag_utils.mp3.MP3")
    def test_get_tag_success_full_metadata(self, mock_mp3_class):
        """Test extraction when all tags and cover art are present."""
        
        # 1. Arrange: Create a mock audio object that behaves like a dict
        mock_audio = MagicMock()
        
        # Mocking TXXX, TIT2, TALB etc. (usually they have a .text list)
        mock_audio.__contains__.side_effect = lambda k: True
        mock_audio.__getitem__.side_effect = {
            'TXXX:ytm_id': MagicMock(text=['vid123']),
            'TXXX:ytm_title': MagicMock(text=['YTM Title']),
            'TIT2': MagicMock(text=['Song Title']),
            'TPE1': MagicMock(text=['Artist A', 'Artist B']),
            'TDRC': MagicMock(text=[MagicMock(year=2024)]),
            'TALB': MagicMock(text=['Album Name']),
            'TPE2': MagicMock(text=['Album Artist']),
            'TRCK': ['5/12'],
            'USLT::XXX': MagicMock(text='Sample Lyrics'),
            'APIC:cover': MagicMock(data=b"fake_binary_image")
        }.get

        mock_mp3_class.return_value = mock_audio

        # 2. Act
        result = get_tag("fake_path.mp3")

        # 3. Assert
        assert result['ytm_id'] == 'vid123'
        assert result['track_name'] == 'Song Title'
        assert result['track_artists'] == ['Artist A', 'Artist B']
        assert result['track_artists_str'] == 'Artist A, Artist B'
        assert result['release_date'] == '2024'
        assert result['track_number'] == '5'
        assert result['total_tracks'] == '12'
        assert result['lyrics'] == 'Sample Lyrics'
        # Check base64 encoding
        expected_cover = base64.b64encode(b"fake_binary_image").decode('utf-8')
        assert result['cover'] == expected_cover

    @patch("muzlib.tag_utils.mp3.MP3")
    def test_get_tag_empty_file(self, mock_mp3_class):
        """Test that missing tags return empty strings instead of crashing."""
        
        # Arrange: Mock audio object where 'in' always returns False
        mock_audio = MagicMock()
        mock_audio.__contains__.return_value = False
        mock_mp3_class.return_value = mock_audio

        # Act
        result = get_tag("empty.mp3")

        # Assert
        assert result['track_name'] == ''
        assert result['track_artists'] == ''
        assert result['track_artists_str'] == ''
        assert result['release_date'] == ''
        assert result['cover'] == ''

    @patch("builtins.print")
    @patch("muzlib.tag_utils.mp3.MP3")
    def test_get_tag_load_error(self, mock_mp3_class, mock_print):
        """Test behavior when the file cannot be loaded (e.g. not an MP3)."""
        
        # Arrange
        mock_mp3_class.side_effect = Exception("File not found or invalid")

        # Act
        result = get_tag("invalid.txt")

        # Assert
        assert result is None
        mock_print.assert_called_once()
        assert "Error loading file" in mock_print.call_args[0][0]

    @patch("builtins.print")
    @patch("muzlib.tag_utils.mp3.MP3")
    def test_get_tag_cover_encoding_error(self, mock_mp3_class, mock_print):
        """Test that a failure in cover art encoding doesn't crash the whole function."""
        
        # Arrange
        mock_audio = MagicMock()
        mock_audio.__contains__.side_effect = lambda k: k == 'APIC:cover'
        
        # Force an error during base64 encoding by providing non-bytes data
        mock_apic = MagicMock()
        type(mock_apic).data = PropertyMock(side_effect=TypeError("Expected bytes"))
        mock_audio.__getitem__.return_value = mock_apic
        
        mock_mp3_class.return_value = mock_audio

        # Act
        # Note: This might still trigger errors on other tags if not careful, 
        # so we ensure it survives.
        result = get_tag("cover_error.mp3")

        # Assert
        assert result['cover'] == ''
        
        print_output = mock_print.call_args[0][0]
        assert "Error encoding cover art" in print_output