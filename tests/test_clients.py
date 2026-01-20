"""Unit tests for BitTorrent client operations."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock, Mock
from requests.structures import CaseInsensitiveDict

# Add parent directory to path to import clients
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients import QBittorrentClient, TransmissionClient, get_client


class TestQBittorrentClient:
    """Tests for qBittorrent client."""

    @patch('clients.qbittorrentapi.Client')
    def test_qbittorrent_client_init_success(self, mock_client_class):
        """Test successful qBittorrent client initialization."""
        mock_client = MagicMock()
        mock_client.auth_log_in.return_value = None
        mock_client_class.return_value = mock_client
        
        client = QBittorrentClient("localhost", 8080, "user", "pass")
        
        assert client.client == mock_client
        mock_client.auth_log_in.assert_called_once()

    @patch('clients.qbittorrentapi.Client')
    def test_qbittorrent_client_init_login_failed(self, mock_client_class):
        """Test qBittorrent client initialization with login failure."""
        import qbittorrentapi
        mock_client = MagicMock()
        mock_client.auth_log_in.side_effect = qbittorrentapi.LoginFailed("Invalid credentials")
        mock_client_class.return_value = mock_client
        
        with pytest.raises(Exception) as exc_info:
            QBittorrentClient("localhost", 8080, "user", "pass")
        
        assert "Failed to connect to qBittorrent" in str(exc_info.value)

    @patch('clients.qbittorrentapi.Client')
    @patch('clients.time.sleep')
    def test_qbittorrent_add_torrents(self, mock_sleep, mock_client_class, sample_magnet_links):
        """Test adding torrents to qBittorrent."""
        mock_client = MagicMock()
        mock_client.auth_log_in.return_value = None
        mock_client.torrents_info.return_value = []  # No existing torrents
        mock_client.torrents_add.return_value = None
        mock_client_class.return_value = mock_client
        
        client = QBittorrentClient("localhost", 8080, "user", "pass")
        client.add_torrents(sample_magnet_links, download_folder="/downloads", tags=["test"], category="anime")
        
        assert mock_client.torrents_add.call_count == 2
        mock_client.torrents_create_tags.assert_called_once()

    @patch('clients.qbittorrentapi.Client')
    @patch('clients.time.sleep')
    def test_qbittorrent_add_torrents_duplicate(self, mock_sleep, mock_client_class, sample_magnet_links):
        """Test adding duplicate torrents to qBittorrent."""
        mock_client = MagicMock()
        mock_client.auth_log_in.return_value = None
        # First torrent exists, second doesn't
        mock_client.torrents_info.side_effect = [
            [{"hash": "1234567890abcdef1234567890abcdef12345678"}],  # First exists
            []  # Second doesn't
        ]
        mock_client.torrents_add.return_value = None
        mock_client_class.return_value = mock_client
        
        client = QBittorrentClient("localhost", 8080, "user", "pass")
        client.add_torrents(sample_magnet_links, tags=["test"])
        
        # Should only add the second torrent
        assert mock_client.torrents_add.call_count == 1
        # Should add tags to existing torrent
        assert mock_client.torrents_add_tags.call_count == 1

    @patch('clients.qbittorrentapi.Client')
    @patch('clients.time.sleep')
    def test_qbittorrent_add_torrents_invalid_magnet(self, mock_sleep, mock_client_class):
        """Test handling invalid magnet links."""
        mock_client = MagicMock()
        mock_client.auth_log_in.return_value = None
        mock_client_class.return_value = mock_client
        
        client = QBittorrentClient("localhost", 8080, "user", "pass")
        invalid_magnets = ["invalid_magnet_link"]
        
        client.add_torrents(invalid_magnets)
        
        # Should not call torrents_add for invalid magnet
        mock_client.torrents_add.assert_not_called()


class TestTransmissionClient:
    """Tests for Transmission client."""

    @patch('clients.requests.Session')
    def test_transmission_client_init_success(self, mock_session_class):
        """Test successful Transmission client initialization."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = TransmissionClient("localhost", 9091, "user", "pass")
        
        assert client.session == mock_session
        mock_session.post.assert_called()

    @patch('clients.requests.Session')
    def test_transmission_client_init_409_retry(self, mock_session_class):
        """Test Transmission client handles 409 status code (session ID)."""
        mock_session = MagicMock()
        
        # First call returns 409 with session ID
        mock_response_409 = MagicMock()
        mock_response_409.status_code = 409
        # Use CaseInsensitiveDict to match requests.Response.headers behavior
        mock_response_409.headers = CaseInsensitiveDict({"X-Transmission-Session-Id": "test_session_id"})
        
        # Second call succeeds
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"result": "success"}
        
        mock_session.post.side_effect = [mock_response_409, mock_response_200]
        mock_session_class.return_value = mock_session
        
        client = TransmissionClient("localhost", 9091, None, None)
        
        assert client.session_id == "test_session_id"

    @patch('clients.requests.Session')
    @patch('clients.time.sleep')
    def test_transmission_add_torrents(self, mock_sleep, mock_session_class, sample_magnet_links):
        """Test adding torrents to Transmission."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = TransmissionClient("localhost", 9091, None, None)
        client.session_id = "test_session_id"
        client.add_torrents(sample_magnet_links, download_folder="/downloads")
        
        assert mock_session.post.call_count >= len(sample_magnet_links)

    @patch('clients.requests.Session')
    @patch('clients.time.sleep')
    def test_transmission_add_torrents_handles_409(self, mock_sleep, mock_session_class, sample_magnet_links):
        """Test Transmission handles 409 during torrent add."""
        mock_session = MagicMock()
        
        # Response for __init__ connection test (session-get)
        mock_init_response = MagicMock()
        mock_init_response.status_code = 200
        mock_init_response.json.return_value = {"result": "success"}
        
        # First call in add_torrents returns 409, second succeeds
        mock_response_409 = MagicMock()
        mock_response_409.status_code = 409
        # Use CaseInsensitiveDict to match requests.Response.headers behavior
        mock_response_409.headers = CaseInsensitiveDict({"X-Transmission-Session-Id": "new_session_id"})
        
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"result": "success"}
        
        # __init__ makes one POST, add_torrents makes two POSTs (409 then retry)
        mock_session.post.side_effect = [mock_init_response, mock_response_409, mock_response_200]
        mock_session_class.return_value = mock_session
        
        client = TransmissionClient("localhost", 9091, None, None)
        client.session_id = "old_session_id"
        client.add_torrents(sample_magnet_links[:1])  # Just one to simplify
        
        assert client.session_id == "new_session_id"


class TestClientFactory:
    """Tests for client factory function."""

    def test_get_client_qbittorrent(self):
        """Test getting qBittorrent client."""
        with patch('clients.QBittorrentClient') as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            client = get_client("qbittorrent", "localhost", 8080, "user", "pass")
            assert client == mock_instance

    def test_get_client_transmission(self):
        """Test getting Transmission client."""
        with patch('clients.TransmissionClient') as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            client = get_client("transmission", "localhost", 9091, "user", "pass")
            assert client == mock_instance

    def test_get_client_unknown(self):
        """Test getting unknown client raises error."""
        with pytest.raises(ValueError) as exc_info:
            get_client("unknown", "localhost", 8080, "user", "pass")
        assert "Unknown client" in str(exc_info.value)
