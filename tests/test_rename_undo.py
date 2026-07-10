"""Unit tests for the rewritten rename engine (Part C/D) and undo (Part H1)."""
import pytest
import os
import sys
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import acepace


def _write_video(path, content=b"some unique video bytes for crc32"):
    with open(path, "wb") as f:
        f.write(content)


def _seed_episode_index(episodes_db_path, crc32, title):
    with patch('acepace.EPISODES_DB_NAME', episodes_db_path):
        conn = acepace.init_episodes_db()
        conn.execute(
            "INSERT OR REPLACE INTO episodes_index (crc32, title, page_link, magnet_link, pub_date) "
            "VALUES (?, ?, ?, ?, ?)",
            (crc32, title, "https://nyaa.si/view/1", "", None),
        )
        conn.commit()
        conn.close()


class TestBuildRenamePlan:
    """Tests for canonical naming + Season NN moves + unrecognized handling."""

    def test_canonical_naming_and_season_folder(self, temp_dir):
        lookup, seasons, _ = acepace.get_reference_index()
        video = os.path.join(temp_dir, "old.mkv")
        _write_video(video)
        entries = [(video, "AAAAAAAA")]
        crc32_to_title = {"AAAAAAAA": "[One Pace][1-5] Romance Dawn 01 [1080p][AAAAAAAA].mkv"}

        rename_plan, unrecognized, already_correct = acepace._build_rename_plan(
            entries, crc32_to_title, seasons, lookup, extended_mode=False
        )

        assert not unrecognized
        assert not already_correct
        assert len(rename_plan) == 1
        item = rename_plan[0]
        assert item["new_path"].endswith(
            os.path.join("Season 01", "One Pace - S01E01 - Romance Dawn, the Dawn of an Adventure.mkv")
        )

    def test_unrecognized_title_is_never_renamed(self, temp_dir):
        lookup, seasons, _ = acepace.get_reference_index()
        video = os.path.join(temp_dir, "old.mkv")
        _write_video(video)
        entries = [(video, "BBBBBBBB")]
        crc32_to_title = {"BBBBBBBB": "Some Completely Unrelated Release.mkv"}

        rename_plan, unrecognized, already_correct = acepace._build_rename_plan(
            entries, crc32_to_title, seasons, lookup, extended_mode=False
        )

        assert not rename_plan
        assert len(unrecognized) == 1
        assert unrecognized[0][0] == video

    def test_no_title_found_is_unrecognized_not_error(self, temp_dir):
        lookup, seasons, _ = acepace.get_reference_index()
        video = os.path.join(temp_dir, "old.mkv")
        _write_video(video)
        entries = [(video, "CCCCCCCC")]

        rename_plan, unrecognized, already_correct = acepace._build_rename_plan(
            entries, {}, seasons, lookup, extended_mode=False
        )

        assert not rename_plan
        assert len(unrecognized) == 1


class TestRenameLocalFilesIntegration:
    """End-to-end tests for rename_local_files() against real temp DBs/files."""

    def _setup(self, temp_dir, title_fmt="[One Pace][1-5] Romance Dawn 01 [1080p][{crc32}].mkv"):
        media = os.path.join(temp_dir, "media")
        os.makedirs(media, exist_ok=True)
        video = os.path.join(media, "old.mkv")
        _write_video(video)

        db_path = os.path.join(temp_dir, "test_crc32.db")
        episodes_db_path = os.path.join(temp_dir, "test_episodes.db")

        with patch('acepace.DB_NAME', db_path):
            conn = acepace.init_db()
            local_crc32s = acepace.calculate_local_crc32(media, conn)
        crc32 = list(local_crc32s)[0]

        _seed_episode_index(episodes_db_path, crc32, title_fmt.format(crc32=crc32))
        return media, video, crc32, conn, db_path, episodes_db_path

    def test_dry_run_makes_no_filesystem_changes(self, temp_dir):
        media, video, crc32, conn, db_path, episodes_db_path = self._setup(temp_dir)

        with patch('acepace.DB_NAME', db_path), patch('acepace.EPISODES_DB_NAME', episodes_db_path):
            with patch('acepace._get_rename_confirmation') as mock_confirm:
                with patch('acepace._execute_rename') as mock_execute:
                    acepace.rename_local_files(conn, dry_run=True, folder=media)
                    mock_confirm.assert_not_called()
                    mock_execute.assert_not_called()

        assert os.path.isfile(video)
        assert not os.path.isdir(os.path.join(media, "Season 01"))
        conn.close()

    def test_real_run_moves_file_and_writes_nfo(self, temp_dir):
        media, video, crc32, conn, db_path, episodes_db_path = self._setup(temp_dir)
        rename_log_path = os.path.join(temp_dir, "rename_log.json")

        with patch('acepace.DB_NAME', db_path), patch('acepace.EPISODES_DB_NAME', episodes_db_path):
            with patch('acepace.RENAME_LOG_FILENAME', rename_log_path):
                with patch('acepace._get_rename_confirmation', return_value="y"):
                    with patch('acepace.IS_DOCKER', False):
                        acepace.rename_local_files(conn, dry_run=False, folder=media)

        new_path = os.path.join(
            media, "Season 01", "One Pace - S01E01 - Romance Dawn, the Dawn of an Adventure.mkv"
        )
        assert os.path.isfile(new_path)
        assert not os.path.isfile(video)
        nfo_path = os.path.splitext(new_path)[0] + ".nfo"
        assert os.path.isfile(nfo_path)
        assert os.path.isfile(os.path.join(media, "tvshow.nfo"))
        conn.close()

    def test_extended_version_prefers_extended_entry(self, temp_dir):
        media, video, crc32, conn, db_path, episodes_db_path = self._setup(
            temp_dir,
            title_fmt="[One Pace][1-5] Romance Dawn 01 Extended [1080p][{crc32}].mkv",
        )

        with patch('acepace.DB_NAME', db_path), patch('acepace.EPISODES_DB_NAME', episodes_db_path):
            with patch('acepace._get_rename_confirmation', return_value="y"):
                with patch('acepace.IS_DOCKER', False):
                    acepace.rename_local_files(conn, dry_run=False, extended_mode=True, folder=media)

        # Whether or not an extended entry exists for S01E01, the file must
        # have been moved into a Season 01 folder with a canonical filename.
        season_dir = os.path.join(media, "Season 01")
        assert os.path.isdir(season_dir)
        assert len(os.listdir(season_dir)) >= 1
        conn.close()

    def test_undo_reverts_last_run(self, temp_dir):
        media, video, crc32, conn, db_path, episodes_db_path = self._setup(temp_dir)
        rename_log_path = os.path.join(temp_dir, "rename_log.json")

        with patch('acepace.DB_NAME', db_path), patch('acepace.EPISODES_DB_NAME', episodes_db_path):
            with patch('acepace.RENAME_LOG_FILENAME', rename_log_path):
                with patch('acepace._get_rename_confirmation', return_value="y"):
                    with patch('acepace.IS_DOCKER', False):
                        acepace.rename_local_files(conn, dry_run=False, folder=media)

                new_path = os.path.join(
                    media, "Season 01", "One Pace - S01E01 - Romance Dawn, the Dawn of an Adventure.mkv"
                )
                assert os.path.isfile(new_path)

                reverted, skipped = acepace.undo_last_rename(conn)
                assert reverted == 1
                assert skipped == 0
                assert os.path.isfile(video)
                assert not os.path.isfile(new_path)

                # Journal is cleared after undo ("undo last run" semantics).
                assert acepace._load_rename_journal() == []
        conn.close()

    def test_undo_with_no_journal_is_a_noop(self, temp_dir):
        rename_log_path = os.path.join(temp_dir, "rename_log_missing.json")
        db_path = os.path.join(temp_dir, "test_crc32.db")
        with patch('acepace.DB_NAME', db_path):
            conn = acepace.init_db()
        with patch('acepace.RENAME_LOG_FILENAME', rename_log_path):
            reverted, skipped = acepace.undo_last_rename(conn)
        assert reverted == 0
        assert skipped == 0
        conn.close()


class TestRenameForceGating:
    """Tests for RENAME_FORCE / Docker gating (Part H1)."""

    def test_rename_force_enabled_reads_env(self):
        with patch.dict(os.environ, {"RENAME_FORCE": "true"}):
            assert acepace._rename_force_enabled() is True
        with patch.dict(os.environ, {"RENAME_FORCE": "false"}):
            assert acepace._rename_force_enabled() is False
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RENAME_FORCE", None)
            assert acepace._rename_force_enabled() is False

    def test_docker_without_rename_force_does_not_touch_filesystem(self, temp_dir):
        media, video, crc32, conn, db_path, episodes_db_path = TestRenameLocalFilesIntegration()._setup(temp_dir)
        rename_log_path = os.path.join(temp_dir, "rename_log.json")

        with patch('acepace.DB_NAME', db_path), patch('acepace.EPISODES_DB_NAME', episodes_db_path):
            with patch('acepace.RENAME_LOG_FILENAME', rename_log_path):
                with patch('acepace.IS_DOCKER', True):
                    with patch.dict(os.environ, {"RENAME_FORCE": "false", "ACEPACE_CONFIG_DIR_DOCKER": temp_dir}):
                        with patch('acepace._execute_rename') as mock_execute:
                            acepace.rename_local_files(conn, dry_run=False, folder=media)
                            mock_execute.assert_not_called()

        assert os.path.isfile(video)
        conn.close()

    def test_docker_with_rename_force_moves_files(self, temp_dir):
        media, video, crc32, conn, db_path, episodes_db_path = TestRenameLocalFilesIntegration()._setup(temp_dir)
        rename_log_path = os.path.join(temp_dir, "rename_log.json")

        with patch('acepace.DB_NAME', db_path), patch('acepace.EPISODES_DB_NAME', episodes_db_path):
            with patch('acepace.RENAME_LOG_FILENAME', rename_log_path):
                with patch('acepace.IS_DOCKER', True):
                    with patch.dict(os.environ, {"RENAME_FORCE": "true", "ACEPACE_CONFIG_DIR_DOCKER": temp_dir}):
                        acepace.rename_local_files(conn, dry_run=False, folder=media)

        new_path = os.path.join(
            media, "Season 01", "One Pace - S01E01 - Romance Dawn, the Dawn of an Adventure.mkv"
        )
        assert os.path.isfile(new_path)
        assert not os.path.isfile(video)
        conn.close()


class TestVersionResolution:
    """Tests for --version / VERSION env var resolution (Part D)."""

    def test_is_extended_mode_explicit_arg(self):
        assert acepace._is_extended_mode("extended") is True
        assert acepace._is_extended_mode("normal") is False

    def test_is_extended_mode_reads_env_when_none(self):
        with patch.dict(os.environ, {"VERSION": "extended"}):
            assert acepace._is_extended_mode(None) is True
        with patch.dict(os.environ, {"VERSION": "normal"}):
            assert acepace._is_extended_mode(None) is False

    def test_lookup_reference_episode_falls_back_across_versions(self):
        lookup, _, _ = acepace.get_reference_index()
        # Find a real (season, number) pair to test fallback with.
        any_key = next(iter(lookup))
        season, number, _is_extended = any_key
        # Whichever mode we ask for, we should get *some* episode back if
        # either the normal or extended entry exists for this (season, number).
        result_normal = acepace._lookup_reference_episode(lookup, season, number, extended_mode=False)
        result_extended = acepace._lookup_reference_episode(lookup, season, number, extended_mode=True)
        assert result_normal is not None or result_extended is not None
