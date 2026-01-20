"""Shared fixtures for Ace-Pace tests."""
import pytest
import sqlite3
import os
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def temp_db_path(temp_dir):
    """Create a temporary database path."""
    return os.path.join(temp_dir, "test_crc32_files.db")


@pytest.fixture
def temp_episodes_db_path(temp_dir):
    """Create a temporary episodes database path."""
    return os.path.join(temp_dir, "test_episodes_index.db")


@pytest.fixture
def sample_video_content():
    """Sample video file content for CRC32 testing."""
    return b"This is sample video content for testing CRC32 calculation" * 100


@pytest.fixture
def sample_crc32():
    """Sample CRC32 value for testing."""
    return "A1B2C3D4"


@pytest.fixture
def sample_episode_data():
    """Sample episode data for testing."""
    return [
        ("A1B2C3D4", "[One Pace] Episode 1 [1080p][A1B2C3D4].mkv", "https://nyaa.si/view/12345"),
        ("E5F6G7H8", "[One Pace] Episode 2 [1080p][E5F6G7H8].mkv", "https://nyaa.si/view/12346"),
        ("I9J0K1L2", "[One Pace] Episode 3 [1080p][I9J0K1L2].mkv", "https://nyaa.si/view/12347"),
    ]


@pytest.fixture
def mock_nyaa_html_single_page():
    """Mock HTML for a single Nyaa.si page."""
    return """
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
                        <a href="/view/12346" title="[One Pace] Episode 2 [1080p][E5F6G7H8].mkv">[One Pace] Episode 2 [1080p][E5F6G7H8].mkv</a>
                        <a href="magnet:?xt=urn:btih:def456">Magnet</a>
                    </td>
                </tr>
            </table>
            <ul class="pagination">
                <li><a href="?p=1">1</a></li>
            </ul>
        </body>
    </html>
    """


@pytest.fixture
def mock_nyaa_html_multi_page():
    """Mock HTML for multi-page Nyaa.si results."""
    return """
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
                <li><a href="?p=2">2</a></li>
                <li><a href="?p=3">3</a></li>
            </ul>
        </body>
    </html>
    """


@pytest.fixture
def mock_nyaa_torrent_page():
    """Mock HTML for a single torrent page with file list."""
    return """
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


@pytest.fixture
def mock_nyaa_torrent_page_folder():
    """Mock HTML for a torrent page with folder structure."""
    return """
    <html>
        <body>
            <div class="torrent-file-list">
                <a class="folder">One Pace</a>
                <ul>
                    <li>
                        <ul>
                            <li>[One Pace] Episode 1 [1080p][A1B2C3D4].mkv</li>
                        </ul>
                    </li>
                </ul>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def sample_magnet_links():
    """Sample magnet links for testing."""
    return [
        "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=test",
        "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12&dn=test2",
    ]
