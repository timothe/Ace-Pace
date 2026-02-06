"""Unit tests for main command execution and Docker mode behavior."""
import pytest
import os
import sys
from unittest.mock import patch, MagicMock, call

# Add parent directory to path to import acepace
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import acepace

# Test constants
TEST_HOST_IP = "localhost"  # Test host for testing environment variable handling


class TestReleaseDateHeader:
    """Tests for release date in header (from acepace.py mtime)."""

    @patch('acepace._get_release_date', return_value='2025-02-04')
    def test_print_header_includes_release_date(self, mock_release_date):
        """Header shows Release line when _get_release_date returns a date."""
        with patch('acepace.IS_DOCKER', False), patch('builtins.print') as mock_print:
            acepace._print_header()
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        assert "Release" in printed
        assert "2025-02-04" in printed

    def test_get_release_date_returns_string_from_mtime(self):
        """_get_release_date returns YYYY-MM-DD from acepace.py mtime."""
        result = acepace._get_release_date()
        assert isinstance(result, str)
        if result:
            assert len(result) == 10
            assert result[4] == "-" and result[7] == "-"


class TestDockerModeBehavior:
    """Tests for Docker mode specific behavior."""

    @patch('acepace.IS_DOCKER', True)
    @patch('acepace._validate_url')
    @patch('acepace._show_episodes_metadata_status')
    @patch('acepace.init_db')
    @patch('acepace._get_folder_from_args')
    @patch('acepace._handle_main_commands')
    def test_docker_mode_message_not_shown_for_db_command(self, mock_handle, mock_folder, mock_init_db, 
                                                          mock_show_status, mock_validate):
        """Test that Docker mode message is not shown for --db command."""
        mock_validate.return_value = True
        mock_init_db.return_value = MagicMock()
        mock_folder.return_value = "/media"
        
        # Create mock args with --db
        mock_args = MagicMock()
        mock_args.help = False
        mock_args.db = True
        mock_args.episodes_update = False
        mock_args.download = False
        mock_args.rename = False
        mock_args.url = "https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc"
        mock_args.folder = None
        
        with patch('acepace._parse_arguments', return_value=mock_args):
            with patch('builtins.print') as mock_print:
                with pytest.raises(SystemExit):
                    acepace.main()
                
                # Verify "Running in Docker mode" was NOT printed
                print_calls = [str(c) for c in mock_print.call_args_list]
                assert not any("Running in Docker mode" in str(call) for call in print_calls)

    @patch('acepace.IS_DOCKER', True)
    @patch('acepace._validate_url')
    @patch('acepace._show_episodes_metadata_status')
    @patch('acepace.update_episodes_index_db')
    def test_docker_mode_message_not_shown_for_episodes_update(self, mock_update, mock_show_status, mock_validate):
        """Test that Docker mode message is not shown for --episodes_update command."""
        mock_validate.return_value = True
        
        # Create mock args with --episodes_update
        mock_args = MagicMock()
        mock_args.help = False
        mock_args.db = False
        mock_args.episodes_update = True
        mock_args.url = "https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc"
        
        with patch('acepace._parse_arguments', return_value=mock_args):
            with patch('builtins.print') as mock_print:
                with pytest.raises(SystemExit):
                    acepace.main()
                
                # Verify "Running in Docker mode" was NOT printed
                print_calls = [str(c) for c in mock_print.call_args_list]
                assert not any("Running in Docker mode" in str(call) for call in print_calls)

    @patch('acepace.IS_DOCKER', True)
    @patch('acepace._validate_url')
    @patch('acepace._show_episodes_metadata_status')
    @patch('acepace.init_db')
    @patch('acepace._get_folder_from_args')
    @patch('acepace._handle_main_commands')
    def test_docker_mode_message_not_printed_by_python_for_main_command(self, mock_handle, mock_folder,
                                                                         mock_init_db, mock_show_status,
                                                                         mock_validate):
        """In Docker, entrypoint.sh prints the header once; Python must not print it again."""
        mock_validate.return_value = True
        mock_init_db.return_value = MagicMock()
        mock_folder.return_value = "/media"
        
        # Create mock args for main command (no --db or --episodes_update)
        mock_args = MagicMock()
        mock_args.help = False
        mock_args.db = False
        mock_args.episodes_update = False
        mock_args.download = False
        mock_args.rename = False
        mock_args.url = "https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc"
        mock_args.folder = None
        
        with patch('acepace._parse_arguments', return_value=mock_args):
            with patch('builtins.print') as mock_print:
                with pytest.raises(SystemExit):
                    acepace.main()
                
                # Python must NOT print header in Docker (entrypoint.sh already did)
                print_calls = [str(c) for c in mock_print.call_args_list]
                assert not any("Running in Docker mode" in str(call) for call in print_calls)

    @patch('acepace.IS_DOCKER', False)
    @patch('acepace._validate_url')
    @patch('acepace._show_episodes_metadata_status')
    @patch('acepace.init_db')
    @patch('acepace._get_folder_from_args')
    @patch('acepace._handle_main_commands')
    def test_docker_mode_message_not_shown_when_not_in_docker(self, mock_handle, mock_folder, mock_init_db,
                                                               mock_show_status, mock_validate):
        """Test that Docker mode message is not shown when not running in Docker."""
        mock_validate.return_value = True
        mock_init_db.return_value = MagicMock()
        mock_folder.return_value = "/media"
        
        # Create mock args for main command
        mock_args = MagicMock()
        mock_args.help = False
        mock_args.db = False
        mock_args.episodes_update = False
        mock_args.download = False
        mock_args.rename = False
        mock_args.url = "https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc"
        mock_args.folder = None
        
        with patch('acepace._parse_arguments', return_value=mock_args):
            with patch('builtins.print') as mock_print:
                with pytest.raises(SystemExit):
                    acepace.main()
                
                # Verify "Running in Docker mode" was NOT printed
                print_calls = [str(c) for c in mock_print.call_args_list]
                assert not any("Running in Docker mode" in str(call) for call in print_calls)


class TestEpisodesMetadataStatusSuppression:
    """Tests for episodes metadata status message suppression."""

    @patch('acepace._validate_url')
    @patch('acepace._show_episodes_metadata_status')
    @patch('acepace.init_db')
    @patch('acepace.export_db_to_csv')
    def test_episodes_metadata_status_not_shown_for_db_command(self, mock_export, mock_init_db,
                                                                mock_show_status, mock_validate):
        """Test that episodes metadata status is not shown for --db command."""
        mock_validate.return_value = True
        mock_conn = MagicMock()
        mock_init_db.return_value = mock_conn
        
        # Create mock args with --db
        mock_args = MagicMock()
        mock_args.help = False
        mock_args.db = True
        mock_args.episodes_update = False
        mock_args.download = False
        mock_args.rename = False
        mock_args.url = "https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc"
        mock_args.folder = "/media"
        
        with patch('acepace._parse_arguments', return_value=mock_args):
            with patch('acepace._get_folder_from_args', return_value="/media"):
                with pytest.raises(SystemExit):
                    acepace.main()
                
                # Verify _show_episodes_metadata_status was NOT called
                mock_show_status.assert_not_called()

    @patch('acepace._validate_url')
    @patch('acepace._show_episodes_metadata_status')
    @patch('acepace.update_episodes_index_db')
    def test_episodes_metadata_status_not_shown_for_episodes_update(self, mock_update, mock_show_status, mock_validate):
        """Test that episodes metadata status is not shown for --episodes_update command."""
        mock_validate.return_value = True
        
        # Create mock args with --episodes_update
        mock_args = MagicMock()
        mock_args.help = False
        mock_args.db = False
        mock_args.episodes_update = True
        mock_args.url = "https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc"
        
        with patch('acepace._parse_arguments', return_value=mock_args):
            with pytest.raises(SystemExit):
                acepace.main()
            
            # Verify _show_episodes_metadata_status was NOT called
            mock_show_status.assert_not_called()

    @patch('acepace._validate_url')
    @patch('acepace._show_episodes_metadata_status')
    @patch('acepace.init_db')
    @patch('acepace._get_folder_from_args')
    @patch('acepace._handle_main_commands')
    def test_episodes_metadata_status_shown_for_main_command(self, mock_handle, mock_folder, mock_init_db,
                                                              mock_show_status, mock_validate):
        """Test that episodes metadata status is shown for main command."""
        mock_validate.return_value = True
        mock_init_db.return_value = MagicMock()
        mock_folder.return_value = "/media"
        
        # Create mock args for main command
        mock_args = MagicMock()
        mock_args.help = False
        mock_args.db = False
        mock_args.episodes_update = False
        mock_args.download = False
        mock_args.rename = False
        mock_args.url = "https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc"
        mock_args.folder = None
        
        with patch('acepace._parse_arguments', return_value=mock_args):
            with pytest.raises(SystemExit):
                acepace.main()
            
            # Verify _show_episodes_metadata_status WAS called
            mock_show_status.assert_called_once()


class TestURLParameterPropagation:
    """Tests for URL parameter propagation through command chain."""

    @patch('acepace._validate_url')
    @patch('acepace.update_episodes_index_db')
    def test_episodes_update_receives_url_parameter(self, mock_update, mock_validate):
        """Test that --episodes_update receives URL parameter from args."""
        mock_validate.return_value = True
        
        test_url = "https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc"
        
        # Create mock args with --episodes_update and URL
        mock_args = MagicMock()
        mock_args.help = False
        mock_args.db = False
        mock_args.episodes_update = True
        mock_args.url = test_url
        
        with patch('acepace._parse_arguments', return_value=mock_args):
            with pytest.raises(SystemExit):
                acepace.main()
            
            # Verify update_episodes_index_db was called with URL and force_update
            mock_update.assert_called_once_with(test_url, force_update=True)

    @patch('acepace._validate_url')
    @patch('acepace.init_db')
    @patch('acepace._get_folder_from_args')
    @patch('acepace._handle_rename_command')
    def test_rename_receives_url_parameter(self, mock_rename, mock_folder, mock_init_db, mock_validate):
        """Test that --rename receives URL parameter from args."""
        mock_validate.return_value = True
        mock_init_db.return_value = MagicMock()
        mock_folder.return_value = "/media"
        
        test_url = "https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc"
        
        # Create mock args with --rename and URL
        mock_args = MagicMock()
        mock_args.help = False
        mock_args.db = False
        mock_args.episodes_update = False
        mock_args.download = False
        mock_args.rename = True
        mock_args.url = test_url
        mock_args.folder = None
        mock_args.dry_run = False

        with patch('acepace._parse_arguments', return_value=mock_args):
            with pytest.raises(SystemExit):
                acepace.main()

            # Verify _handle_rename_command was called with URL, dry_run, and folder
            mock_rename.assert_called_once()
            call_args = mock_rename.call_args
            assert call_args[0][1] == test_url  # Second positional argument is URL
            assert call_args[1]["dry_run"] is False
            assert call_args[1]["folder"] == "/media"

    @patch('acepace._validate_url')
    @patch('acepace.init_db')
    @patch('acepace._get_folder_from_args')
    @patch('acepace._handle_rename_command')
    def test_rename_with_dry_run_passes_dry_run_true(self, mock_rename, mock_folder, mock_init_db, mock_validate):
        """Test that --rename --dry-run passes dry_run=True to _handle_rename_command."""
        mock_validate.return_value = True
        mock_init_db.return_value = MagicMock()
        mock_folder.return_value = "/media"

        mock_args = MagicMock()
        mock_args.help = False
        mock_args.db = False
        mock_args.episodes_update = False
        mock_args.download = False
        mock_args.rename = True
        mock_args.url = None
        mock_args.folder = None
        mock_args.dry_run = True

        with patch('acepace._parse_arguments', return_value=mock_args):
            with pytest.raises(SystemExit):
                acepace.main()

            mock_rename.assert_called_once()
            assert mock_rename.call_args[1]["dry_run"] is True
            assert mock_rename.call_args[1]["folder"] == "/media"


class TestDockerDownloadDefaults:
    """Tests for Docker download default values and logging."""

    @patch('acepace.IS_DOCKER', True)
    @patch('acepace._load_magnet_links')
    @patch('acepace.get_client')
    def test_docker_uses_default_connection_values(self, mock_get_client, mock_load_magnets):
        """Test that Docker mode uses default connection values when not specified."""
        mock_load_magnets.return_value = ["magnet:?xt=urn:btih:test123"]
        mock_client_obj = MagicMock()
        mock_get_client.return_value = mock_client_obj
        
        # Create mock args without client/host/port specified
        mock_args = MagicMock()
        mock_args.client = None
        mock_args.host = None
        mock_args.port = None
        mock_args.username = None
        mock_args.password = None
        mock_args.download_folder = None
        mock_args.tag = None
        mock_args.category = None
        
        with patch.dict('os.environ', {}, clear=False):
            # Remove any TORRENT_* env vars to test defaults
            for key in ['TORRENT_CLIENT', 'TORRENT_HOST', 'TORRENT_PORT', 'TORRENT_USER', 'TORRENT_PASSWORD']:
                if key in os.environ:
                    del os.environ[key]
            
            acepace._handle_download_command(mock_args)
            
            # Verify default values were used
            mock_get_client.assert_called_once()
            call_args = mock_get_client.call_args
            assert call_args[0][0] == "transmission"  # Default client
            assert call_args[0][1] == "localhost"  # Default host
            assert call_args[0][2] == 9091  # Default port for transmission

    @patch('acepace.IS_DOCKER', True)
    @patch('acepace._load_magnet_links')
    @patch('acepace.get_client')
    def test_docker_logs_connection_parameters(self, mock_get_client, mock_load_magnets):
        """Test that Docker mode logs connection parameters used for download."""
        mock_load_magnets.return_value = ["magnet:?xt=urn:btih:test123"]
        mock_client_obj = MagicMock()
        mock_get_client.return_value = mock_client_obj
        
        # Create mock args
        mock_args = MagicMock()
        mock_args.client = None
        mock_args.host = None
        mock_args.port = None
        mock_args.username = None
        mock_args.password = None
        mock_args.download_folder = None
        mock_args.tag = None
        mock_args.category = None
        
        with patch.dict('os.environ', {}, clear=False):
            # Remove any TORRENT_* env vars
            for key in ['TORRENT_CLIENT', 'TORRENT_HOST', 'TORRENT_PORT', 'TORRENT_USER', 'TORRENT_PASSWORD']:
                if key in os.environ:
                    del os.environ[key]
            
            with patch('builtins.print') as mock_print:
                acepace._handle_download_command(mock_args)
                
                # Verify connection parameters were logged
                print_calls = [str(c) for c in mock_print.call_args_list]
                assert any("Download configuration:" in str(call) for call in print_calls)
                assert any("Client:" in str(call) for call in print_calls)
                assert any("Host:" in str(call) for call in print_calls)
                assert any("Port:" in str(call) for call in print_calls)

    @patch('acepace.IS_DOCKER', True)
    @patch('acepace._load_magnet_links')
    @patch('acepace.get_client')
    def test_docker_uses_environment_variable_overrides(self, mock_get_client, mock_load_magnets):
        """Test that Docker mode uses environment variables to override defaults."""
        mock_load_magnets.return_value = ["magnet:?xt=urn:btih:test123"]
        mock_client_obj = MagicMock()
        mock_get_client.return_value = mock_client_obj
        
        # Create mock args
        mock_args = MagicMock()
        mock_args.client = None
        mock_args.host = None
        mock_args.port = None
        mock_args.username = None
        mock_args.password = None
        mock_args.download_folder = None
        mock_args.tag = None
        mock_args.category = None
        
        with patch.dict('os.environ', {
            'TORRENT_CLIENT': 'qbittorrent',
            'TORRENT_HOST': TEST_HOST_IP,
            'TORRENT_PORT': '8080',
            'TORRENT_USER': 'admin'
        }):
            acepace._handle_download_command(mock_args)
            
            # Verify environment variable values were used
            mock_get_client.assert_called_once()
            call_args = mock_get_client.call_args
            assert call_args[0][0] == "qbittorrent"  # From env var
            assert call_args[0][1] == TEST_HOST_IP  # From env var
            assert call_args[0][2] == 8080  # From env var
            assert call_args[0][3] == "admin"  # From env var


class TestDryRunMode:
    """Tests for dry run mode in download command."""

    @patch('acepace._load_magnet_links')
    @patch('acepace.get_client')
    def test_dry_run_mode_calls_add_torrents_with_dry_run_flag(self, mock_get_client, mock_load_magnets):
        """Test that dry run mode passes dry_run=True to add_torrents."""
        mock_load_magnets.return_value = ["magnet:?xt=urn:btih:test123"]
        mock_client_obj = MagicMock()
        mock_get_client.return_value = mock_client_obj
        
        mock_args = MagicMock()
        mock_args.client = "transmission"
        mock_args.host = "localhost"
        mock_args.port = 9091
        mock_args.username = None
        mock_args.password = None
        mock_args.download_folder = None
        mock_args.tag = None
        mock_args.category = None
        mock_args.dry_run = True
        
        acepace._handle_download_command(mock_args)
        
        # Verify add_torrents was called with dry_run=True
        mock_client_obj.add_torrents.assert_called_once()
        call_kwargs = mock_client_obj.add_torrents.call_args[1]
        assert call_kwargs['dry_run'] is True

    @patch('acepace.IS_DOCKER', True)
    @patch('acepace._load_magnet_links')
    @patch('acepace.get_client')
    def test_docker_dry_run_mode_logs_dry_run(self, mock_get_client, mock_load_magnets):
        """Test that Docker mode logs dry run status."""
        mock_load_magnets.return_value = ["magnet:?xt=urn:btih:test123"]
        mock_client_obj = MagicMock()
        mock_get_client.return_value = mock_client_obj
        
        mock_args = MagicMock()
        mock_args.client = None
        mock_args.host = None
        mock_args.port = None
        mock_args.username = None
        mock_args.password = None
        mock_args.download_folder = None
        mock_args.tag = None
        mock_args.category = None
        mock_args.dry_run = True
        
        with patch.dict('os.environ', {}, clear=False):
            for key in ['TORRENT_CLIENT', 'TORRENT_HOST', 'TORRENT_PORT', 'TORRENT_USER', 'TORRENT_PASSWORD']:
                if key in os.environ:
                    del os.environ[key]
            
            with patch('builtins.print') as mock_print:
                acepace._handle_download_command(mock_args)
                
                # Verify dry run mode was logged
                print_calls = [str(c) for c in mock_print.call_args_list]
                assert any("DRY RUN" in str(call) for call in print_calls)
                assert any("Mode: DRY RUN" in str(call) for call in print_calls)

    @patch('acepace.IS_DOCKER', False)
    @patch('acepace._load_magnet_links')
    @patch('acepace.get_client')
    def test_non_docker_dry_run_mode_logs_dry_run(self, mock_get_client, mock_load_magnets):
        """Test that non-Docker mode logs dry run status."""
        mock_load_magnets.return_value = ["magnet:?xt=urn:btih:test123"]
        mock_client_obj = MagicMock()
        mock_get_client.return_value = mock_client_obj
        
        mock_args = MagicMock()
        mock_args.client = "transmission"
        mock_args.host = "localhost"
        mock_args.port = 9091
        mock_args.username = None
        mock_args.password = None
        mock_args.download_folder = None
        mock_args.tag = None
        mock_args.category = None
        mock_args.dry_run = True
        
        with patch('builtins.print') as mock_print:
            acepace._handle_download_command(mock_args)
            
            # Verify dry run mode was logged
            print_calls = [str(c) for c in mock_print.call_args_list]
            assert any("DRY RUN MODE" in str(call) for call in print_calls)

    @patch('acepace._load_magnet_links')
    @patch('acepace.get_client')
    def test_dry_run_mode_does_not_add_torrents(self, mock_get_client, mock_load_magnets):
        """Test that dry run mode does not actually add torrents."""
        mock_load_magnets.return_value = ["magnet:?xt=urn:btih:test123"]
        mock_client_obj = MagicMock()
        mock_get_client.return_value = mock_client_obj
        
        mock_args = MagicMock()
        mock_args.client = "transmission"
        mock_args.host = "localhost"
        mock_args.port = 9091
        mock_args.username = None
        mock_args.password = None
        mock_args.download_folder = None
        mock_args.tag = None
        mock_args.category = None
        mock_args.dry_run = True
        
        acepace._handle_download_command(mock_args)
        
        # Verify add_torrents was called with dry_run=True
        mock_client_obj.add_torrents.assert_called_once()
        call_kwargs = mock_client_obj.add_torrents.call_args[1]
        assert call_kwargs['dry_run'] is True
