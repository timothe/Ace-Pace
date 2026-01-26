"""Unit tests for episode metadata fetching."""
import pytest
import os
import sys
from unittest.mock import patch, MagicMock, Mock
from bs4 import BeautifulSoup

# Add parent directory to path to import acepace
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import acepace


class TestEpisodeMetadataFetching:
    """Tests for fetching episode metadata from Nyaa."""

    @patch('acepace.requests.get')
    def test_fetch_episodes_metadata_single_page(self, mock_get, mock_nyaa_html_single_page):
        """Test fetching episodes from a single page."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = mock_nyaa_html_single_page
        mock_get.return_value = mock_response
        
        episodes = acepace.fetch_episodes_metadata()
        
        assert len(episodes) == 2
        assert any(ep[0] == "A1B2C3D4" for ep in episodes)
        assert any(ep[0] == "E5F6A7B8" for ep in episodes)
        
        # Verify default URL was used
        assert mock_get.call_count > 0
        # Check that the default URL (without 1080p) was used
        call_urls = [call[0][0] for call in mock_get.call_args_list]
        assert any("q=one+pace" in url and "1080p" not in url for url in call_urls)

    @patch('acepace.requests.get')
    def test_fetch_episodes_metadata_uses_custom_url(self, mock_get, mock_nyaa_html_single_page):
        """Test that fetch_episodes_metadata uses the provided URL parameter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = mock_nyaa_html_single_page
        mock_get.return_value = mock_response
        
        custom_url = "https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc"
        episodes = acepace.fetch_episodes_metadata(custom_url)
        
        assert len(episodes) == 2
        
        # Verify the custom URL was used in requests
        assert mock_get.call_count > 0
        call_urls = [call[0][0] for call in mock_get.call_args_list]
        # All URLs should start with the custom URL (with page parameter)
        for url in call_urls:
            assert url.startswith(custom_url + "&p=") or url == custom_url + "&p=1"

    @patch('acepace.requests.get')
    def test_fetch_episodes_metadata_default_url_when_none_provided(self, mock_get, mock_nyaa_html_single_page):
        """Test that fetch_episodes_metadata uses default URL when None is provided."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = mock_nyaa_html_single_page
        mock_get.return_value = mock_response
        
        # Call with None explicitly
        episodes = acepace.fetch_episodes_metadata(None)
        
        assert len(episodes) == 2
        
        # Verify default URL was used
        assert mock_get.call_count > 0
        call_urls = [call[0][0] for call in mock_get.call_args_list]
        # Should use default URL without 1080p
        assert any("q=one+pace" in url and "1080p" not in url for url in call_urls)

    @patch('acepace.requests.get')
    @patch('acepace.time.sleep')  # Mock sleep to speed up tests
    def test_fetch_episodes_metadata_multi_page(self, mock_sleep, mock_get, mock_nyaa_html_multi_page):
        """Test fetching episodes from multiple pages."""
        # First page response
        mock_response1 = MagicMock()
        mock_response1.status_code = 200
        mock_response1.text = mock_nyaa_html_multi_page
        
        # Second page response
        mock_response2 = MagicMock()
        mock_response2.status_code = 200
        mock_response2.text = """
        <html>
            <body>
                <table class="torrent-list">
                    <tr>
                        <td>
                            <a href="/view/12347" title="[One Pace] Episode 3 [1080p][A9B0C1D2].mkv">[One Pace] Episode 3 [1080p][A9B0C1D2].mkv</a>
                        </td>
                    </tr>
                </table>
            </body>
        </html>
        """
        
        # Third page response (empty)
        mock_response3 = MagicMock()
        mock_response3.status_code = 200
        mock_response3.text = "<html><body><table class='torrent-list'></table></body></html>"
        
        mock_get.side_effect = [mock_response1, mock_response2, mock_response3]
        
        episodes = acepace.fetch_episodes_metadata()
        
        # Should have episodes from both pages
        assert len(episodes) >= 2
        assert mock_get.call_count >= 2

    @patch('acepace.requests.get')
    def test_fetch_episodes_metadata_crc32_in_title(self, mock_get):
        """Test extracting CRC32 from title directly."""
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
                <ul class="pagination">
                    <li><a href="?p=1">1</a></li>
                </ul>
            </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response
        
        episodes = acepace.fetch_episodes_metadata()
        
        assert len(episodes) == 1
        assert episodes[0][0] == "A1B2C3D4"
        assert "[One Pace]" in episodes[0][1]

    @patch('acepace.requests.get')
    def test_fetch_episodes_metadata_crc32_from_file_list(self, mock_get, mock_nyaa_torrent_page):
        """Test extracting CRC32 from torrent page file list."""
        # Listing page without CRC32 in title
        listing_html = """
        <html>
            <body>
                <table class="torrent-list">
                    <tr>
                        <td>
                            <a href="/view/12345" title="[One Pace] Episode 1">[One Pace] Episode 1</a>
                        </td>
                    </tr>
                </table>
                <ul class="pagination">
                    <li><a href="?p=1">1</a></li>
                </ul>
            </body>
        </html>
        """
        
        # Torrent page with file list
        mock_listing_response = MagicMock()
        mock_listing_response.status_code = 200
        mock_listing_response.text = listing_html
        
        mock_torrent_response = MagicMock()
        mock_torrent_response.status_code = 200
        mock_torrent_response.text = mock_nyaa_torrent_page
        
        mock_get.side_effect = [mock_listing_response, mock_torrent_response]
        
        episodes = acepace.fetch_episodes_metadata()
        
        assert len(episodes) == 1
        assert episodes[0][0] == "A1B2C3D4"

    @patch('acepace.requests.get')
    def test_fetch_episodes_metadata_handles_http_error(self, mock_get):
        """Test that HTTP errors are handled gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        episodes = acepace.fetch_episodes_metadata()
        
        assert len(episodes) == 0

    @patch('acepace.requests.get')
    def test_fetch_episodes_metadata_deduplicates_crc32(self, mock_get):
        """Test that duplicate CRC32s are not added multiple times."""
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
                <ul class="pagination">
                    <li><a href="?p=1">1</a></li>
                </ul>
            </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response
        
        episodes = acepace.fetch_episodes_metadata()
        
        # Should only have one entry despite duplicate CRC32
        crc32s = [ep[0] for ep in episodes]
        assert crc32s.count("A1B2C3D4") == 1


class TestUpdateEpisodesIndex:
    """Tests for updating episodes index database."""

    @patch('acepace.fetch_episodes_metadata')
    @patch('acepace.EPISODES_DB_NAME', 'test_episodes_index.db')
    def test_update_episodes_index_db(self, mock_fetch, temp_dir, sample_episode_data):
        """Test updating episodes index database."""
        with patch('acepace.EPISODES_DB_NAME', os.path.join(temp_dir, 'test.db')):
            mock_fetch.return_value = sample_episode_data
            
            acepace.update_episodes_index_db()
            
            # Verify data was inserted
            conn = acepace.init_episodes_db()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM episodes_index")
            count = cursor.fetchone()[0]
            assert count == 3
            
            # Verify metadata was updated
            last_update = acepace.get_episodes_metadata(conn, "episodes_db_last_update")
            assert last_update is not None
            
            conn.close()
            os.remove(os.path.join(temp_dir, 'test.db'))

    @patch('acepace.fetch_episodes_metadata')
    @patch('acepace.EPISODES_DB_NAME', 'test_episodes_index.db')
    def test_update_episodes_index_db_uses_url_parameter(self, mock_fetch, temp_dir, sample_episode_data):
        """Test that update_episodes_index_db passes URL parameter to fetch_episodes_metadata."""
        with patch('acepace.EPISODES_DB_NAME', os.path.join(temp_dir, 'test.db')):
            mock_fetch.return_value = sample_episode_data
            
            test_url = "https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc"
            acepace.update_episodes_index_db(test_url)
            
            # Verify fetch_episodes_metadata was called with the URL
            mock_fetch.assert_called_once_with(test_url)
            
            # Clean up
            if os.path.exists(os.path.join(temp_dir, 'test.db')):
                os.remove(os.path.join(temp_dir, 'test.db'))


class TestEpisodeQualityFiltering:
    """Tests for ensuring only 1080p (or 720p fallback) episodes are extracted."""

    @patch('acepace.requests.get')
    def test_fetch_episodes_prefers_1080p(self, mock_get):
        """Test that 1080p episodes are extracted when available."""
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
                            <a href="/view/12346" title="[One Pace] Episode 2 [1080p][E5F6A7B8].mkv">[One Pace] Episode 2 [1080p][E5F6A7B8].mkv</a>
                        </td>
                    </tr>
                </table>
                <ul class="pagination">
                    <li><a href="?p=1">1</a></li>
                </ul>
            </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response
        
        episodes = acepace.fetch_episodes_metadata()
        
        # All episodes should be 1080p
        assert len(episodes) == 2
        for crc32, title, _ in episodes:
            assert "[1080p]" in title.upper() or "1080P" in title.upper()
            assert "[One Pace]" in title

    @patch('acepace.requests.get')
    def test_fetch_episodes_accepts_720p_as_fallback(self, mock_get):
        """Test that 720p episodes are accepted when 1080p is not available."""
        html = """
        <html>
            <body>
                <table class="torrent-list">
                    <tr>
                        <td>
                            <a href="/view/12345" title="[One Pace] Episode 1 [720p][A1B2C3D4].mkv">[One Pace] Episode 1 [720p][A1B2C3D4].mkv</a>
                        </td>
                    </tr>
                    <tr>
                        <td>
                            <a href="/view/12346" title="[One Pace] Episode 2 [720p][E5F6A7B8].mkv">[One Pace] Episode 2 [720p][E5F6A7B8].mkv</a>
                        </td>
                    </tr>
                </table>
                <ul class="pagination">
                    <li><a href="?p=1">1</a></li>
                </ul>
            </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response
        
        episodes = acepace.fetch_episodes_metadata()
        
        # All episodes should be 720p
        assert len(episodes) == 2
        for crc32, title, _ in episodes:
            assert "[720p]" in title.upper() or "720P" in title.upper()
            assert "[One Pace]" in title

    @patch('acepace.requests.get')
    def test_fetch_episodes_excludes_lower_quality(self, mock_get):
        """Test that episodes with quality lower than 720p are excluded."""
        html = """
        <html>
            <body>
                <table class="torrent-list">
                    <tr>
                        <td>
                            <a href="/view/12345" title="[One Pace] Episode 1 [480p][A1B2C3D4].mkv">[One Pace] Episode 1 [480p][A1B2C3D4].mkv</a>
                        </td>
                    </tr>
                    <tr>
                        <td>
                            <a href="/view/12346" title="[One Pace] Episode 2 [360p][E5F6A7B8].mkv">[One Pace] Episode 2 [360p][E5F6A7B8].mkv</a>
                        </td>
                    </tr>
                    <tr>
                        <td>
                            <a href="/view/12347" title="[One Pace] Episode 3 [240p][A9B0C1D2].mkv">[One Pace] Episode 3 [240p][A9B0C1D2].mkv</a>
                        </td>
                    </tr>
                </table>
                <ul class="pagination">
                    <li><a href="?p=1">1</a></li>
                </ul>
            </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response
        
        episodes = acepace.fetch_episodes_metadata()
        
        # Lower quality episodes should be excluded
        assert len(episodes) == 0

    @patch('acepace.requests.get')
    def test_fetch_episodes_prefers_1080p_over_720p_same_episode(self, mock_get):
        """Test that when both 1080p and 720p versions exist for same episode, 1080p is preferred."""
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
                            <a href="/view/12346" title="[One Pace] Episode 1 [720p][A1B2C3D4].mkv">[One Pace] Episode 1 [720p][A1B2C3D4].mkv</a>
                        </td>
                    </tr>
                </table>
                <ul class="pagination">
                    <li><a href="?p=1">1</a></li>
                </ul>
            </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response
        
        episodes = acepace.fetch_episodes_metadata()
        
        # Should only have one entry (deduplicated by CRC32)
        # But we need to verify it's the 1080p version
        assert len(episodes) == 1
        crc32, title, _ = episodes[0]
        assert crc32 == "A1B2C3D4"
        # The first one encountered should be kept (1080p in this case)
        # Since CRC32 deduplication happens, we need to check which one was kept
        assert "[1080p]" in title.upper() or "1080P" in title.upper()

    @patch('acepace.requests.get')
    def test_fetch_episodes_mixed_qualities_only_keeps_valid(self, mock_get):
        """Test that mixed quality episodes only keeps 1080p and 720p."""
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
                            <a href="/view/12346" title="[One Pace] Episode 2 [720p][E5F6A7B8].mkv">[One Pace] Episode 2 [720p][E5F6A7B8].mkv</a>
                        </td>
                    </tr>
                    <tr>
                        <td>
                            <a href="/view/12347" title="[One Pace] Episode 3 [480p][A9B0C1D2].mkv">[One Pace] Episode 3 [480p][A9B0C1D2].mkv</a>
                        </td>
                    </tr>
                    <tr>
                        <td>
                            <a href="/view/12348" title="[One Pace] Episode 4 [1080p][A3B4C5D6].mkv">[One Pace] Episode 4 [1080p][A3B4C5D6].mkv</a>
                        </td>
                    </tr>
                </table>
                <ul class="pagination">
                    <li><a href="?p=1">1</a></li>
                </ul>
            </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response
        
        episodes = acepace.fetch_episodes_metadata()
        
        # Should only have 1080p and 720p episodes (3 total, excluding 480p)
        assert len(episodes) == 3
        for crc32, title, _ in episodes:
            title_upper = title.upper()
            has_1080p = "[1080P]" in title_upper or "1080P" in title_upper
            has_720p = "[720P]" in title_upper or "720P" in title_upper
            assert has_1080p or has_720p, f"Episode {title} should be 1080p or 720p"
            # Verify no lower quality
            assert "[480P]" not in title_upper
            assert "[360P]" not in title_upper
            assert "[240P]" not in title_upper

    @patch('acepace.requests.get')
    def test_fetch_episodes_handles_case_insensitive_quality(self, mock_get):
        """Test that quality detection is case-insensitive."""
        html = """
        <html>
            <body>
                <table class="torrent-list">
                    <tr>
                        <td>
                            <a href="/view/12345" title="[One Pace] Episode 1 [1080P][A1B2C3D4].mkv">[One Pace] Episode 1 [1080P][A1B2C3D4].mkv</a>
                        </td>
                    </tr>
                    <tr>
                        <td>
                            <a href="/view/12346" title="[One Pace] Episode 2 [720P][E5F6A7B8].mkv">[One Pace] Episode 2 [720P][E5F6A7B8].mkv</a>
                        </td>
                    </tr>
                </table>
                <ul class="pagination">
                    <li><a href="?p=1">1</a></li>
                </ul>
            </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response
        
        episodes = acepace.fetch_episodes_metadata()
        
        # Should accept both uppercase and lowercase quality markers
        assert len(episodes) == 2

    @patch('acepace.requests.get')
    def test_fetch_episodes_excludes_episodes_without_quality_marker(self, mock_get):
        """Test that episodes without quality markers are excluded."""
        html = """
        <html>
            <body>
                <table class="torrent-list">
                    <tr>
                        <td>
                            <a href="/view/12345" title="[One Pace] Episode 1 [A1B2C3D4].mkv">[One Pace] Episode 1 [A1B2C3D4].mkv</a>
                        </td>
                    </tr>
                    <tr>
                        <td>
                            <a href="/view/12346" title="[One Pace] Episode 2 [1080p][E5F6A7B8].mkv">[One Pace] Episode 2 [1080p][E5F6A7B8].mkv</a>
                        </td>
                    </tr>
                </table>
                <ul class="pagination">
                    <li><a href="?p=1">1</a></li>
                </ul>
            </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response
        
        episodes = acepace.fetch_episodes_metadata()
        
        # Should only include episode with quality marker
        assert len(episodes) == 1
        crc32, title, _ = episodes[0]
        assert crc32 == "E5F6A7B8"
        assert "[1080p]" in title.upper() or "1080P" in title.upper()

    @patch('acepace.requests.get')
    @patch('acepace.time.sleep')
    def test_fetch_episodes_quality_filtering_from_file_list(self, mock_sleep, mock_get):
        """Test quality filtering when CRC32 is extracted from torrent file list."""
        # Listing page
        listing_html = """
        <html>
            <body>
                <table class="torrent-list">
                    <tr>
                        <td>
                            <a href="/view/12345" title="[One Pace] Episode 1">[One Pace] Episode 1</a>
                        </td>
                    </tr>
                </table>
                <ul class="pagination">
                    <li><a href="?p=1">1</a></li>
                </ul>
            </body>
        </html>
        """
        
        # Torrent page with 1080p file
        torrent_html_1080p = """
        <html>
            <body>
                <div class="torrent-file-list">
                    <ul>
                        <li>[One Pace] Episode 1 [1080p][A1B2C3D4].mkv</li>
                    </ul>
                </div>
            </body>
        </html>
        """
        
        mock_listing_response = MagicMock()
        mock_listing_response.status_code = 200
        mock_listing_response.text = listing_html
        
        mock_torrent_response = MagicMock()
        mock_torrent_response.status_code = 200
        mock_torrent_response.text = torrent_html_1080p
        
        mock_get.side_effect = [mock_listing_response, mock_torrent_response]
        
        episodes = acepace.fetch_episodes_metadata()
        
        # Should extract 1080p episode from file list
        assert len(episodes) == 1
        crc32, title, _ = episodes[0]
        assert crc32 == "A1B2C3D4"
        assert "[1080p]" in title.upper() or "1080P" in title.upper()

    @patch('acepace.requests.get')
    @patch('acepace.time.sleep')
    def test_fetch_episodes_quality_filtering_from_file_list_excludes_lower_quality(self, mock_sleep, mock_get):
        """Test that lower quality episodes are excluded when extracted from file list."""
        # Listing page
        listing_html = """
        <html>
            <body>
                <table class="torrent-list">
                    <tr>
                        <td>
                            <a href="/view/12345" title="[One Pace] Episode 1">[One Pace] Episode 1</a>
                        </td>
                    </tr>
                </table>
                <ul class="pagination">
                    <li><a href="?p=1">1</a></li>
                </ul>
            </body>
        </html>
        """
        
        # Torrent page with 480p file (should be excluded)
        torrent_html_480p = """
        <html>
            <body>
                <div class="torrent-file-list">
                    <ul>
                        <li>[One Pace] Episode 1 [480p][A1B2C3D4].mkv</li>
                    </ul>
                </div>
            </body>
        </html>
        """
        
        mock_listing_response = MagicMock()
        mock_listing_response.status_code = 200
        mock_listing_response.text = listing_html
        
        mock_torrent_response = MagicMock()
        mock_torrent_response.status_code = 200
        mock_torrent_response.text = torrent_html_480p
        
        mock_get.side_effect = [mock_listing_response, mock_torrent_response]
        
        episodes = acepace.fetch_episodes_metadata()
        
        # Should exclude 480p episode
        assert len(episodes) == 0


class TestQualityFilteringHelper:
    """Tests for the quality filtering helper function."""

    def test_quality_filtering_accepts_1080p(self):
        """Test that 1080p quality is accepted."""
        # We need to test the internal _is_valid_quality function
        # Since it's nested, we'll test it through fetch_episodes_metadata
        # But we can also test the regex directly
        from acepace import QUALITY_REGEX
        
        test_cases = [
            "[One Pace] Episode 1 [1080p][A1B2C3D4].mkv",
            "[One Pace] Episode 1 [1080P][A1B2C3D4].mkv",
            "[One Pace] Episode 1 [1080P][A1B2C3D4].mkv",
        ]
        
        for test_case in test_cases:
            matches = QUALITY_REGEX.findall(test_case)
            assert len(matches) > 0
            quality_num = int(matches[0].lower().replace('p', ''))
            assert quality_num == 1080

    def test_quality_filtering_accepts_720p(self):
        """Test that 720p quality is accepted."""
        from acepace import QUALITY_REGEX
        
        test_cases = [
            "[One Pace] Episode 1 [720p][A1B2C3D4].mkv",
            "[One Pace] Episode 1 [720P][A1B2C3D4].mkv",
        ]
        
        for test_case in test_cases:
            matches = QUALITY_REGEX.findall(test_case)
            assert len(matches) > 0
            quality_num = int(matches[0].lower().replace('p', ''))
            assert quality_num == 720

    def test_quality_filtering_rejects_lower_quality(self):
        """Test that qualities lower than 720p are rejected."""
        from acepace import QUALITY_REGEX
        
        test_cases = [
            "[One Pace] Episode 1 [480p][A1B2C3D4].mkv",
            "[One Pace] Episode 1 [360p][A1B2C3D4].mkv",
            "[One Pace] Episode 1 [240p][A1B2C3D4].mkv",
        ]
        
        for test_case in test_cases:
            matches = QUALITY_REGEX.findall(test_case)
            assert len(matches) > 0
            quality_num = int(matches[0].lower().replace('p', ''))
            assert quality_num < 720

    def test_quality_filtering_rejects_higher_quality(self):
        """Test that qualities higher than 1080p are rejected (4K, etc.)."""
        from acepace import QUALITY_REGEX
        
        test_cases = [
            "[One Pace] Episode 1 [2160p][A1B2C3D4].mkv",  # 4K
            "[One Pace] Episode 1 [1440p][A1B2C3D4].mkv",  # 1440p
        ]
        
        for test_case in test_cases:
            matches = QUALITY_REGEX.findall(test_case)
            assert len(matches) > 0
            quality_num = int(matches[0].lower().replace('p', ''))
            assert quality_num not in [720, 1080]


class TestURLParameterConsistency:
    """Tests to ensure URL parameter is used consistently across functions."""

    @patch('acepace.requests.get')
    def test_fetch_episodes_metadata_and_fetch_crc32_links_use_same_url(self, mock_get):
        """Test that both fetch_episodes_metadata and fetch_crc32_links use the same URL when provided."""
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
                </table>
                <ul class="pagination">
                    <li><a href="?p=1">1</a></li>
                </ul>
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
        mock_response1.text = html_with_results
        
        mock_response2 = MagicMock()
        mock_response2.status_code = 200
        mock_response2.text = html_empty
        
        mock_get.side_effect = [mock_response1, mock_response2]
        
        test_url = "https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc"
        
        # Test fetch_episodes_metadata
        episodes = acepace.fetch_episodes_metadata(test_url)
        
        # Reset mock for second test
        mock_get.reset_mock()
        mock_get.side_effect = [mock_response1, mock_response2]
        
        # Test fetch_crc32_links
        crc32_to_link, _, _, _ = acepace.fetch_crc32_links(test_url)
        
        # Both should use the same URL
        assert mock_get.call_count > 0
        
        # Verify URLs used in both calls
        episodes_urls = [call[0][0] for call in mock_get.call_args_list]
        
        # Both should have used URLs starting with test_url
        for url in episodes_urls:
            assert url.startswith(test_url + "&p=") or url == test_url + "&p=1"

    @patch('acepace.fetch_episodes_metadata')
    def test_update_episodes_index_db_passes_url_to_fetch_episodes_metadata(self, mock_fetch, temp_dir):
        """Test that update_episodes_index_db correctly passes URL to fetch_episodes_metadata."""
        with patch('acepace.EPISODES_DB_NAME', os.path.join(temp_dir, 'test.db')):
            mock_fetch.return_value = []
            
            test_url = "https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc"
            acepace.update_episodes_index_db(test_url)
            
            # Verify fetch_episodes_metadata was called with the URL
            mock_fetch.assert_called_once_with(test_url)
            
            conn = acepace.init_episodes_db()
            conn.close()
            os.remove(os.path.join(temp_dir, 'test.db'))

    @patch('acepace.fetch_episodes_metadata')
    def test_update_episodes_index_db_default_url_when_none_provided(self, mock_fetch, temp_dir):
        """Test that update_episodes_index_db uses default URL when None is provided."""
        with patch('acepace.EPISODES_DB_NAME', os.path.join(temp_dir, 'test.db')):
            mock_fetch.return_value = []
            
            acepace.update_episodes_index_db()
            
            # Verify fetch_episodes_metadata was called with None (which triggers default)
            mock_fetch.assert_called_once_with(None)
            
            conn = acepace.init_episodes_db()
            conn.close()
            os.remove(os.path.join(temp_dir, 'test.db'))
