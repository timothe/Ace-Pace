"""Gap-review coverage pass: tests for previously-untested acepace.py behavior.

Focus areas (see coverage.xml "Missing" column for acepace.py before this file
was added): URL validation, magnet-link loading/dedup, missing-episode CSV
save/load, report header bookkeeping, version-aware missing detection
integration (_calculate_missing_episodes / _calculate_and_find_missing /
_generate_missing_episodes_report), episodes-update decision logic, the
rename/download/doctor/undo command dispatch in _handle_main_commands and
main(), and folder-resolution helpers.
"""
import argparse
import csv
import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import acepace


def _args(**overrides):
    base = dict(
        folder=None, client=None, host=None, port=None, username=None, password=None,
        url=f"{acepace.NYAA_BASE_URL}/?f=0&c=0_0&q=one+pace&o=asc",
        db=False, download=False, rename=False, episodes_update=False,
        dry_run=False, version="normal", undo=False, quiet=False, verbose=False,
        doctor=False, help=False, download_folder=None, tag=None, category=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


class TestValidateUrl:
    def test_valid_nyaa_url_passes(self):
        assert acepace._validate_url(f"{acepace.NYAA_BASE_URL}/?f=0&c=0_0&q=one+pace") is True

    def test_valid_nyaa_land_url_passes(self):
        assert acepace._validate_url("https://nyaa.land/?f=0&c=0_0&q=one+pace") is True

    def test_invalid_domain_fails(self):
        assert acepace._validate_url("https://evil.example.com/?q=one+pace") is False


class TestLoadMagnetLinks:
    def test_missing_csv_returns_none(self, temp_dir):
        csv_path = os.path.join(temp_dir, "Ace-Pace_Missing.csv")
        with patch('acepace.MISSING_CSV_FILENAME', csv_path):
            assert acepace._load_magnet_links() is None

    def test_no_magnet_links_returns_none(self, temp_dir):
        csv_path = os.path.join(temp_dir, "Ace-Pace_Missing.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Title", "Page Link", "Magnet Link"])
            writer.writerow(["Some Episode", "https://nyaa.si/view/1", ""])
        with patch('acepace.MISSING_CSV_FILENAME', csv_path):
            assert acepace._load_magnet_links() is None

    def test_dedups_and_sorts_magnet_links(self, temp_dir):
        csv_path = os.path.join(temp_dir, "Ace-Pace_Missing.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Title", "Page Link", "Magnet Link"])
            writer.writerow(["Ep1", "https://nyaa.si/view/1", "magnet:?xt=urn:btih:bbb"])
            writer.writerow(["Ep2 (grouped)", "https://nyaa.si/view/1", "magnet:?xt=urn:btih:bbb"])
            writer.writerow(["Ep3", "https://nyaa.si/view/2", "magnet:?xt=urn:btih:aaa"])
        with patch('acepace.MISSING_CSV_FILENAME', csv_path):
            magnets = acepace._load_magnet_links()
        assert magnets == ["magnet:?xt=urn:btih:aaa", "magnet:?xt=urn:btih:bbb"]


class TestLoadOldMissingCrc32s:
    def test_no_file_returns_empty_set(self, temp_dir):
        csv_path = os.path.join(temp_dir, "Ace-Pace_Missing.csv")
        with patch('acepace.MISSING_CSV_FILENAME', csv_path):
            assert acepace._load_old_missing_crc32s() == set()

    def test_extracts_crc32_from_titles(self, temp_dir):
        csv_path = os.path.join(temp_dir, "Ace-Pace_Missing.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Title", "Page Link", "Magnet Link"])
            writer.writerow(["[One Pace] Ep [1080p][AAAAAAAA].mkv", "", ""])
            writer.writerow(["[One Pace] Ep [1080p][bbbbbbbb].mkv", "", ""])
            writer.writerow(["No crc32 here", "", ""])
        with patch('acepace.MISSING_CSV_FILENAME', csv_path):
            crc32s = acepace._load_old_missing_crc32s()
        assert crc32s == {"AAAAAAAA", "BBBBBBBB"}


class TestSaveMissingEpisodesCsv:
    def test_writes_rows_for_each_missing_episode(self, temp_dir):
        csv_path = os.path.join(temp_dir, "Ace-Pace_Missing.csv")
        crc32_to_text = {"AAAAAAAA": "Episode A", "BBBBBBBB": "Episode B"}
        crc32_to_link = {"AAAAAAAA": "https://nyaa.si/view/1"}
        crc32_to_magnet = {"AAAAAAAA": "magnet:?xt=1", "BBBBBBBB": "magnet:?xt=2"}
        with patch('acepace.MISSING_CSV_FILENAME', csv_path):
            acepace._save_missing_episodes_csv(
                ["AAAAAAAA", "BBBBBBBB"], crc32_to_text, crc32_to_link, crc32_to_magnet
            )
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["Title", "Page Link", "Magnet Link"]
        assert rows[1] == ["Episode A", "https://nyaa.si/view/1", "magnet:?xt=1"]
        assert rows[2] == ["Episode B", "", "magnet:?xt=2"]

    def test_missing_title_falls_back_to_crc32_placeholder(self, temp_dir):
        csv_path = os.path.join(temp_dir, "Ace-Pace_Missing.csv")
        with patch('acepace.MISSING_CSV_FILENAME', csv_path):
            acepace._save_missing_episodes_csv(["ZZZZZZZZ"], {}, {}, {})
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert rows[1][0] == "[CRC32: ZZZZZZZZ]"


class TestPrintReportHeader:
    def test_sets_last_run_metadata_and_returns_previous_value(self, temp_dir):
        db_path = os.path.join(temp_dir, "crc32.db")
        with patch('acepace.DB_NAME', db_path):
            conn = acepace.init_db()
            acepace.set_metadata(conn, "last_run", "2020-01-01 00:00:00")
            last_run = acepace._print_report_header(conn, temp_dir, _args(url=f"{acepace.NYAA_BASE_URL}/?f=0&q=one+pace"))
            assert last_run == "2020-01-01 00:00:00"
            # last_run metadata is refreshed to "now" by the call.
            assert acepace.get_metadata(conn, "last_run") != "2020-01-01 00:00:00"
            conn.close()

    def test_first_run_has_no_previous_last_run(self, temp_dir):
        db_path = os.path.join(temp_dir, "crc32.db")
        with patch('acepace.DB_NAME', db_path):
            conn = acepace.init_db()
            last_run = acepace._print_report_header(conn, temp_dir, _args(url=f"{acepace.NYAA_BASE_URL}/?f=0&q=one+pace"))
            assert last_run is None
            conn.close()


class TestNormalizeCrc32Sets:
    def test_uppercases_and_strips(self):
        crc32_to_link = {" aaaaaaaa": "link1", "BBBBBBBB": "link2"}
        local_crc32s = {"aaaaaaaa ", "cccccccc"}
        nyaa, local = acepace._normalize_crc32_sets(crc32_to_link, local_crc32s)
        assert nyaa == {"AAAAAAAA", "BBBBBBBB"}
        assert local == {"AAAAAAAA", "CCCCCCCC"}


class TestShouldForceEpisodesUpdate:
    def test_no_last_update_forces_update(self):
        assert acepace._should_force_episodes_update(None) is True

    def test_recent_update_skips_forced_update(self):
        now_str = acepace.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        assert acepace._should_force_episodes_update(now_str) is False

    def test_stale_update_forces_update(self):
        assert acepace._should_force_episodes_update("2000-01-01 00:00:00") is True

    def test_unparseable_timestamp_forces_update(self):
        assert acepace._should_force_episodes_update("not-a-date") is True


class TestHandleEpisodesUpdateDecision:
    def test_force_update_env_triggers_update_when_stale(self):
        with patch('acepace.update_episodes_index_db') as mock_update:
            result = acepace._handle_episodes_update_decision(True, None, "url")
            mock_update.assert_called_once_with("url", force_update=True)
        assert result is True

    def test_force_update_env_skips_when_recent(self):
        now_str = acepace.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with patch('acepace.update_episodes_index_db') as mock_update:
            result = acepace._handle_episodes_update_decision(True, now_str, "url")
            mock_update.assert_not_called()
        assert result is True

    def test_no_force_uses_database_when_last_update_exists(self):
        result = acepace._handle_episodes_update_decision(False, "2020-01-01 00:00:00", "url")
        assert result is True

    def test_no_force_and_no_prior_update_falls_back_to_fetch(self):
        result = acepace._handle_episodes_update_decision(False, None, "url")
        assert result is False


class TestLoadEpisodesFromDatabase:
    def _seed_db(self, episodes_db_path):
        with patch('acepace.EPISODES_DB_NAME', episodes_db_path):
            conn = acepace.init_episodes_db()
            conn.execute(
                "INSERT INTO episodes_index (crc32, title, page_link, magnet_link, pub_date) "
                "VALUES (?, ?, ?, ?, ?)",
                ("AAAAAAAA", "[One Pace] Ep [1080p][AAAAAAAA].mkv", "link1", "magnet:?xt=1", "1000"),
            )
            conn.execute(
                "INSERT INTO episodes_index (crc32, title, page_link, magnet_link, pub_date) "
                "VALUES (?, ?, ?, ?, ?)",
                ("BBBBBBBB", "[One Pace] Ep2 [1080p][BBBBBBBB].mkv", "link2", "", "2000"),
            )
            conn.commit()
            conn.close()

    def test_loads_episodes_with_existing_magnets_no_fetch_needed(self, temp_dir):
        episodes_db_path = os.path.join(temp_dir, "episodes.db")
        self._seed_db(episodes_db_path)
        with patch('acepace.EPISODES_DB_NAME', episodes_db_path):
            with patch('acepace.fetch_magnet_links_for_episodes_from_search') as mock_fetch:
                mock_fetch.return_value = {"BBBBBBBB": "magnet:?xt=2"}
                crc32_to_link, crc32_to_text, crc32_to_magnet, crc32_to_pubdate, last_page = (
                    acepace._load_episodes_from_database(False, "url", fetch_magnets=True)
                )
        # BBBBBBBB had no magnet in DB, so fetch should have been attempted.
        mock_fetch.assert_called_once()
        assert crc32_to_magnet == {"AAAAAAAA": "magnet:?xt=1", "BBBBBBBB": "magnet:?xt=2"}
        assert set(crc32_to_link) == {"AAAAAAAA", "BBBBBBBB"}
        assert last_page == 0

    def test_fetch_magnets_false_skips_fetch_and_filters_missing(self, temp_dir):
        episodes_db_path = os.path.join(temp_dir, "episodes.db")
        self._seed_db(episodes_db_path)
        with patch('acepace.EPISODES_DB_NAME', episodes_db_path):
            with patch('acepace.fetch_magnet_links_for_episodes_from_search') as mock_fetch:
                crc32_to_link, crc32_to_text, crc32_to_magnet, crc32_to_pubdate, last_page = (
                    acepace._load_episodes_from_database(True, "url", fetch_magnets=False)
                )
        mock_fetch.assert_not_called()
        # Only AAAAAAAA has a magnet link -> BBBBBBBB (no magnet) is filtered out.
        assert crc32_to_magnet == {"AAAAAAAA": "magnet:?xt=1"}
        assert "BBBBBBBB" not in crc32_to_link


class TestCalculateMissingEpisodes:
    """Integration of grouping + normalization for the live missing-detection path."""

    def test_reports_newest_version_when_no_version_present_locally(self):
        crc32_to_text = {
            "OLD00001": "[One Pace][1-5] Romance Dawn 03 [1080p][OLD00001].mkv",
            "NEW00001": "[One Pace][1-5] Romance Dawn 03 [1080p][NEW00001].mkv",
        }
        crc32_to_link = {"OLD00001": "link1", "NEW00001": "link2"}
        crc32_to_magnet = {"OLD00001": "magnet:?xt=old", "NEW00001": "magnet:?xt=new"}
        crc32_to_pubdate = {"OLD00001": "1000", "NEW00001": "5000"}

        missing = acepace._calculate_missing_episodes(
            crc32_to_link, crc32_to_text, crc32_to_magnet, crc32_to_pubdate, local_crc32s=set()
        )
        assert missing == ["NEW00001"]

    def test_present_via_any_version_is_not_missing(self):
        crc32_to_text = {
            "OLD00002": "[One Pace][1-5] Romance Dawn 04 [1080p][OLD00002].mkv",
            "NEW00002": "[One Pace][1-5] Romance Dawn 04 [1080p][NEW00002].mkv",
        }
        crc32_to_link = {"OLD00002": "link1", "NEW00002": "link2"}
        crc32_to_magnet = {"OLD00002": "magnet:?xt=old", "NEW00002": "magnet:?xt=new"}
        crc32_to_pubdate = {"OLD00002": "1000", "NEW00002": "5000"}

        missing = acepace._calculate_missing_episodes(
            crc32_to_link, crc32_to_text, crc32_to_magnet, crc32_to_pubdate,
            local_crc32s={"old00002"},  # lowercase local hash, must still normalize-match
        )
        assert missing == []


class TestCalculateAndFindMissing:
    def test_uses_database_path_when_recently_updated(self, temp_dir):
        episodes_db_path = os.path.join(temp_dir, "episodes.db")
        db_path = os.path.join(temp_dir, "crc32.db")
        with patch('acepace.EPISODES_DB_NAME', episodes_db_path):
            conn = acepace.init_episodes_db()
            now_str = acepace.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            acepace.set_episodes_metadata(conn, "episodes_db_last_update", now_str)
            conn.close()

        with patch('acepace.DB_NAME', db_path):
            crc32_conn = acepace.init_db()

        fake_load = (
            {"AAAAAAAA": "link"},
            {"AAAAAAAA": "[One Pace][1-5] Romance Dawn 05 [1080p][AAAAAAAA].mkv"},
            {"AAAAAAAA": "magnet:?xt=a"},
            {"AAAAAAAA": "1000"},
            0,
        )
        with patch('acepace.EPISODES_DB_NAME', episodes_db_path), \
             patch('acepace.DB_NAME', db_path), \
             patch('acepace._load_episodes_from_database', return_value=fake_load) as mock_load, \
             patch('acepace.calculate_local_crc32', return_value=set()) as mock_calc, \
             patch('acepace.fetch_crc32_links') as mock_fetch:
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("EPISODES_UPDATE", None)
                missing, crc32_to_text, crc32_to_link, crc32_to_magnet, last_checked_page = (
                    acepace._calculate_and_find_missing(temp_dir, crc32_conn, _args(url="u"), last_run=None)
                )
        mock_load.assert_called_once()
        mock_fetch.assert_not_called()
        assert missing == ["AAAAAAAA"]
        crc32_conn.close()

    def test_falls_back_to_nyaa_fetch_when_no_database_history(self, temp_dir):
        episodes_db_path = os.path.join(temp_dir, "episodes.db")
        db_path = os.path.join(temp_dir, "crc32.db")
        with patch('acepace.DB_NAME', db_path):
            crc32_conn = acepace.init_db()

        with patch('acepace.EPISODES_DB_NAME', episodes_db_path), \
             patch('acepace.DB_NAME', db_path), \
             patch('acepace.fetch_crc32_links', return_value=({}, {}, {}, 0)) as mock_fetch, \
             patch('acepace.calculate_local_crc32', return_value=set()):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("EPISODES_UPDATE", None)
                missing, crc32_to_text, crc32_to_link, crc32_to_magnet, last_checked_page = (
                    acepace._calculate_and_find_missing(temp_dir, crc32_conn, _args(url="u"), last_run=None)
                )
        mock_fetch.assert_called_once_with("u")
        assert missing == []
        crc32_conn.close()


class TestGenerateMissingEpisodesReport:
    def test_generates_report_and_persists_metadata(self, temp_dir):
        db_path = os.path.join(temp_dir, "crc32.db")
        csv_path = os.path.join(temp_dir, "Ace-Pace_Missing.csv")
        with patch('acepace.DB_NAME', db_path):
            conn = acepace.init_db()

        fake_missing_result = (
            ["AAAAAAAA"],
            {"AAAAAAAA": "Episode A"},
            {"AAAAAAAA": "link1"},
            {"AAAAAAAA": "magnet:?xt=1"},
            3,
        )
        with patch('acepace.DB_NAME', db_path), \
             patch('acepace.MISSING_CSV_FILENAME', csv_path), \
             patch('acepace._calculate_and_find_missing', return_value=fake_missing_result):
            missing, crc32_to_text = acepace._generate_missing_episodes_report(
                conn, temp_dir, _args(url=f"{acepace.NYAA_BASE_URL}/?f=0&q=one+pace")
            )

        assert missing == ["AAAAAAAA"]
        assert crc32_to_text == {"AAAAAAAA": "Episode A"}
        assert os.path.isfile(csv_path)
        assert acepace.get_metadata(conn, "last_checked_page") == "3"
        assert acepace.get_metadata(conn, "last_missing_export") is not None
        conn.close()


class TestGetRenamePrompt:
    def test_docker_updates_when_never_updated(self):
        with patch('acepace.IS_DOCKER', True):
            assert acepace._get_rename_prompt(None) == "y"

    def test_docker_skips_when_already_updated(self):
        with patch('acepace.IS_DOCKER', True):
            assert acepace._get_rename_prompt("2020-01-01 00:00:00") == "n"

    def test_non_docker_prompts_user(self):
        with patch('acepace.IS_DOCKER', False):
            with patch('builtins.input', return_value="Y") as mock_input:
                result = acepace._get_rename_prompt(None)
        mock_input.assert_called_once()
        assert result == "y"

    def test_non_docker_prompts_with_last_update_shown(self):
        with patch('acepace.IS_DOCKER', False):
            with patch('builtins.input', return_value="n") as mock_input:
                result = acepace._get_rename_prompt("2020-01-01 00:00:00")
        assert "last update" in mock_input.call_args[0][0]
        assert result == "n"


class TestHandleRenameCommand:
    def test_declines_episodes_update_and_skips_crc32_check_without_folder(self, temp_dir):
        episodes_db_path = os.path.join(temp_dir, "episodes.db")
        db_path = os.path.join(temp_dir, "crc32.db")
        with patch('acepace.DB_NAME', db_path):
            conn = acepace.init_db()
        with patch('acepace.EPISODES_DB_NAME', episodes_db_path), \
             patch('acepace.DB_NAME', db_path), \
             patch('acepace._get_rename_prompt', return_value="n"), \
             patch('acepace.update_episodes_index_db') as mock_update, \
             patch('acepace._ensure_crc32_cache_complete') as mock_ensure, \
             patch('acepace.rename_local_files') as mock_rename:
            acepace._handle_rename_command(conn, base_url="u", dry_run=True, folder=None)
        mock_update.assert_not_called()
        mock_ensure.assert_not_called()
        mock_rename.assert_called_once_with(conn, dry_run=True, extended_mode=False, folder=None)
        conn.close()

    def test_accepts_episodes_update_and_checks_crc32_cache_with_folder(self, temp_dir):
        episodes_db_path = os.path.join(temp_dir, "episodes.db")
        db_path = os.path.join(temp_dir, "crc32.db")
        with patch('acepace.DB_NAME', db_path):
            conn = acepace.init_db()
        with patch('acepace.EPISODES_DB_NAME', episodes_db_path), \
             patch('acepace.DB_NAME', db_path), \
             patch('acepace._get_rename_prompt', return_value="y"), \
             patch('acepace.update_episodes_index_db') as mock_update, \
             patch('acepace._ensure_crc32_cache_complete') as mock_ensure, \
             patch('acepace.rename_local_files') as mock_rename:
            acepace._handle_rename_command(conn, base_url="u", dry_run=False, folder=temp_dir, extended_mode=True)
        mock_update.assert_called_once_with("u")
        mock_ensure.assert_called_once_with(temp_dir, conn)
        mock_rename.assert_called_once_with(conn, dry_run=False, extended_mode=True, folder=temp_dir)
        conn.close()


class TestHandleDownloadCommand:
    def test_no_magnet_links_returns_false(self):
        with patch('acepace.IS_DOCKER', False):
            with patch('acepace._load_magnet_links', return_value=None):
                assert acepace._handle_download_command(_args(client="transmission")) is False

    def test_non_docker_missing_client_returns_false(self):
        with patch('acepace.IS_DOCKER', False):
            assert acepace._handle_download_command(_args(client=None)) is False

    def test_connection_error_is_handled(self):
        with patch('acepace.IS_DOCKER', False):
            with patch('acepace._load_magnet_links', return_value=["magnet:?xt=1"]):
                with patch('acepace.get_client', side_effect=ConnectionError("boom")):
                    result = acepace._handle_download_command(_args(client="transmission"))
        assert result is False

    def test_value_error_is_handled(self):
        with patch('acepace.IS_DOCKER', False):
            with patch('acepace._load_magnet_links', return_value=["magnet:?xt=1"]):
                with patch('acepace.get_client', side_effect=ValueError("bad config")):
                    result = acepace._handle_download_command(_args(client="transmission"))
        assert result is False

    def test_unexpected_exception_is_handled(self):
        with patch('acepace.IS_DOCKER', False):
            with patch('acepace._load_magnet_links', return_value=["magnet:?xt=1"]):
                with patch('acepace.get_client', side_effect=RuntimeError("weird")):
                    result = acepace._handle_download_command(_args(client="transmission"))
        assert result is False

    def test_successful_dry_run_returns_true(self):
        mock_client_obj = MagicMock()
        with patch('acepace.IS_DOCKER', False):
            with patch('acepace._load_magnet_links', return_value=["magnet:?xt=1"]):
                with patch('acepace.get_client', return_value=mock_client_obj):
                    result = acepace._handle_download_command(
                        _args(client="transmission", dry_run=True, tag=["t1"], category="cat")
                    )
        assert result is True
        mock_client_obj.add_torrents.assert_called_once()
        assert mock_client_obj.add_torrents.call_args.kwargs["dry_run"] is True

    def test_successful_real_run_returns_true(self):
        mock_client_obj = MagicMock()
        with patch('acepace.IS_DOCKER', False):
            with patch('acepace._load_magnet_links', return_value=["magnet:?xt=1"]):
                with patch('acepace.get_client', return_value=mock_client_obj):
                    result = acepace._handle_download_command(
                        _args(client="transmission", dry_run=False)
                    )
        assert result is True
        mock_client_obj.add_torrents.assert_called_once()
        assert "dry_run" not in mock_client_obj.add_torrents.call_args.kwargs


class TestHandleMainCommands:
    def test_download_dispatches_and_returns(self, temp_dir):
        with patch('acepace._handle_download_command') as mock_download, \
             patch('acepace._handle_rename_command') as mock_rename, \
             patch('acepace._generate_missing_episodes_report') as mock_report:
            acepace._handle_main_commands(_args(download=True), conn=MagicMock(), folder=None)
        mock_download.assert_called_once()
        mock_rename.assert_not_called()
        mock_report.assert_not_called()

    def test_rename_dispatches_with_extended_mode_resolved(self, temp_dir):
        with patch('acepace._handle_rename_command') as mock_rename:
            acepace._handle_main_commands(
                _args(rename=True, version="extended"), conn=MagicMock(), folder=temp_dir
            )
        mock_rename.assert_called_once()
        _, kwargs = mock_rename.call_args
        assert kwargs["extended_mode"] is True
        assert kwargs["folder"] == temp_dir

    def test_missing_folder_prints_error_and_does_not_report(self, capsys):
        with patch('acepace._generate_missing_episodes_report') as mock_report:
            acepace._handle_main_commands(_args(), conn=MagicMock(), folder=None)
        mock_report.assert_not_called()
        assert "--folder argument is required" in capsys.readouterr().out

    def test_db_flag_exports_csv(self):
        conn = MagicMock()
        with patch('acepace.export_db_to_csv') as mock_export, \
             patch('acepace._generate_missing_episodes_report') as mock_report:
            acepace._handle_main_commands(_args(db=True), conn=conn, folder="/some/folder")
        mock_export.assert_called_once_with(conn)
        mock_report.assert_not_called()

    def test_default_generates_missing_report(self):
        conn = MagicMock()
        args = _args()
        with patch('acepace._generate_missing_episodes_report') as mock_report:
            acepace._handle_main_commands(args, conn=conn, folder="/some/folder")
        mock_report.assert_called_once_with(conn, "/some/folder", args)


class TestGetFolderFromArgs:
    def test_docker_uses_default_media_dir_and_records_metadata(self, temp_dir):
        db_path = os.path.join(temp_dir, "crc32.db")
        with patch('acepace.DB_NAME', db_path):
            conn = acepace.init_db()
        with patch('acepace.IS_DOCKER', True):
            with patch('acepace._get_default_media_dir', return_value="/media"):
                folder = acepace._get_folder_from_args(_args(folder=None), conn, needs_folder=True)
        assert folder == "/media"
        assert acepace.get_metadata(conn, "last_folder") == "/media"
        conn.close()

    def test_non_docker_no_folder_no_default_prompts_interactively(self, temp_dir):
        db_path = os.path.join(temp_dir, "crc32.db")
        with patch('acepace.DB_NAME', db_path):
            conn = acepace.init_db()
        with patch('acepace.IS_DOCKER', False):
            with patch('acepace._get_default_media_dir', return_value=""):
                with patch('builtins.input', return_value=temp_dir):
                    folder = acepace._get_folder_from_args(_args(folder=None), conn, needs_folder=True)
        assert folder == temp_dir
        assert acepace.get_metadata(conn, "last_folder") == temp_dir
        conn.close()

    def test_non_docker_uses_default_media_dir_when_set(self, temp_dir):
        db_path = os.path.join(temp_dir, "crc32.db")
        with patch('acepace.DB_NAME', db_path):
            conn = acepace.init_db()
        with patch('acepace.IS_DOCKER', False):
            with patch('acepace._get_default_media_dir', return_value=temp_dir):
                folder = acepace._get_folder_from_args(_args(folder=None), conn, needs_folder=True)
        assert folder == temp_dir
        assert acepace.get_metadata(conn, "last_folder") == temp_dir
        conn.close()

    def test_folder_provided_records_metadata(self, temp_dir):
        db_path = os.path.join(temp_dir, "crc32.db")
        with patch('acepace.DB_NAME', db_path):
            conn = acepace.init_db()
        with patch('acepace.IS_DOCKER', False):
            folder = acepace._get_folder_from_args(_args(folder=temp_dir), conn, needs_folder=True)
        assert folder == temp_dir
        assert acepace.get_metadata(conn, "last_folder") == temp_dir
        conn.close()

    def test_prompt_interactive_uses_last_folder_default(self, temp_dir):
        db_path = os.path.join(temp_dir, "crc32.db")
        with patch('acepace.DB_NAME', db_path):
            conn = acepace.init_db()
            acepace.set_metadata(conn, "last_folder", temp_dir)
        with patch('builtins.input', return_value=""):
            folder = acepace._prompt_folder_interactive(conn)
        assert folder == temp_dir
        conn.close()

    def test_prompt_interactive_no_input_and_no_last_folder_returns_none(self, temp_dir):
        db_path = os.path.join(temp_dir, "crc32.db")
        with patch('acepace.DB_NAME', db_path):
            conn = acepace.init_db()
        with patch('builtins.input', return_value=""):
            folder = acepace._prompt_folder_interactive(conn)
        assert folder is None
        conn.close()


class TestMainDispatch:
    """Exercises main()'s top-level dispatch branches (doctor/undo/help/url
    validation/episodes_update) without touching real network or filesystem
    beyond a scratch config dir."""

    def _run_main(self, argv, temp_dir, extra_patches=None):
        with patch.dict(os.environ, {"ACEPACE_CONFIG_DIR_LOCAL": temp_dir}, clear=False):
            with patch.object(sys, "argv", ["acepace.py"] + argv):
                with patch('acepace.signal.signal'):
                    try:
                        acepace.main()
                    except SystemExit as e:
                        return e.code
        return None

    def test_doctor_flag_exits_with_doctor_return_code(self, temp_dir):
        with patch('acepace.handle_doctor_command', return_value=0) as mock_doctor:
            code = self._run_main(["--doctor"], temp_dir)
        mock_doctor.assert_called_once()
        assert code == 0

    def test_doctor_flag_propagates_nonzero_exit(self, temp_dir):
        with patch('acepace.handle_doctor_command', return_value=1):
            code = self._run_main(["--doctor"], temp_dir)
        assert code == 1

    def test_undo_flag_exits_zero(self, temp_dir):
        with patch('acepace.undo_last_rename', return_value=(0, 0)) as mock_undo:
            code = self._run_main(["--undo"], temp_dir)
        mock_undo.assert_called_once()
        assert code == 0

    def test_help_flag_exits_zero(self, temp_dir):
        code = self._run_main(["--help"], temp_dir)
        assert code == 0

    def test_invalid_url_exits_one(self, temp_dir):
        code = self._run_main(["--url", "https://evil.example.com", "--folder", temp_dir], temp_dir)
        assert code == 1

    def test_episodes_update_flow_exits_zero(self, temp_dir):
        with patch('acepace.update_episodes_index_db') as mock_update, \
             patch('acepace._generate_missing_episodes_report') as mock_report:
            code = self._run_main(["--episodes_update", "--folder", temp_dir], temp_dir)
        mock_update.assert_called_once()
        mock_report.assert_called_once()
        assert code == 0

    def test_missing_folder_non_docker_exits_one_when_prompt_empty(self, temp_dir):
        with patch('acepace.IS_DOCKER', False):
            with patch('builtins.input', return_value=""):
                code = self._run_main([], temp_dir)
        assert code == 1

    def test_unhandled_exception_is_caught_and_exits_one(self, temp_dir):
        with patch('acepace._handle_main_commands', side_effect=RuntimeError("boom")):
            code = self._run_main(["--folder", temp_dir], temp_dir)
        assert code == 1


class TestMiscHelpers:
    def test_get_release_date_handles_oserror(self):
        with patch('acepace.os.path.getmtime', side_effect=OSError("nope")):
            assert acepace._get_release_date() == ""

    def test_normalize_file_path_falls_back_on_oserror(self, temp_dir):
        path = os.path.join(temp_dir, "does_not_exist.mkv")
        with patch('acepace.os.path.realpath', side_effect=OSError("nope")):
            result = acepace.normalize_file_path(path)
        assert os.path.isabs(result)

    def test_get_default_media_dir_docker_uses_env_override(self):
        with patch('acepace.IS_DOCKER', True):
            with patch.dict(os.environ, {"ACEPACE_MEDIA_DIR_DOCKER": "/custom/media"}):
                assert acepace._get_default_media_dir() == "/custom/media"

    def test_get_default_media_dir_docker_default(self):
        with patch('acepace.IS_DOCKER', True):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("ACEPACE_MEDIA_DIR_DOCKER", None)
                assert acepace._get_default_media_dir() == "/media"

    def test_print_header_docker_mode_shown(self, capsys):
        with patch('acepace.IS_DOCKER', True):
            acepace._print_header()
        out = capsys.readouterr().out
        assert "Running in Docker mode" in out
