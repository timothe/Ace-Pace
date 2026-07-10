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
        """Test that fetch_crc32_links filters episodes by quality (1080p only)."""
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

    @patch('acepace.requests.get')
    def test_fetch_crc32_links_stops_on_empty_page(self, mock_get):
        """Test that fetching processes all pages based on pagination."""
        # First page has results and pagination showing 2 pages
        html_with_results = """
        <html>
            <body>
                <ul class="pagination">
                    <li><a href="?p=1">1</a></li>
                    <li><a href="?p=2">2</a></li>
                </ul>
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
        
        # Second page has no results (empty table)
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
        
        # Page 1 is fetched once (for pagination), page 2 is fetched in the loop
        mock_get.side_effect = [mock_response1, mock_response2]
        
        base_url = "https://nyaa.si/?f=0&c=0_0&q=one+pace"
        crc32_to_link, _, _, last_page = acepace.fetch_crc32_links(base_url)
        
        # Should process both pages (pagination shows 2 pages)
        assert len(crc32_to_link) == 1
        assert last_page == 2  # Processed both pages

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


class TestVersionAwareMissingDetection:
    """Tests for Part E: pub_date capture + newest-version-aware grouping."""

    def test_extract_pub_date_from_row_reads_data_timestamp(self):
        html = """
        <tr>
            <td class="text-center" data-timestamp="1782664408">2026-06-28 16:33</td>
        </tr>
        """
        from bs4 import BeautifulSoup
        row = BeautifulSoup(html, "html.parser").find("tr")
        assert acepace._extract_pub_date_from_row(row) == "1782664408"

    def test_extract_pub_date_from_row_returns_none_when_absent(self):
        from bs4 import BeautifulSoup
        row = BeautifulSoup("<tr><td>no timestamp here</td></tr>", "html.parser").find("tr")
        assert acepace._extract_pub_date_from_row(row) is None

    @patch('acepace.requests.get')
    def test_fetch_episodes_metadata_populates_pub_date_side_channel(self, mock_get):
        html_with_results = """
        <html><body><table class="torrent-list">
            <tr>
                <td><a href="/view/1" title="[One Pace] Episode 1 [1080p][A1B2C3D4].mkv">[One Pace] Episode 1 [1080p][A1B2C3D4].mkv</a></td>
                <td class="text-center" data-timestamp="1700000000">2023-11-14 22:13</td>
            </tr>
        </table></body></html>
        """
        html_empty = '<html><body><table class="torrent-list"></table></body></html>'
        r1 = MagicMock(status_code=200, text=html_with_results)
        r2 = MagicMock(status_code=200, text=html_empty)
        mock_get.side_effect = [r1, r2]

        episodes = acepace.fetch_episodes_metadata("https://nyaa.si/?f=0&c=0_0&q=one+pace")
        pub_dates = acepace.get_last_fetched_pub_dates()

        assert len(episodes) == 1
        assert pub_dates.get("A1B2C3D4") == "1700000000"
        # Return shape must stay a 4-tuple list (hard test/API contract).
        assert len(episodes[0]) == 4

    def test_grouped_missing_detection_prefers_newest_present_check(self):
        # Two versions of the same canonical episode (S01E01): an older one
        # the user already has locally, and a newer re-release on Nyaa.
        crc32_to_text = {
            "OLDOLD01": "[One Pace][1-5] Romance Dawn 01 [1080p][OLDOLD01].mkv",
            "NEWNEW01": "[One Pace][1-5] Romance Dawn 01 [1080p][NEWNEW01].mkv",
        }
        crc32_to_magnet = {"OLDOLD01": "magnet:?xt=old", "NEWNEW01": "magnet:?xt=new"}
        crc32_to_pubdate = {"OLDOLD01": "1000", "NEWNEW01": "2000"}
        local_crc32s = {"OLDOLD01"}

        missing = acepace._calculate_missing_episodes_grouped(
            crc32_to_text, crc32_to_magnet, crc32_to_pubdate, local_crc32s
        )

        # Present locally via the OLD version -> canonical episode is not missing.
        assert missing == []

    def test_grouped_missing_detection_reports_newest_version_when_absent(self):
        crc32_to_text = {
            "OLDOLD02": "[One Pace][1-5] Romance Dawn 02 [1080p][OLDOLD02].mkv",
            "NEWNEW02": "[One Pace][1-5] Romance Dawn 02 [1080p][NEWNEW02].mkv",
        }
        crc32_to_magnet = {"OLDOLD02": "magnet:?xt=old", "NEWNEW02": "magnet:?xt=new"}
        crc32_to_pubdate = {"OLDOLD02": "1000", "NEWNEW02": "2000"}
        local_crc32s = set()  # neither version present locally

        missing = acepace._calculate_missing_episodes_grouped(
            crc32_to_text, crc32_to_magnet, crc32_to_pubdate, local_crc32s
        )

        assert missing == ["NEWNEW02"]

    def test_unparseable_titles_fall_back_to_singleton_groups(self):
        crc32_to_text = {"ZZZZZZZZ": "Some Unrelated Release That Does Not Parse.mkv"}
        crc32_to_magnet = {"ZZZZZZZZ": "magnet:?xt=whatever"}
        crc32_to_pubdate = {"ZZZZZZZZ": None}

        missing = acepace._calculate_missing_episodes_grouped(
            crc32_to_text, crc32_to_magnet, crc32_to_pubdate, set()
        )

        assert missing == ["ZZZZZZZZ"]
