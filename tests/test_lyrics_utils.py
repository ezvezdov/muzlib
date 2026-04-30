import pytest
from unittest.mock import MagicMock, patch, call

from muzlib.lyrics_utils import _convert_to_timestamp, get_lyrics_ytm, get_lyrics, add_lyrics, add_lyrics_library


class TestConvertToTimestamp:
    """Test suite for the _convert_to_timestamp utility function."""

    @pytest.mark.parametrize(
        "ms, expected",
        [
            # Base case: Zero
            (0, "00:00.000"),
            
            # Examples from docstring
            (9000, "00:09.000"),
            (65432, "01:05.432"),
            (123456, "02:03.456"),
            
            # Edge cases: Roll-overs
            (999, "00:00.999"),       # Just under a second
            (1000, "00:01.000"),      # Exactly one second
            (59999, "00:59.999"),     # Just under a minute
            (60000, "01:00.000"),     # Exactly one minute
            
            # Larger times
            (3600000, "60:00.000"),   # Exactly one hour
            (3661001, "61:01.001"),   # One hour, one minute, one second, one ms
            (3661001.6, "61:01.001"), # Float input (should be converted to int)
        ],
    )
    def test_correct_formatting(self, ms, expected):
        """Test that milliseconds are correctly converted to MM:SS.mmm format."""
        assert _convert_to_timestamp(ms) == expected

class TestGetLyricsYTM:
    """Test suite for the get_lyrics_ytm function."""

    @pytest.fixture
    def mock_ytmusic(self):
        """
        Creates a fake ytmusic client before each test. 
        Using a fixture keeps our tests clean and avoids repetitive setup.
        """
        return MagicMock()

    @patch("muzlib.lyrics_utils.logging_utils.logging.error")
    def test_get_watch_playlist_exception(self, mock_logging_error, mock_ytmusic):
        """Test that it gracefully handles and logs exceptions from the YouTube API."""
        # Arrange: Force the mock to throw an exception when called
        mock_ytmusic.get_watch_playlist.side_effect = Exception("YouTube API Down")
        
        # Act
        result = get_lyrics_ytm(mock_ytmusic, "fake_video_id")
        
        # Assert
        assert result is None
        mock_logging_error.assert_called_once()
        assert "fake_video_id" in mock_logging_error.call_args[0][0]

    def test_no_lyrics_browse_id_in_playlist(self, mock_ytmusic):
        """Test behavior when the track exists but has no lyrics attached."""
        # Arrange: Return a playlist dict that is missing the 'lyrics' key
        mock_ytmusic.get_watch_playlist.return_value = {"other_data": "something"}
        
        # Act
        result = get_lyrics_ytm(mock_ytmusic, "fake_video_id")
        
        # Assert
        assert result is None

    def test_get_lyrics_returns_none(self, mock_ytmusic):
        """Test behavior when a lyrics ID exists, but fetching the actual lyrics fails."""
        # Arrange: Provide a browseId, but make the secondary API call return None
        mock_ytmusic.get_watch_playlist.return_value = {"lyrics": "browse_id_123"}
        mock_ytmusic.get_lyrics.return_value = None
        
        # Act
        result = get_lyrics_ytm(mock_ytmusic, "fake_video_id")
        
        # Assert
        assert result is None

    def test_unsynchronized_lyrics(self, mock_ytmusic):
        """Test that plain text lyrics are passed through correctly."""
        # Arrange
        mock_ytmusic.get_watch_playlist.return_value = {"lyrics": "browse_id_123"}
        mock_ytmusic.get_lyrics.return_value = {
            "hasTimestamps": False,
            "lyrics": "Never gonna give you up\nNever gonna let you down"
        }
        
        # Act
        result = get_lyrics_ytm(mock_ytmusic, "dQw4w9WgXcQ")
        
        # Assert
        assert result == {
            'lyrics': "Never gonna give you up\nNever gonna let you down",
            'hasTimestamps': False
        }

    @patch("muzlib.lyrics_utils._convert_to_timestamp")
    def test_synchronized_lyrics(self, mock_convert_to_timestamp, mock_ytmusic):
        """Test that timestamped lyrics are correctly formatted into LRC syntax."""
        # Arrange
        mock_ytmusic.get_watch_playlist.return_value = {"lyrics": "browse_id_123"}
        
        # Create fake lyric objects that mimic the ytmusicapi response objects
        line1 = MagicMock(start_time=18000, text="We're no strangers to love")
        line2 = MagicMock(start_time=22000, text="You know the rules and so do I")
        
        mock_ytmusic.get_lyrics.return_value = {
            "hasTimestamps": True,
            "lyrics": [line1, line2]
        }
        
        # Dictate what the _convert_to_timestamp function should return for these calls
        mock_convert_to_timestamp.side_effect = ["00:18.000", "00:22.000"]
        
        # Act
        result = get_lyrics_ytm(mock_ytmusic, "dQw4w9WgXcQ")
        
        # Assert
        expected_lrc = "[00:18.000]We're no strangers to love\n[00:22.000]You know the rules and so do I"
        assert result == {
            'lyrics': expected_lrc,
            'hasTimestamps': True
        }

class TestGetLyrics:
    """Test suite for the cascading get_lyrics function."""

    @pytest.fixture
    def ytmusic_mock(self):
        """Provides a fake YTMusic client."""
        return MagicMock()

    @patch("muzlib.lyrics_utils.logging_utils.logging.debug")
    @patch("muzlib.lyrics_utils.syncedlyrics.search")
    @patch("muzlib.lyrics_utils.get_lyrics_ytm")
    def test_step_1_ytm_synced_lyrics(self, mock_get_ytm, mock_synced_search, mock_log, ytmusic_mock):
        """Test that it returns YTM synced lyrics immediately and stops searching."""
        # Arrange
        mock_get_ytm.return_value = {'lyrics': '[00:10.0]YTM Synced \n', 'hasTimestamps': True}

        # Act
        result = get_lyrics("Track", "Artist", ytmusic=ytmusic_mock, video_id="123")

        # Assert
        assert result == "[00:10.0]YTM Synced"
        mock_get_ytm.assert_called_once_with(ytmusic_mock, "123")
        mock_synced_search.assert_not_called()  # Proves it stopped early

    @patch("muzlib.lyrics_utils.logging_utils.logging.debug")
    @patch("muzlib.lyrics_utils.syncedlyrics.search")
    def test_step_2_external_synced_lyrics(self, mock_synced_search, mock_log):
        """Test that it skips YTM (if no client) and finds external synced lyrics."""
        # Arrange: No YTM client passed, so it skips step 1
        mock_synced_search.return_value = "[00:20.0]External Synced \n"

        # Act
        result = get_lyrics("Track", "Artist")

        # Assert
        assert result == "[00:20.0]External Synced"
        # Proves it called the enhanced search
        mock_synced_search.assert_called_once_with("Artist Track", providers=['Lrclib', 'NetEase'], enhanced=True)

    @patch("muzlib.lyrics_utils.logging_utils.logging.debug")
    @patch("muzlib.lyrics_utils.syncedlyrics.search")
    @patch("muzlib.lyrics_utils.get_lyrics_ytm")
    def test_step_3_ytm_plain_lyrics(self, mock_get_ytm, mock_synced_search, mock_log, ytmusic_mock):
        """Test that it caches YTM plain lyrics, tries external synced, then falls back to YTM plain."""
        # Arrange
        mock_get_ytm.return_value = {'lyrics': 'YTM Plain \n', 'hasTimestamps': False}
        mock_synced_search.return_value = None  # Force external synced to fail

        # Act
        result = get_lyrics("Track", "Artist", ytmusic=ytmusic_mock, video_id="123")

        # Assert
        assert result == "YTM Plain"
        mock_synced_search.assert_called_once() # Called once for synced, but NOT a second time for plain

    @patch("muzlib.lyrics_utils.logging_utils.logging.debug")
    @patch("muzlib.lyrics_utils.syncedlyrics.search")
    def test_step_4_external_plain_lyrics(self, mock_synced_search, mock_log):
        """Test that if all synced options fail, it fetches external plain lyrics."""
        # Arrange
        # side_effect acts as a list of responses for each consecutive call
        # Call 1 (Synced): Returns None. Call 2 (Plain): Returns the lyrics.
        mock_synced_search.side_effect = [None, "External Plain \n"]

        # Act
        result = get_lyrics("Track", "Artist")

        # Assert
        assert result == "External Plain"
        assert mock_synced_search.call_count == 2 # Proves both search steps were executed

    @patch("muzlib.lyrics_utils.logging_utils.logging.debug")
    @patch("muzlib.lyrics_utils.syncedlyrics.search")
    def test_step_5_no_lyrics_found(self, mock_synced_search, mock_log):
        """Test behavior when absolutely no lyrics exist anywhere."""
        # Arrange
        mock_synced_search.side_effect = [None, None] # Fails both times

        # Act
        result = get_lyrics("Track", "Artist")

        # Assert
        assert result is None


class TestAddLyrics:
    """Test suite for the add_lyrics orchestrator function."""

    @patch("muzlib.lyrics_utils.tag_utils.add_tag")
    @patch("muzlib.lyrics_utils.get_lyrics")
    @patch("muzlib.lyrics_utils.tag_utils.get_tag")
    def test_add_lyrics_success(self, mock_get_tag, mock_get_lyrics, mock_add_tag):
        """Test the happy path where a file needs lyrics, they are found, and then saved."""
        # Arrange
        mock_get_tag.return_value = {
            'track_name': 'Bohemian Rhapsody', 
            'track_artists_str': 'Queen'
        }
        mock_get_lyrics.return_value = "[00:00.00]Is this the real life?"

        # Act
        add_lyrics("fake/audio/path.mp3")

        # Assert
        # 1. Did it try to fetch lyrics for the right song?
        mock_get_lyrics.assert_called_once_with('Bohemian Rhapsody', 'Queen')
        
        # 2. Did it try to save the file with the new lyrics injected into the dictionary?
        mock_add_tag.assert_called_once_with(
            "fake/audio/path.mp3", 
            {
                'track_name': 'Bohemian Rhapsody', 
                'track_artists_str': 'Queen',
                'lyrics': '[00:00.00]Is this the real life?'
            }
        )

    @patch("muzlib.lyrics_utils.logging_utils.logging.error")
    @patch("muzlib.lyrics_utils.tag_utils.get_tag")
    def test_add_lyrics_missing_metadata(self, mock_get_tag, mock_log_error):
        """Test that it aborts and logs an error if the track name or artist is missing."""
        # Arrange: Return empty strings/None for the required fields
        mock_get_tag.return_value = {
            'track_name': '', 
            'track_artists_str': None
        }

        # Act
        add_lyrics("fake/audio/path.mp3")

        # Assert
        mock_log_error.assert_called_once_with("ERROR: Unknown title or Artist!")

    @patch("muzlib.lyrics_utils.tag_utils.add_tag")
    @patch("muzlib.lyrics_utils.get_lyrics")
    @patch("muzlib.lyrics_utils.tag_utils.get_tag")
    def test_add_lyrics_already_exist(self, mock_get_tag, mock_get_lyrics, mock_add_tag):
        """Test that it does nothing if the file already contains lyrics."""
        # Arrange: Include a populated 'lyrics' key in the fake tag
        mock_get_tag.return_value = {
            'track_name': 'Billie Jean', 
            'track_artists_str': 'Michael Jackson',
            'lyrics': 'She was more like a beauty queen...'
        }

        # Act
        add_lyrics("fake/audio/path.mp3")

        # Assert: It should exit early before fetching or saving anything
        mock_get_lyrics.assert_not_called()
        mock_add_tag.assert_not_called()

    @patch("muzlib.lyrics_utils.tag_utils.add_tag")
    @patch("muzlib.lyrics_utils.get_lyrics")
    @patch("muzlib.lyrics_utils.tag_utils.get_tag")
    def test_add_lyrics_not_found(self, mock_get_tag, mock_get_lyrics, mock_add_tag):
        """Test that it gracefully exits if no lyrics are found on the internet."""
        # Arrange
        mock_get_tag.return_value = {
            'track_name': 'Obscure Indie Song', 
            'track_artists_str': 'Unknown Band'
        }
        # Simulate the fetcher failing to find anything
        mock_get_lyrics.return_value = None

        # Act
        add_lyrics("fake/audio/path.mp3")

        # Assert: It should try to fetch, but stop before saving
        mock_get_lyrics.assert_called_once()
        mock_add_tag.assert_not_called()
    

class TestAddLyricsLibrary:
    """Test suite for the add_lyrics_library bulk-processing function."""

    @patch("muzlib.lyrics_utils.add_lyrics")
    @patch("muzlib.lyrics_utils.find_audio_files")
    def test_add_lyrics_library_processes_all_files(self, mock_find_audio_files, mock_add_lyrics):
        """Test that the library scanner passes every found file to the lyrics adder."""
        
        # 1. Arrange: Fake the output of find_audio_files
        fake_library_path = "/fake/music/folder"
        fake_files = [
            "/fake/music/folder/track1.mp3",
            "/fake/music/folder/track2.opus",
            "/fake/music/folder/track3.m4a"
        ]
        mock_find_audio_files.return_value = fake_files

        # 2. Act: Call the function we are testing
        add_lyrics_library(fake_library_path)

        # 3. Assert: Check that our mocked functions were called correctly
        
        # Did it search the right folder?
        mock_find_audio_files.assert_called_once_with(fake_library_path)
        
        # Did it call add_lyrics exactly 3 times?
        assert mock_add_lyrics.call_count == 3
        
        # Did it call add_lyrics with the exact file paths we expect?
        expected_calls = [
            call("/fake/music/folder/track1.mp3"),
            call("/fake/music/folder/track2.opus"),
            call("/fake/music/folder/track3.m4a")
        ]
        mock_add_lyrics.assert_has_calls(expected_calls, any_order=False)

    @patch("muzlib.lyrics_utils.add_lyrics")
    @patch("muzlib.lyrics_utils.find_audio_files")
    def test_add_lyrics_library_empty_folder(self, mock_find_audio_files, mock_add_lyrics):
        """Test behavior when no audio files are found in the target directory."""
        
        # Arrange: Return an empty list, simulating a folder with no music
        mock_find_audio_files.return_value = []

        # Act
        add_lyrics_library("/empty/folder")

        # Assert: add_lyrics should NEVER be called
        mock_add_lyrics.assert_not_called()