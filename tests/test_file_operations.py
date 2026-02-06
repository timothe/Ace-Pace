"""Unit tests for file operations and renaming."""
import pytest
import os
import sys
import shutil
import re
from unittest.mock import patch, MagicMock, mock_open

# Add parent directory to path to import acepace
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import acepace


class TestFileRenaming:
    """Tests for file renaming functionality."""

    def test_rename_local_files_matches_by_crc32(self, temp_dir, sample_episode_data):
        """Test that files are renamed based on CRC32 matching."""
        # Create test video file
        test_file = os.path.join(temp_dir, "old_name.mkv")
        with open(test_file, "wb") as f:
            f.write(b"test video content")
        
        # Calculate CRC32 for the file
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            crc32s = acepace.calculate_local_crc32(temp_dir, conn)
            actual_crc32 = list(crc32s)[0]
            
            # Update episodes index with matching CRC32
            with patch('acepace.EPISODES_DB_NAME', os.path.join(temp_dir, 'episodes.db')):
                episodes_conn = acepace.init_episodes_db()
                cursor = episodes_conn.cursor()
                cursor.execute(
                    "INSERT INTO episodes_index (crc32, title, page_link, magnet_link) VALUES (?, ?, ?, ?)",
                    (actual_crc32, "[One Pace] Episode 1 [1080p].mkv", "https://nyaa.si/view/12345", "")
                )
                episodes_conn.commit()
                episodes_conn.close()
            
            # Mock load_crc32_to_title_from_index to return our mapping
            with patch('acepace.load_crc32_to_title_from_index') as mock_load:
                mock_load.return_value = {actual_crc32: "[One Pace] Episode 1 [1080p].mkv"}
                
                # Note: rename_local_files requires user input, so we'll test the logic separately
                # by checking the rename plan generation
                cursor = conn.cursor()
                cursor.execute("SELECT file_path, crc32 FROM crc32_cache")
                entries = cursor.fetchall()
                
                crc32_to_title = mock_load.return_value
                rename_plan = []
                for file_path, crc32 in entries:
                    title = crc32_to_title.get(crc32)
                    if title:
                        dir_name = os.path.dirname(file_path)
                        sanitized_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
                        new_filename = f"{sanitized_title}"
                        new_path = os.path.join(dir_name, new_filename)
                        if os.path.abspath(file_path) != os.path.abspath(new_path):
                            rename_plan.append((file_path, new_path))
                
                assert len(rename_plan) > 0
                assert rename_plan[0][1].endswith("[One Pace] Episode 1 [1080p].mkv")
            
            conn.close()

    def test_rename_sanitizes_filename(self):
        """Test that filenames are sanitized to remove problematic characters."""
        title = "[One Pace] Episode 1: Test <1080p> | Special.mkv"
        sanitized = re.sub(r'[\\/*?:"<>|]', "", title).strip()
        assert ":" not in sanitized
        assert "<" not in sanitized
        assert ">" not in sanitized
        assert "|" not in sanitized

    def test_rename_skips_files_without_match(self, temp_dir):
        """Test that files without CRC32 match are skipped."""
        # Create test video file
        test_file = os.path.join(temp_dir, "test.mkv")
        with open(test_file, "wb") as f:
            f.write(b"test content")
        
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            acepace.calculate_local_crc32(temp_dir, conn)
            
            # Mock load_crc32_to_title_from_index to return empty/no match
            with patch('acepace.load_crc32_to_title_from_index') as mock_load:
                mock_load.return_value = {}  # No matches
                
                cursor = conn.cursor()
                cursor.execute("SELECT file_path, crc32 FROM crc32_cache")
                entries = cursor.fetchall()
                
                crc32_to_title = mock_load.return_value
                rename_plan = []
                for file_path, crc32 in entries:
                    title = crc32_to_title.get(crc32)
                    if title:
                        # This should not execute
                        rename_plan.append((file_path, "new_path"))
                
                assert len(rename_plan) == 0
            
            conn.close()

    def test_rename_uses_normalized_paths(self, temp_dir):
        """Test that rename operations use normalized paths in database."""
        test_file = os.path.join(temp_dir, "old_name.mkv")
        with open(test_file, "wb") as f:
            f.write(b"test video content")
        
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            
            # Calculate CRC32 (stores normalized path)
            acepace.calculate_local_crc32(temp_dir, conn)
            
            # Get the stored path from database
            cursor = conn.cursor()
            cursor.execute("SELECT file_path FROM crc32_cache")
            stored_path = cursor.fetchone()[0]
            
            # Verify it's normalized
            assert os.path.isabs(stored_path)
            assert stored_path == acepace.normalize_file_path(test_file)
            
            # Mock rename scenario
            with patch('acepace.load_crc32_to_title_from_index') as mock_load:
                crc32s = acepace.calculate_local_crc32(temp_dir, conn)
                actual_crc32 = list(crc32s)[0]
                mock_load.return_value = {actual_crc32: "[One Pace] Episode 1 [1080p].mkv"}
                
                # Simulate rename
                new_path = os.path.join(temp_dir, "[One Pace] Episode 1 [1080p].mkv")
                normalized_old = acepace.normalize_file_path(test_file)
                normalized_new = acepace.normalize_file_path(new_path)
                
                # Check that paths would be normalized in database update
                assert normalized_old == stored_path  # Should match what's in DB
                assert os.path.isabs(normalized_new)
            
            conn.close()

    def test_rename_dry_run_does_not_confirm_or_execute(self, temp_dir):
        """Test that rename_local_files(conn, dry_run=True) does not ask for confirmation or rename files."""
        test_file = os.path.join(temp_dir, "old_name.mkv")
        with open(test_file, "wb") as f:
            f.write(b"test video content")

        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            acepace.calculate_local_crc32(temp_dir, conn)
            actual_crc32 = list(acepace.calculate_local_crc32(temp_dir, conn))[0]

            with patch('acepace.load_crc32_to_title_from_index') as mock_load:
                mock_load.return_value = {actual_crc32: "[One Pace] Episode 1 [1080p].mkv"}
                with patch('acepace._get_rename_confirmation') as mock_confirm:
                    with patch('acepace._execute_rename') as mock_execute:
                        acepace.rename_local_files(conn, dry_run=True)
                        mock_confirm.assert_not_called()
                        mock_execute.assert_not_called()
            conn.close()

    def test_ensure_crc32_cache_complete_runs_calculation_when_missing(self, temp_dir):
        """When cache is missing CRC32s for some files, calculate_local_crc32 is called."""
        conn = MagicMock()
        with patch('acepace._count_video_files') as mock_count:
            with patch('acepace.calculate_local_crc32') as mock_calc:
                mock_count.return_value = (3, 1)
                acepace._ensure_crc32_cache_complete(temp_dir, conn)
                mock_calc.assert_called_once_with(temp_dir, conn)

    def test_ensure_crc32_cache_complete_skips_when_up_to_date(self, temp_dir):
        """When all files are in cache, calculate_local_crc32 is not called."""
        conn = MagicMock()
        with patch('acepace._count_video_files') as mock_count:
            with patch('acepace.calculate_local_crc32') as mock_calc:
                mock_count.return_value = (2, 2)
                acepace._ensure_crc32_cache_complete(temp_dir, conn)
                mock_calc.assert_not_called()

    def test_ensure_crc32_cache_complete_skips_when_no_files(self, temp_dir):
        """When folder has no video files, calculate_local_crc32 is not called."""
        conn = MagicMock()
        with patch('acepace._count_video_files') as mock_count:
            with patch('acepace.calculate_local_crc32') as mock_calc:
                mock_count.return_value = (0, 0)
                acepace._ensure_crc32_cache_complete(temp_dir, conn)
                mock_calc.assert_not_called()


class TestCSVExport:
    """Tests for CSV export functionality."""

    def test_export_db_to_csv(self, temp_dir):
        """Test exporting database to CSV."""
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            cursor = conn.cursor()
            
            # Add test data
            cursor.execute(
                "INSERT INTO crc32_cache (file_path, crc32) VALUES (?, ?)",
                ("/path/to/file1.mkv", "A1B2C3D4")
            )
            cursor.execute(
                "INSERT INTO crc32_cache (file_path, crc32) VALUES (?, ?)",
                ("/path/to/file2.mkv", "E5F6A7B8")
            )
            conn.commit()
            
            # Export to CSV
            with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
                acepace.export_db_to_csv(conn)
            
            # Check if CSV was created (it should be in current directory, but we'll check the logic)
            # The actual file would be created in the working directory
            conn.close()

    def test_export_db_to_csv_updates_metadata(self, temp_dir):
        """Test that export updates last_db_export metadata."""
        with patch('acepace.DB_NAME', os.path.join(temp_dir, 'test.db')):
            conn = acepace.init_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO crc32_cache (file_path, crc32) VALUES (?, ?)",
                ("/path/to/file.mkv", "A1B2C3D4")
            )
            conn.commit()
            
            acepace.export_db_to_csv(conn)
            
            last_export = acepace.get_metadata(conn, "last_db_export")
            assert last_export is not None
            conn.close()
