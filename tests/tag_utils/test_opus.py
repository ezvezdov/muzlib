import pytest
import base64
from unittest.mock import MagicMock, patch

# Update the import path to where your actual opus.py is located
from muzlib.tag_utils.opus import add_tag, get_tag

class TestAddTagOpus:
    """Test suite for the add_tag Ogg Opus metadata function."""

    @pytest.fixture
    def track_info_full(self):
        """Returns a complete track info dictionary with dummy cover art."""
        return {
            'ytm_id': 'opus123',
            'ytm_title': 'Opus Track (YT)',
            'track_name': 'Opus Song',
            'track_artists': ['Opus Artist'],
            'album_artists': ['Album Artist'],
            'album_name': 'The Opus Album',
            'release_date': '2024',
            'lyrics': 'Sample opus lyrics',
            'track_number': 1,
            'total_tracks': 12,
            'cover': base64.b64encode(b"fake_image_bytes").decode('utf-8')
        }

    @patch("muzlib.tag_utils.opus.Picture")
    @patch("muzlib.tag_utils.opus.OggOpus")
    def test_add_tag_opus_success(self, mock_oggopus, mock_picture_class, track_info_full):
        """Test that all tags and cover art are correctly mapped and saved."""
        mock_audio = MagicMock()
        mock_oggopus.return_value = mock_audio
        
        mock_picture_instance = MagicMock()
        mock_picture_instance.write.return_value = b"encoded_binary_metadata_block"
        mock_picture_class.return_value = mock_picture_instance

        add_tag("fake_track.opus", track_info_full)

        # Assert behavior
        assert mock_oggopus.call_count == 2
        mock_audio.delete.assert_called_once()
        mock_audio.save.assert_called_once()

        # Check assignments instead of retrieval
        # .call_args_list returns [call(key, value), ...]
        mock_audio.__setitem__.assert_any_call('ytm_id', 'opus123')
        mock_audio.__setitem__.assert_any_call('title', 'Opus Song')
        mock_audio.__setitem__.assert_any_call('artist', ['Opus Artist'])
        mock_audio.__setitem__.assert_any_call('date', '2024')
        
        # Check specialized Picture block encoding
        expected_picture_b64 = base64.b64encode(b"encoded_binary_metadata_block").decode("ascii")
        mock_audio.__setitem__.assert_any_call("metadata_block_picture", [expected_picture_b64])

    @patch("builtins.print")
    @patch("muzlib.tag_utils.opus.OggOpus")
    def test_add_tag_opus_picture_error(self, mock_oggopus, mock_print):
        """Test that an error in cover art embedding doesn't crash the whole save."""
        mock_audio = MagicMock()
        mock_oggopus.return_value = mock_audio
        info = {'ytm_id': '123', 'cover': '!!!not-base64!!!'}

        add_tag("test.opus", info)

        # Check assignment
        mock_audio.__setitem__.assert_any_call('ytm_id', '123')
        mock_audio.save.assert_called_once()
        
        assert any("Error embedding art" in call.args[0] for call in mock_print.call_args_list)

class TestGetTagOpus:
    """Test suite for the get_tag Ogg Opus extraction function."""

    @patch("muzlib.tag_utils.opus.Picture")
    @patch("muzlib.tag_utils.opus.OggOpus")
    def test_get_tag_opus_success_full(self, mock_oggopus, mock_picture_class):
        """Test extraction when all Vorbis comments and cover art are present."""
        
        # 1. Arrange
        mock_audio = MagicMock()
        
        # Create a valid base64 string for the mock tags
        valid_b64_block = base64.b64encode(b"dummy_block").decode('ascii')
        
        mock_tags = {
            'ytm_id': ['opus_vid_123'],
            'ytm_title': ['Opus YTM Title'],
            'title': ['Opus Song Title'],
            'artist': ['Artist 1', 'Artist 2'],
            'albumartist': ['Main Album Artist'],
            'date': ['2024-05-20'],
            'album': ['The Opus Collection'],
            'tracknumber': ['03'],
            'tracktotal': ['10'],
            'lyrics': ['Ogg lyrics content'],
            'metadata_block_picture': [valid_b64_block] # Use valid base64 here
        }
        mock_audio.tags = mock_tags
        mock_oggopus.return_value = mock_audio

        # Mock the Picture decoding process
        mock_picture_instance = MagicMock()
        mock_picture_instance.data = b"raw_image_binary_data"
        mock_picture_class.return_value = mock_picture_instance

        # 2. Act
        result = get_tag("fake_audio.opus")

        # 3. Assert
        assert result['ytm_id'] == 'opus_vid_123'
        assert result['track_name'] == 'Opus Song Title'
        assert result['track_artists'] == ['Artist 1', 'Artist 2']
        assert result['track_artists_str'] == 'Artist 1, Artist 2'
        assert result['release_date'] == '2024' 
        assert result['track_number'] == '03'
        assert result['lyrics'] == 'Ogg lyrics content'
        
        # Verify cover art base64 encoding
        expected_cover = base64.b64encode(b"raw_image_binary_data").decode('utf-8')
        assert result['cover'] == expected_cover

    @patch("muzlib.tag_utils.opus.OggOpus")
    def test_get_tag_opus_missing_tags(self, mock_oggopus):
        """Test that missing tags return default empty values."""
        
        # Arrange
        mock_audio = MagicMock()
        mock_audio.tags = {} # No tags present
        mock_oggopus.return_value = mock_audio

        # Act
        result = get_tag("empty.opus")

        # Assert
        assert result['track_name'] == ''
        assert result['track_artists'] == []
        assert result['track_artists_str'] == ''
        assert result['release_date'] == ''
        assert result['cover'] == ''

    @patch("muzlib.tag_utils.opus.OggOpus")
    def test_get_tag_opus_load_failure(self, mock_oggopus):
        """Test that a file load error returns an empty dictionary."""
        
        # Arrange
        mock_oggopus.side_effect = Exception("Critical load error")

        # Act
        result = get_tag("corrupt.opus")

        # Assert
        assert result == {}

    @patch("builtins.print")
    @patch("muzlib.tag_utils.opus.Picture")
    @patch("muzlib.tag_utils.opus.OggOpus")
    def test_get_tag_opus_picture_decode_error(self, mock_oggopus, mock_picture_class, mock_print):
        """Test that a failure in picture decoding doesn't crash the tag extraction."""
        
        # Arrange
        mock_audio = MagicMock()
        mock_audio.tags = {'metadata_block_picture': ['corrupt_data']}
        mock_oggopus.return_value = mock_audio
        
        # Simulate Picture class failing to parse the decoded base64 data
        mock_picture_class.side_effect = Exception("Invalid metadata block")

        # Act
        result = get_tag("bad_art.opus")

        # Assert
        assert result['cover'] == ''
        # Verify the error was logged to the console
        mock_print.assert_called_once()
        assert "Error encoding cover art" in mock_print.call_args[0][0]