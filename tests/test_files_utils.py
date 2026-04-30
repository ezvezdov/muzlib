from muzlib.files_utils import find_audio_files


def test_find_audio_files_with_matches(tmp_path):
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

def test_find_audio_files_empty_directory(tmp_path):
    """Test behavior when the directory has no matching files."""

    # Setup directory with no audio files
    (tmp_path / "document.pdf").touch()
    
    assert find_audio_files(str(tmp_path)) == []

def test_find_audio_files_nonexistent_directory():
    """Test behavior with a directory that doesn't exist."""

    assert find_audio_files("/path/that/definitely/does/not/exist_12345") == []