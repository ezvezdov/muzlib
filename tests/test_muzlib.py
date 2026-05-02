"""Test suite for the Muzlib core classes and functions."""

import base64
from unittest.mock import patch, MagicMock, mock_open
import pytest

# Adjust this import to match your project structure
from muzlib.muzlib import _get_image, SearchType, Muzlib

class TestGetImage:
    """Test suite for the module-level helper functions and Enums."""

    @patch("muzlib.muzlib.requests.get")
    def test_get_image_success(self, mock_get):
        """Test that an image is successfully downloaded and base64 encoded."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake_image_data"
        mock_get.return_value = mock_response

        # Act
        result = _get_image("http://fakeurl.com/image.jpg")

        # Assert
        expected_b64 = base64.b64encode(b"fake_image_data").decode('utf-8')
        assert result == expected_b64
        mock_get.assert_called_once_with("http://fakeurl.com/image.jpg", timeout=10)

    @patch("muzlib.muzlib.time.sleep")  # Mock sleep to speed up the test
    @patch("muzlib.muzlib.requests.get")
    def test_get_image_retry_failure(self, mock_get, mock_sleep):
        """Test that the function retries on failure and eventually returns an empty string."""
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        # Act
        result = _get_image("http://fakeurl.com/image.jpg", retries=3, delay=1)

        # Assert
        assert result == ''
        assert mock_get.call_count == 3  # It should have retried 3 times
        assert mock_sleep.call_count == 3 # It should have slept between retries


def test_SearchType_enum():
    """Test that the SearchType enum evaluates to the correct API strings[cite: 1]."""
    assert SearchType.ARTIST == "artists"
    assert SearchType.ALBUM == "albums"
    assert SearchType.SONG == "songs"


class TestMuzlibClass:
    """Test suite for the main Muzlib downloader class."""

    @pytest.fixture
    @patch("muzlib.muzlib.os.makedirs")
    @patch("muzlib.muzlib.open", new_callable=mock_open, read_data='{}')
    @patch("muzlib.muzlib.yt_dlp.YoutubeDL")
    @patch("muzlib.muzlib.YTMusic")
    @patch("muzlib.muzlib.files_utils.get_tmp_folder", return_value="/tmp/muzlib")
    def muzlib_instance(self, *mocks):
        """Fixture to provide a mocked Muzlib instance for testing."""
        # Instantiate without touching the real disk or network
        return Muzlib(library_path="/fake/library", codec="mp3")

    def test_artist_rename(self, muzlib_instance):
        """Test the custom artist renaming logic[cite: 1]."""
        # Inject some fake rename data
        muzlib_instance.artists_rename = {"Old Name": "New Name"}

        assert muzlib_instance._artist_rename("Old Name") == "New Name"
        assert muzlib_instance._artist_rename("Unknown Artist") == "Unknown Artist"

    def test_search_routing(self, muzlib_instance):
        """Test that the search method formats the query string correctly based on SearchType[cite: 1]."""

        # Test ARTIST search
        muzlib_instance.search(SearchType.ARTIST, artist_name="Daft Punk")
        muzlib_instance.ytmusic.search.assert_called_with("Daft Punk", filter="artists", limit=20)

        # Test ALBUM search
        muzlib_instance.search(SearchType.ALBUM, artist_name="Daft Punk", album_name="Discovery")
        muzlib_instance.ytmusic.search.assert_called_with("Daft Punk – Discovery", filter="albums", limit=20)

        # Test SONG search
        muzlib_instance.search(SearchType.SONG, artist_name="Daft Punk", song_name="Get Lucky")
        muzlib_instance.ytmusic.search.assert_called_with("Daft Punk – Get Lucky", filter="songs", limit=20)

    def test_get_download_summary_album(self, muzlib_instance):
        """Test that track counts are correctly extracted for an album[cite: 1]."""
        # Arrange
        muzlib_instance.ytmusic.get_album.return_value = {'trackCount': 12}
        search_result = {'browseId': 'album123'}

        # Act
        count = muzlib_instance.get_download_summary(search_result, SearchType.ALBUM)

        # Assert
        assert count == 12
        muzlib_instance.ytmusic.get_album.assert_called_once_with('album123')
