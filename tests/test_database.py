"""Unit tests for database operations."""
import pytest
import sqlite3
import os
import sys
from unittest.mock import patch, MagicMock

# Add parent directory to path to import acepace
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import acepace


class TestDatabaseInitialization:
    """Tests for database initialization functions."""

    @patch('acepace.DB_NAME', 'test_crc32_files.db')
    def test_init_db_creates_tables(self, temp_dir, monkeypatch):
        """Test that init_db creates required tables."""
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test_crc32_files.db')):
            conn = acepace.init_db()
            cursor = conn.cursor()
            
            # Check crc32_cache table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='crc32_cache'")
            assert cursor.fetchone() is not None
            
            # Check metadata table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metadata'")
            assert cursor.fetchone() is not None
            
            conn.close()
            os.remove(os.path.join(temp_dir, 'test_crc32_files.db'))

    @patch('acepace.EPISODES_DB_NAME', 'test_episodes_index.db')
    def test_init_episodes_db_creates_tables(self, temp_dir, monkeypatch):
        """Test that init_episodes_db creates required tables."""
        with patch('acepace.EPISODES_DB_NAME', os.path.join(temp_dir, 'test_episodes_index.db')):
            conn = acepace.init_episodes_db()
            cursor = conn.cursor()
            
            # Check episodes_index table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='episodes_index'")
            assert cursor.fetchone() is not None
            
            # Check metadata table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metadata'")
            assert cursor.fetchone() is not None
            
            conn.close()
            os.remove(os.path.join(temp_dir, 'test_episodes_index.db'))

    def test_init_db_suppresses_messages_when_requested(self, temp_dir):
        """Test that init_db suppresses messages when suppress_messages=True."""
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            # First call creates the database (should show message if suppress_messages=False)
            conn1 = acepace.init_db(suppress_messages=False)
            conn1.close()
            
            # Second call with suppress_messages=True should not print message
            with patch('builtins.print') as mock_print:
                conn2 = acepace.init_db(suppress_messages=True)
                conn2.close()
                
                # Verify "Database already exists" message was NOT printed
                print_calls = [str(c) for c in mock_print.call_args_list]
                assert not any("Database already exists" in str(call) for call in print_calls)

    def test_init_db_shows_messages_when_not_suppressed(self, temp_dir):
        """Test that init_db shows messages when suppress_messages=False (default)."""
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            # First call creates the database
            conn1 = acepace.init_db()
            conn1.close()
            
            # Second call should show message (default behavior)
            with patch('builtins.print') as mock_print:
                conn2 = acepace.init_db(suppress_messages=False)
                conn2.close()
                
                # Verify "Database already exists" message WAS printed
                print_calls = [str(c) for c in mock_print.call_args_list]
                assert any("Database already exists" in str(call) for call in print_calls)


class TestMetadataOperations:
    """Tests for metadata get/set operations."""

    def test_get_metadata_nonexistent_key(self, temp_dir):
        """Test getting metadata for non-existent key returns None."""
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            result = acepace.get_metadata(conn, "nonexistent_key")
            assert result is None
            conn.close()
            os.remove(os.path.join(temp_dir, 'test.db'))

    def test_set_and_get_metadata(self, temp_dir):
        """Test setting and getting metadata."""
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            acepace.set_metadata(conn, "test_key", "test_value")
            result = acepace.get_metadata(conn, "test_key")
            assert result == "test_value"
            conn.close()
            os.remove(os.path.join(temp_dir, 'test.db'))

    def test_set_metadata_overwrites_existing(self, temp_dir):
        """Test that set_metadata overwrites existing values."""
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            acepace.set_metadata(conn, "test_key", "old_value")
            acepace.set_metadata(conn, "test_key", "new_value")
            result = acepace.get_metadata(conn, "test_key")
            assert result == "new_value"
            conn.close()
            os.remove(os.path.join(temp_dir, 'test.db'))

    def test_get_episodes_metadata_nonexistent_key(self, temp_dir):
        """Test getting episodes metadata for non-existent key returns None."""
        with patch('acepace.EPISODES_DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_episodes_db()
            result = acepace.get_episodes_metadata(conn, "nonexistent_key")
            assert result is None
            conn.close()
            os.remove(os.path.join(temp_dir, 'test.db'))

    def test_set_and_get_episodes_metadata(self, temp_dir):
        """Test setting and getting episodes metadata."""
        with patch('acepace.EPISODES_DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_episodes_db()
            acepace.set_episodes_metadata(conn, "test_key", "test_value")
            result = acepace.get_episodes_metadata(conn, "test_key")
            assert result == "test_value"
            conn.close()
            os.remove(os.path.join(temp_dir, 'test.db'))


class TestEpisodesIndexOperations:
    """Tests for episodes index database operations."""

    def test_load_crc32_to_title_from_index(self, temp_dir, sample_episode_data):
        """Test loading CRC32 to title mapping from episodes index."""
        with patch('acepace.EPISODES_DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_episodes_db()
            cursor = conn.cursor()
            
            # Insert sample data
            for crc32, title, page_link in sample_episode_data:
                cursor.execute(
                    "INSERT INTO episodes_index (crc32, title, page_link) VALUES (?, ?, ?)",
                    (crc32, title, page_link)
                )
            conn.commit()
            conn.close()
            
            # Load and verify
            mapping = acepace.load_crc32_to_title_from_index()
            assert len(mapping) == 3
            assert mapping["A1B2C3D4"] == "[One Pace] Episode 1 [1080p][A1B2C3D4].mkv"
            assert mapping["E5F6A7B8"] == "[One Pace] Episode 2 [1080p][E5F6A7B8].mkv"
            assert mapping["A9B0C1D2"] == "[One Pace] Episode 3 [1080p][A9B0C1D2].mkv"
            
            os.remove(os.path.join(temp_dir, 'test.db'))
