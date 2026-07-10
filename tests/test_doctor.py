"""Unit tests for the --doctor diagnostics command (Part H3)."""
import pytest
import os
import sys
import sqlite3
import json
import argparse
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import acepace


def _args(**overrides):
    base = dict(folder=None, client=None, host=None, port=None, username=None, password=None)
    base.update(overrides)
    return argparse.Namespace(**base)


class TestDoctorFolderCheck:
    def test_missing_folder_arg_warns_but_passes(self):
        with patch('acepace._get_default_media_dir', return_value=None):
            assert acepace._doctor_check_folder(_args(folder=None)) is True

    def test_existing_readable_folder_passes(self, temp_dir):
        assert acepace._doctor_check_folder(_args(folder=temp_dir)) is True

    def test_missing_folder_fails(self, temp_dir):
        missing = os.path.join(temp_dir, "does_not_exist")
        assert acepace._doctor_check_folder(_args(folder=missing)) is False


class TestDoctorReferenceDataCheck:
    def test_reference_data_present_passes(self):
        # The real vendored reference data ships with the repo.
        assert acepace._doctor_check_reference_data() is True

    def test_reference_data_missing_fails(self, temp_dir):
        with patch('acepace.REFERENCE_BASE_DIR', temp_dir):
            assert acepace._doctor_check_reference_data() is False


class TestDoctorEpisodesDbCheck:
    def test_missing_db_fails(self, temp_dir):
        db_path = os.path.join(temp_dir, "nonexistent_episodes.db")
        with patch('acepace.EPISODES_DB_NAME', db_path):
            assert acepace._doctor_check_episodes_db() is False

    def test_empty_db_warns_but_passes(self, temp_dir):
        db_path = os.path.join(temp_dir, "episodes.db")
        with patch('acepace.EPISODES_DB_NAME', db_path):
            conn = acepace.init_episodes_db()
            conn.close()
            assert acepace._doctor_check_episodes_db() is True

    def test_db_with_rows_passes(self, temp_dir):
        db_path = os.path.join(temp_dir, "episodes.db")
        with patch('acepace.EPISODES_DB_NAME', db_path):
            conn = acepace.init_episodes_db()
            conn.execute(
                "INSERT INTO episodes_index (crc32, title, page_link, magnet_link, pub_date) "
                "VALUES (?, ?, ?, ?, ?)",
                ("AAAAAAAA", "title", "link", "", None),
            )
            conn.commit()
            conn.close()
            assert acepace._doctor_check_episodes_db() is True


class TestDoctorSqliteIntegrityCheck:
    def test_missing_file_warns_but_passes(self, temp_dir):
        assert acepace._doctor_check_sqlite_integrity(os.path.join(temp_dir, "missing.db")) is True

    def test_valid_sqlite_file_passes(self, temp_dir):
        db_path = os.path.join(temp_dir, "valid.db")
        with patch('acepace.DB_NAME', db_path):
            conn = acepace.init_db()
            conn.close()
        assert acepace._doctor_check_sqlite_integrity(db_path) is True

    def test_corrupted_file_fails(self, temp_dir):
        db_path = os.path.join(temp_dir, "corrupt.db")
        with open(db_path, "wb") as f:
            f.write(b"not a real sqlite file, definitely corrupted content here")
        assert acepace._doctor_check_sqlite_integrity(db_path) is False


class TestDoctorTorrentClientCheck:
    def test_not_configured_skips(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TORRENT_CLIENT", None)
            os.environ.pop("TORRENT_HOST", None)
            os.environ.pop("TORRENT_PORT", None)
            with patch('acepace.IS_DOCKER', False):
                assert acepace._doctor_check_torrent_client(_args(client=None)) is True

    def test_configured_but_unreachable_fails(self):
        with patch.dict(os.environ, {"TORRENT_CLIENT": "transmission", "TORRENT_HOST": "127.0.0.1", "TORRENT_PORT": "1"}):
            with patch('acepace.get_client', side_effect=Exception("connection refused")):
                assert acepace._doctor_check_torrent_client(_args()) is False

    def test_configured_and_reachable_passes(self):
        with patch.dict(os.environ, {"TORRENT_CLIENT": "transmission", "TORRENT_HOST": "127.0.0.1", "TORRENT_PORT": "9091"}):
            with patch('acepace.get_client', return_value=MagicMock()):
                assert acepace._doctor_check_torrent_client(_args()) is True


class TestHandleDoctorCommand:
    def test_all_pass_returns_zero(self, temp_dir):
        db_path = os.path.join(temp_dir, "crc32.db")
        episodes_db_path = os.path.join(temp_dir, "episodes.db")
        with patch('acepace.DB_NAME', db_path), patch('acepace.EPISODES_DB_NAME', episodes_db_path):
            conn = acepace.init_episodes_db()
            conn.execute(
                "INSERT INTO episodes_index (crc32, title, page_link, magnet_link, pub_date) "
                "VALUES (?, ?, ?, ?, ?)",
                ("AAAAAAAA", "title", "link", "", None),
            )
            conn.commit()
            conn.close()
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("TORRENT_CLIENT", None)
                rc = acepace.handle_doctor_command(_args(folder=temp_dir))
        assert rc == 0

    def test_hard_failure_returns_nonzero(self, temp_dir):
        missing_folder = os.path.join(temp_dir, "nope")
        db_path = os.path.join(temp_dir, "crc32.db")
        episodes_db_path = os.path.join(temp_dir, "missing_episodes.db")
        with patch('acepace.DB_NAME', db_path), patch('acepace.EPISODES_DB_NAME', episodes_db_path):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("TORRENT_CLIENT", None)
                rc = acepace.handle_doctor_command(_args(folder=missing_folder))
        assert rc != 0
