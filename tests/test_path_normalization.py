"""Unit tests for path normalization and quality filtering."""
import pytest
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup

# Add parent directory to path to import acepace
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import acepace


def _create_test_row(title):
    """Helper function to create a test HTML row with given title.
    Args:
        title: Episode title to use in the row
    Returns: BeautifulSoup row element"""
    row_html = f"""
    <tr>
        <td>
            <a href="/view/12345" title="{title}">{title}</a>
            <a href="magnet:?xt=urn:btih:abc123">Magnet</a>
        </td>
    </tr>
    """
    soup = BeautifulSoup(row_html, "html.parser")
    return soup.find("tr")


def _process_row_with_assertions(title, expected_success, expected_crc32_in_link=None, expected_text_in_values=None):
    """Helper function to process a row and assert results.
    Args:
        title: Episode title
        expected_success: Expected success value (True/False)
        expected_crc32_in_link: CRC32 that should be in link dict (None to skip check)
        expected_text_in_values: Text that should be in text dict values (None to skip check)
    Returns: Tuple of (success, should_warn, crc32_to_link, crc32_to_text)"""
    row = _create_test_row(title)
    crc32_to_link = {}
    crc32_to_text = {}
    crc32_to_magnet = {}
    
    success, _, should_warn = acepace._process_crc32_row(
        row, crc32_to_link, crc32_to_text, crc32_to_magnet
    )
    
    assert success is expected_success
    assert should_warn is False
    
    if expected_crc32_in_link is not None:
        if expected_success:
            assert expected_crc32_in_link in crc32_to_link
        else:
            assert expected_crc32_in_link not in crc32_to_link
    
    if expected_text_in_values is not None:
        assert expected_text_in_values in crc32_to_text.values()
    
    return success, should_warn, crc32_to_link, crc32_to_text


class TestPathNormalization:
    """Tests for file path normalization functionality."""

    def test_normalize_file_path_absolute(self, temp_dir):
        """Test that normalize_file_path converts to absolute path."""
        test_file = os.path.join(temp_dir, "test.mkv")
        with open(test_file, "wb") as f:
            f.write(b"test content")
        
        normalized = acepace.normalize_file_path(test_file)
        
        assert os.path.isabs(normalized)
        assert normalized == os.path.realpath(os.path.abspath(test_file))

    def test_normalize_file_path_relative(self, temp_dir):
        """Test that normalize_file_path handles relative paths."""
        test_file = os.path.join(temp_dir, "test.mkv")
        with open(test_file, "wb") as f:
            f.write(b"test content")
        
        # Change to temp_dir and use relative path
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            normalized = acepace.normalize_file_path("test.mkv")
            
            assert os.path.isabs(normalized)
            assert normalized == os.path.realpath(os.path.abspath(test_file))
        finally:
            os.chdir(original_cwd)

    def test_normalize_file_path_resolves_symlinks(self, temp_dir):
        """Test that normalize_file_path resolves symlinks."""
        # Create a real file
        real_file = os.path.join(temp_dir, "real.mkv")
        with open(real_file, "wb") as f:
            f.write(b"test content")
        
        # Create a symlink (if supported)
        try:
            symlink_file = os.path.join(temp_dir, "link.mkv")
            os.symlink(real_file, symlink_file)
            
            normalized = acepace.normalize_file_path(symlink_file)
            real_normalized = acepace.normalize_file_path(real_file)
            
            # Both should resolve to the same path
            assert normalized == real_normalized
        except (OSError, AttributeError):
            # Symlinks not supported on this platform, skip
            pytest.skip("Symlinks not supported on this platform")

    def test_normalize_file_path_nonexistent_file(self):
        """Test that normalize_file_path handles nonexistent files gracefully."""
        nonexistent = "/nonexistent/path/file.mkv"
        normalized = acepace.normalize_file_path(nonexistent)
        
        # Should still return normalized absolute path even if file doesn't exist
        assert os.path.isabs(normalized)
        assert normalized == os.path.normpath(os.path.abspath(nonexistent))

    def test_normalize_file_path_consistent(self, temp_dir):
        """Test that normalize_file_path produces consistent results."""
        test_file = os.path.join(temp_dir, "test.mkv")
        with open(test_file, "wb") as f:
            f.write(b"test content")
        
        # Test with different path representations
        path1 = test_file
        path2 = os.path.join(temp_dir, ".", "test.mkv")
        path3 = os.path.join(temp_dir, "..", os.path.basename(temp_dir), "test.mkv")
        
        normalized1 = acepace.normalize_file_path(path1)
        normalized2 = acepace.normalize_file_path(path2)
        normalized3 = acepace.normalize_file_path(path3)
        
        # All should normalize to the same path
        assert normalized1 == normalized2 == normalized3


class TestPathNormalizationInCalculateCRC32:
    """Tests for path normalization in calculate_local_crc32."""

    def test_calculate_local_crc32_stores_normalized_paths(self, temp_dir):
        """Test that calculate_local_crc32 stores normalized paths in database."""
        test_file = os.path.join(temp_dir, "test.mkv")
        with open(test_file, "wb") as f:
            f.write(b"test content")
        
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            acepace.calculate_local_crc32(temp_dir, conn)
            
            # Check database for normalized path
            cursor = conn.cursor()
            cursor.execute("SELECT file_path FROM crc32_cache")
            rows = cursor.fetchall()
            
            assert len(rows) == 1
            stored_path = rows[0][0]
            
            # Stored path should be normalized (absolute)
            assert os.path.isabs(stored_path)
            assert stored_path == acepace.normalize_file_path(test_file)
            
            conn.close()

    def test_calculate_local_crc32_finds_cached_by_normalized_path(self, temp_dir):
        """Test that calculate_local_crc32 finds cached entries using normalized paths."""
        test_file = os.path.join(temp_dir, "test.mkv")
        with open(test_file, "wb") as f:
            f.write(b"test content")
        
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            
            # First calculation
            crc32s1 = acepace.calculate_local_crc32(temp_dir, conn)
            
            # Manually insert with different path representation
            normalized_path = acepace.normalize_file_path(test_file)
            relative_path = "test.mkv"  # Different representation
            
            # Try to query with relative path - should not find it
            cursor = conn.cursor()
            cursor.execute("SELECT crc32 FROM crc32_cache WHERE file_path = ?", (relative_path,))
            row = cursor.fetchone()
            assert row is None  # Should not find with relative path
            
            # Query with normalized path - should find it
            cursor.execute("SELECT crc32 FROM crc32_cache WHERE file_path = ?", (normalized_path,))
            row = cursor.fetchone()
            assert row is not None  # Should find with normalized path
            
            # Second calculation should use cache (even with different path representation)
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                crc32s2 = acepace.calculate_local_crc32(".", conn)
                assert crc32s1 == crc32s2
            finally:
                os.chdir(original_cwd)
            
            conn.close()


class TestPathNormalizationInCountFiles:
    """Tests for path normalization in _count_video_files."""

    def test_count_video_files_uses_normalized_paths(self, temp_dir):
        """Test that _count_video_files uses normalized paths for lookup."""
        test_file = os.path.join(temp_dir, "test.mkv")
        with open(test_file, "wb") as f:
            f.write(b"test content")
        
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            
            # Calculate CRC32 (stores normalized path)
            acepace.calculate_local_crc32(temp_dir, conn)
            
            # Count files - should find the cached entry
            total, recorded = acepace._count_video_files(temp_dir, conn)
            
            assert total == 1
            assert recorded == 1  # Should find the cached entry
            
            conn.close()


class TestQualityFiltering:
    """Tests for quality filtering in episode processing."""

    def test_process_crc32_row_accepts_1080p(self):
        """Test that _process_crc32_row accepts 1080p episodes."""
        _process_row_with_assertions(
            "[One Pace] Episode 1 [1080p][A1B2C3D4].mkv",
            expected_success=True,
            expected_crc32_in_link="A1B2C3D4",
            expected_text_in_values="[One Pace] Episode 1 [1080p][A1B2C3D4].mkv"
        )

    def test_process_crc32_row_rejects_720p(self):
        """Test that _process_crc32_row rejects 720p episodes."""
        _process_row_with_assertions(
            "[One Pace] Episode 1 [720p][A1B2C3D4].mkv",
            expected_success=False,
            expected_crc32_in_link="A1B2C3D4"
        )

    def test_process_crc32_row_rejects_480p(self):
        """Test that _process_crc32_row rejects 480p episodes."""
        _process_row_with_assertions(
            "[One Pace] Episode 1 [480p][A1B2C3D4].mkv",
            expected_success=False,
            expected_crc32_in_link="A1B2C3D4"
        )

    def test_process_crc32_row_rejects_2160p(self):
        """Test that _process_crc32_row rejects 2160p (4K) episodes."""
        _process_row_with_assertions(
            "[One Pace] Episode 1 [2160p][A1B2C3D4].mkv",
            expected_success=False,
            expected_crc32_in_link="A1B2C3D4"
        )

    def test_process_crc32_row_rejects_no_quality(self):
        """Test that _process_crc32_row rejects episodes without quality marker."""
        _process_row_with_assertions(
            "[One Pace] Episode 1 [A1B2C3D4].mkv",
            expected_success=False,
            expected_crc32_in_link="A1B2C3D4"
        )

    def test_process_crc32_row_rejects_no_one_pace_marker(self):
        """Test that _process_crc32_row rejects episodes without [One Pace] marker."""
        _process_row_with_assertions(
            "Episode 1 [1080p][A1B2C3D4].mkv",
            expected_success=False,
            expected_crc32_in_link="A1B2C3D4"
        )

    def test_process_crc32_row_case_insensitive_quality(self):
        """Test that quality filtering is case insensitive."""
        _process_row_with_assertions(
            "[One Pace] Episode 1 [1080P][A1B2C3D4].mkv",
            expected_success=True,
            expected_crc32_in_link="A1B2C3D4"
        )

    @patch('acepace.requests.get')
    def test_fetch_crc32_links_filters_by_quality(self, mock_get):
        """Test that fetch_crc32_links filters episodes by quality."""
        html_with_mixed_quality = """
        <html>
            <body>
                <table class="torrent-list">
                    <tr>
                        <td>
                            <a href="/view/12345" title="[One Pace] Episode 1 [1080p][A1B2C3D4].mkv">[One Pace] Episode 1 [1080p][A1B2C3D4].mkv</a>
                            <a href="magnet:?xt=urn:btih:abc123">Magnet</a>
                        </td>
                    </tr>
                    <tr>
                        <td>
                            <a href="/view/12346" title="[One Pace] Episode 2 [720p][E5F6A7B8].mkv">[One Pace] Episode 2 [720p][E5F6A7B8].mkv</a>
                            <a href="magnet:?xt=urn:btih:def456">Magnet</a>
                        </td>
                    </tr>
                    <tr>
                        <td>
                            <a href="/view/12347" title="[One Pace] Episode 3 [480p][A9B0C1D2].mkv">[One Pace] Episode 3 [480p][A9B0C1D2].mkv</a>
                            <a href="magnet:?xt=urn:btih:ghi789">Magnet</a>
                        </td>
                    </tr>
                </table>
            </body>
        </html>
        """
        
        html_empty = """
        <html>
            <body>
                <table class="torrent-list">
                </table>
            </body>
        </html>
        """
        
        mock_response1 = MagicMock()
        mock_response1.status_code = 200
        mock_response1.text = html_with_mixed_quality
        
        mock_response2 = MagicMock()
        mock_response2.status_code = 200
        mock_response2.text = html_empty
        
        mock_get.side_effect = [mock_response1, mock_response2]
        
        base_url = "https://nyaa.si/?f=0&c=0_0&q=one+pace"
        crc32_to_link, _, _, _ = acepace.fetch_crc32_links(base_url)
        
        # Should only have 1080p episodes, not 720p or 480p
        assert len(crc32_to_link) == 1
        assert "A1B2C3D4" in crc32_to_link  # 1080p - should be included
        assert "E5F6A7B8" not in crc32_to_link  # 720p - should be excluded
        assert "A9B0C1D2" not in crc32_to_link  # 480p - should be excluded
