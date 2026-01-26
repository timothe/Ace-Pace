"""Unit tests for missing episode detection."""
import pytest
import os
import sys
import csv
from unittest.mock import patch, MagicMock

# Add parent directory to path to import acepace
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import acepace


class TestMissingEpisodeDetection:
    """Tests for missing episode detection logic."""

    def test_detect_missing_episodes(self, temp_dir):
        """Test detecting missing episodes by comparing CRC32s."""
        # Setup: Create local file with known CRC32
        test_file = os.path.join(temp_dir, "test.mkv")
        with open(test_file, "wb") as f:
            f.write(b"test content")
        
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            local_crc32s = acepace.calculate_local_crc32(temp_dir, conn)
            
            # Simulate episodes from Nyaa
            crc32_to_link = {
                list(local_crc32s)[0]: "https://nyaa.si/view/12345",  # Has this one
                "MISSING1": "https://nyaa.si/view/12346",  # Missing
                "MISSING2": "https://nyaa.si/view/12347",  # Missing
            }
            
            # Find missing
            missing = [crc32 for crc32 in crc32_to_link if crc32 not in local_crc32s]
            
            assert len(missing) == 2
            assert "MISSING1" in missing
            assert "MISSING2" in missing
            
            conn.close()

    @patch('acepace.requests.get')
    def test_fetch_crc32_links_from_nyaa(self, mock_get):
        """Test fetching CRC32 links from Nyaa."""
        html_with_results = """
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
                            <a href="/view/12346" title="[One Pace] Episode 2 [1080p][E5F6A7B8].mkv">[One Pace] Episode 2 [1080p][E5F6A7B8].mkv</a>
                            <a href="magnet:?xt=urn:btih:def456">Magnet</a>
                        </td>
                    </tr>
                </table>
            </body>
        </html>
        """
        
        # Empty page to stop the loop
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
        mock_response1.text = html_with_results
        
        mock_response2 = MagicMock()
        mock_response2.status_code = 200
        mock_response2.text = html_empty
        
        # First page has results, second page is empty to stop the loop
        mock_get.side_effect = [mock_response1, mock_response2]
        
        base_url = "https://nyaa.si/?f=0&c=0_0&q=one+pace"
        crc32_to_link, crc32_to_text, crc32_to_magnet, _ = acepace.fetch_crc32_links(base_url)
        
        assert len(crc32_to_link) == 2
        assert "A1B2C3D4" in crc32_to_link
        assert "E5F6A7B8" in crc32_to_link
        assert "A1B2C3D4" in crc32_to_text
        assert "magnet:?xt=urn:btih:abc123" in crc32_to_magnet.values()

    @patch('acepace.requests.get')
    def test_fetch_crc32_links_filters_quality(self, mock_get):
        """Test that fetch_crc32_links filters episodes by quality (1080p/720p only)."""
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
        crc32_to_link, crc32_to_text, crc32_to_magnet, _ = acepace.fetch_crc32_links(base_url)
        
        # Should only have 1080p and 720p episodes, not 480p
        assert len(crc32_to_link) == 2
        assert "A1B2C3D4" in crc32_to_link  # 1080p - should be included
        assert "E5F6A7B8" in crc32_to_link  # 720p - should be included
        assert "A9B0C1D2" not in crc32_to_link  # 480p - should be filtered out

    @patch('acepace.requests.get')
    def test_fetch_crc32_links_stops_on_empty_page(self, mock_get):
        """Test that fetching stops when no matches found."""
        # First page has results
        html_with_results = """
        <html>
            <body>
                <table class="torrent-list">
                    <tr>
                        <td>
                            <a href="/view/12345" title="[One Pace] Episode 1 [1080p][A1B2C3D4].mkv">[One Pace] Episode 1 [1080p][A1B2C3D4].mkv</a>
                        </td>
                    </tr>
                </table>
            </body>
        </html>
        """
        
        # Second page has no results
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
        mock_response1.text = html_with_results
        
        mock_response2 = MagicMock()
        mock_response2.status_code = 200
        mock_response2.text = html_empty
        
        mock_get.side_effect = [mock_response1, mock_response2]
        
        base_url = "https://nyaa.si/?f=0&c=0_0&q=one+pace"
        crc32_to_link, _, _, last_page = acepace.fetch_crc32_links(base_url)
        
        # Should stop after first page (no results on second)
        assert len(crc32_to_link) == 1
        assert last_page == 1

    @patch('acepace.requests.get')
    def test_fetch_title_by_crc32(self, mock_get):
        """Test fetching title by CRC32 from Nyaa search."""
        html = """
        <html>
            <body>
                <table class="torrent-list">
                    <tr>
                        <td>
                            <a href="/view/12345" title="[One Pace] Episode 1 [1080p][A1B2C3D4].mkv">[One Pace] Episode 1 [1080p][A1B2C3D4].mkv</a>
                        </td>
                    </tr>
                </table>
            </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response
        
        title = acepace.fetch_title_by_crc32("A1B2C3D4")
        
        assert title == "[One Pace] Episode 1 [1080p][A1B2C3D4].mkv"

    @patch('acepace.requests.get')
    def test_fetch_title_by_crc32_no_match(self, mock_get):
        """Test fetching title when CRC32 not found."""
        html = """
        <html>
            <body>
                <table class="torrent-list">
                </table>
            </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response
        
        title = acepace.fetch_title_by_crc32("NONEXISTENT")
        
        assert title is None

    @patch('acepace.requests.get')
    def test_fetch_title_by_crc32_multiple_matches(self, mock_get):
        """Test fetching title when multiple matches found."""
        html = """
        <html>
            <body>
                <table class="torrent-list">
                    <tr>
                        <td>
                            <a href="/view/12345" title="[One Pace] Episode 1 [1080p][A1B2C3D4].mkv">[One Pace] Episode 1 [1080p][A1B2C3D4].mkv</a>
                        </td>
                    </tr>
                    <tr>
                        <td>
                            <a href="/view/12346" title="[One Pace] Episode 1 Alt [1080p][A1B2C3D4].mkv">[One Pace] Episode 1 Alt [1080p][A1B2C3D4].mkv</a>
                        </td>
                    </tr>
                </table>
            </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response
        
        title = acepace.fetch_title_by_crc32("A1B2C3D4")
        
        # Should return None when multiple matches
        assert title is None
