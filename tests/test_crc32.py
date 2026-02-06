"""Unit tests for CRC32 operations."""
import pytest
import zlib
import os
import sys
import tempfile
from unittest.mock import patch, mock_open

# Add parent directory to path to import acepace
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import acepace


class TestCRC32Extraction:
    """Tests for CRC32 extraction from filenames."""

    def test_extract_crc32_from_filename(self):
        """Test extracting CRC32 from filename with brackets."""
        filename = "[One Pace] Episode 1 [1080p][A1B2C3D4].mkv"
        matches = acepace.CRC32_REGEX.findall(filename)
        assert len(matches) > 0
        assert matches[-1].upper() == "A1B2C3D4"

    def test_extract_crc32_multiple_matches(self):
        """Test extracting CRC32 when multiple matches exist (takes last)."""
        filename = "[One Pace] Episode 1 [1080p][A1B2C3D4][E5F6A7B8].mkv"
        matches = acepace.CRC32_REGEX.findall(filename)
        assert len(matches) == 2
        # Should take the last match
        assert matches[-1].upper() == "E5F6A7B8"

    def test_extract_crc32_no_match(self):
        """Test extracting CRC32 from filename without CRC32."""
        filename = "[One Pace] Episode 1 [1080p].mkv"
        matches = acepace.CRC32_REGEX.findall(filename)
        assert len(matches) == 0

    def test_extract_crc32_lowercase(self):
        """Test extracting CRC32 with lowercase hex."""
        filename = "[One Pace] Episode 1 [1080p][a1b2c3d4].mkv"
        matches = acepace.CRC32_REGEX.findall(filename)
        assert len(matches) > 0
        assert matches[-1].upper() == "A1B2C3D4"

    def test_extract_crc32_invalid_length(self):
        """Test that regex doesn't match invalid CRC32 lengths."""
        filename = "[One Pace] Episode 1 [1080p][A1B2C3].mkv"  # Too short
        matches = acepace.CRC32_REGEX.findall(filename)
        assert len(matches) == 0


class TestCRC32Calculation:
    """Tests for CRC32 calculation from file content."""

    def test_calculate_crc32_from_content(self, sample_video_content, temp_dir):
        """Test calculating CRC32 from file content."""
        test_file = os.path.join(temp_dir, "test_video.mkv")
        with open(test_file, "wb") as f:
            f.write(sample_video_content)
        
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            crc32s = acepace.calculate_local_crc32(temp_dir, conn)
            conn.close()
            
            # Calculate expected CRC32
            expected_crc = 0
            for chunk in [sample_video_content[i:i+8192] for i in range(0, len(sample_video_content), 8192)]:
                expected_crc = zlib.crc32(chunk, expected_crc)
            expected_crc32 = f"{expected_crc & 0xFFFFFFFF:08X}"
            
            assert len(crc32s) == 1
            assert expected_crc32 in crc32s

    def test_calculate_crc32_caches_result(self, sample_video_content, temp_dir):
        """Test that CRC32 calculation caches results in database."""
        test_file = os.path.join(temp_dir, "test_video.mkv")
        with open(test_file, "wb") as f:
            f.write(sample_video_content)
        
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            
            # First calculation
            crc32s1 = acepace.calculate_local_crc32(temp_dir, conn)
            
            # Second calculation should use cache
            crc32s2 = acepace.calculate_local_crc32(temp_dir, conn)
            
            # Verify cache was used (check database with normalized path)
            normalized_path = acepace.normalize_file_path(test_file)
            cursor = conn.cursor()
            cursor.execute("SELECT crc32 FROM crc32_cache WHERE file_path = ?", (normalized_path,))
            row = cursor.fetchone()
            assert row is not None
            
            assert crc32s1 == crc32s2
            conn.close()

    def test_calculate_crc32_only_video_files(self, temp_dir):
        """Test that only video files are processed."""
        # Create video file
        video_file = os.path.join(temp_dir, "test.mkv")
        with open(video_file, "wb") as f:
            f.write(b"video content")
        
        # Create non-video file
        text_file = os.path.join(temp_dir, "test.txt")
        with open(text_file, "w") as f:
            f.write("text content")
        
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            crc32s = acepace.calculate_local_crc32(temp_dir, conn)
            conn.close()
            
            # Should only have one CRC32 (for the video file)
            assert len(crc32s) == 1

    def test_calculate_crc32_multiple_video_formats(self, temp_dir):
        """Test that multiple video formats are supported."""
        files = [
            ("test1.mkv", b"mkv content"),
            ("test2.mp4", b"mp4 content"),
            ("test3.avi", b"avi content"),
        ]
        
        for filename, content in files:
            filepath = os.path.join(temp_dir, filename)
            with open(filepath, "wb") as f:
                f.write(content)
        
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            crc32s = acepace.calculate_local_crc32(temp_dir, conn)
            conn.close()
            
            assert len(crc32s) == 3

    def test_calculate_crc32_subdirectories(self, temp_dir):
        """Test that CRC32 calculation works in subdirectories."""
        subdir = os.path.join(temp_dir, "subdir")
        os.makedirs(subdir)
        
        video_file = os.path.join(subdir, "test.mkv")
        with open(video_file, "wb") as f:
            f.write(b"video content")
        
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            crc32s = acepace.calculate_local_crc32(temp_dir, conn)
            conn.close()
            
            assert len(crc32s) == 1
