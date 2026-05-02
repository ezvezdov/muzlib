"""Unit tests for the Muzlib text utilities."""

import pytest

from muzlib.text_utils import trackname_remove_unnecessary, get_feat_artists, sanitize_filename

class TestTracknameRemoveUnnecessary:
    """Test suite for the track name string cleaning utility."""

    @pytest.mark.parametrize("input_name, expected_name", [
        # Standard '(feat. )' variations
        ("Song Title (feat. Artist B)", "Song Title"),
        ("Song Title (Feat. Artist B)", "Song Title"),
        ("Song Title (ft. Artist B)", "Song Title"),
        ("Song Title (Ft. Artist B)", "Song Title"),
        
        # Without parentheses
        ("Track Name feat. Somebody", "Track Name"),
        ("Track Name ft. Somebody", "Track Name"),
        
        # Producer tags
        ("Another Track [prod. by DJ Tape]", "Another Track"),
        ("Another Track (prod. by DJ Tape)", "Another Track"),
        ("Another Track (Prod. by DJ Tape)", "Another Track"),
        
        # Clean tracks (should remain completely unchanged)
        ("Clean Song", "Clean Song"),
        ("Bohemian Rhapsody", "Bohemian Rhapsody"),
        
        # Edge cases for trailing whitespace removal (.rstrip())
        ("Song Title  (feat. Person)", "Song Title"),
        ("Trailing Whitespace Song   ", "Trailing Whitespace Song"),

        # Multiple
        ("Multiple (feat. A) [prod. B]", "Multiple"),
        ("Multiple (ft. A) (prod. B)", "Multiple"),
    ])
    def test_trackname_remove_unnecessary(self, input_name, expected_name):
        """Test that feature and producer tags are stripped and whitespace is trimmed."""
        
        # Act
        result = trackname_remove_unnecessary(input_name)
        
        # Assert
        assert result == expected_name


class TestGetFeatArtists:
    """Test suite for the featured artist extraction utility."""

    @pytest.mark.parametrize("track_name, expected_artists", [
        # 1. No featured artists
        ("Bohemian Rhapsody", []),
        ("Clean Track Name", []),

        # 2. Single artist, different prefix variations
        ("Song Title (feat. Artist A)", ["Artist A"]),
        ("Song Title feat. Artist A", ["Artist A"]),
        ("Song Title (ft. Artist A)", ["Artist A"]),
        ("Song Title ft. Artist A", ["Artist A"]),
        
        # 3. Case insensitivity and missing dots
        ("Song Title (Feat. Artist A)", ["Artist A"]),
        ("Song Title FT. Artist A", ["Artist A"]),
        ("Song Title feat Artist A", ["Artist A"]), # No dot

        # 4. Multiple artists (Ampersands and Commas)
        ("Song (feat. Artist A & Artist B)", ["Artist A", "Artist B"]),
        ("Song ft. Artist A, Artist B", ["Artist A", "Artist B"]),
        ("Song (feat. Artist A, Artist B & Artist C)", ["Artist A", "Artist B", "Artist C"]),

        # 5. Edge cases: messy whitespace
        ("Song  ( feat.   Artist A  )", ["Artist A"]),
        ("Song ft. Artist A , Artist B", ["Artist A", "Artist B"]),
        
        # 6. Edge cases: text after the artist
        ("Song (feat. Artist A) [Remix]", ["Artist A"]),
    ])
    def test_get_feat_artists(self, track_name, expected_artists):
        """Test that featured artists are correctly extracted and split."""
        
        # Act
        result = get_feat_artists(track_name)
        
        # Assert
        assert result == expected_artists


class TestSanitizeFilename:
    """Test suite for the OS-safe filename sanitization utility."""

    @pytest.mark.parametrize("input_name, expected_name", [
        # 1. Clean filename (should remain unchanged)
        ("Perfectly Normal Filename 123.mp3", "Perfectly Normal Filename 123.mp3"),
        
        # 2. Individual forbidden characters
        ("Track: Name", "Track： Name"),
        ("Are you ready?", "Are you ready？"),
        ("My *Track*", "My ＊Track＊"),
        ("<Artist>", "＜Artist＞"),
        ("AC/DC", "AC／DC"),
        ('My "Awesome" Track', "My ''Awesome'' Track"),
        ("Track | Remix", "Track ∣ Remix"),
        
        # 3. Null byte removal
        ("Track\0Name", "TrackName"),
        
        # 4. Multiple forbidden characters at once
        ('What: Is <This> "Madness"? AC/DC *Remix* | Part 1', 
         "What： Is ＜This＞ ''Madness''？ AC／DC ＊Remix＊ ∣ Part 1"),
         
        # 5. Empty string
        ("", ""),
    ])
    def test_sanitize_filename(self, input_name, expected_name):
        """Test that forbidden OS characters are replaced with safe unicode equivalents."""
        
        # Act
        result = sanitize_filename(input_name)
        
        # Assert
        assert result == expected_name