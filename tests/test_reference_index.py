"""Unit tests for reference_index (vendored one-pace-for-plex snapshot)."""
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path to import reference_index
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import reference_index
from reference_index import Episode, get_reference_index, refresh_reference_index


@pytest.fixture
def vendored_dir(tmp_path):
    """Build a small, hand-written vendored snapshot directory."""
    base = tmp_path / "one-pace-for-plex"
    base.mkdir()

    seasons = {"Romance Dawn": 1, "Orange Town": 2, "Skypiea": 16}
    exceptions = {"Season 7": {"The Adventures of Buggy's Crew": 1}}
    episodes = [
        {
            "season": 1,
            "number": 1,
            "title": "Romance Dawn, the Dawn of an Adventure",
            "extended": "",
            "nfo_path": "One Pace/Season 1/One Pace - S01E01 - Romance Dawn, the Dawn of an Adventure.nfo",
        },
        {
            "season": 16,
            "number": 24,
            "title": "A Storm Coming",
            "extended": "",
            "nfo_path": "One Pace/Season 16/One Pace - S16E24 - A Storm Coming.nfo",
        },
        {
            "season": 16,
            "number": 25,
            "title": "Finale",
            "extended": "Alternate (G-8)",
            "nfo_path": "One Pace/Season 16/One Pace - S16E25 - Finale (Alternate (G-8)).nfo",
        },
    ]

    (base / "seasons.json").write_text(json.dumps(seasons), encoding="utf-8")
    (base / "exceptions.json").write_text(json.dumps(exceptions), encoding="utf-8")
    (base / "episodes_index.json").write_text(json.dumps(episodes), encoding="utf-8")
    (base / "metadata.json").write_text(
        json.dumps({"last_refresh": "2024-01-01T00:00:00+00:00"}), encoding="utf-8"
    )
    return base


class TestGetReferenceIndex:
    def test_loads_vendored_snapshot(self, vendored_dir):
        lookup, seasons, exceptions = get_reference_index(base_dir=vendored_dir)

        assert seasons == {"Romance Dawn": 1, "Orange Town": 2, "Skypiea": 16}
        assert exceptions == {"Season 7": {"The Adventures of Buggy's Crew": 1}}
        assert len(lookup) == 3

    def test_lookup_key_shape_and_values(self, vendored_dir):
        lookup, _, _ = get_reference_index(base_dir=vendored_dir)

        episode = lookup[(1, 1, False)]
        assert isinstance(episode, Episode)
        assert episode.season == 1
        assert episode.number == 1
        assert episode.title == "Romance Dawn, the Dawn of an Adventure"
        assert episode.extended == ""

    def test_extended_episode_keyed_separately(self, vendored_dir):
        lookup, _, _ = get_reference_index(base_dir=vendored_dir)

        assert (16, 25, True) in lookup
        assert (16, 25, False) not in lookup
        assert lookup[(16, 25, True)].extended == "Alternate (G-8)"

    def test_missing_vendored_files_returns_empty_fallback(self, tmp_path):
        empty_dir = tmp_path / "does-not-exist"
        lookup, seasons, exceptions = get_reference_index(base_dir=empty_dir)

        assert lookup == {}
        assert seasons == {}
        assert exceptions == {}

    def test_malformed_episode_entry_is_skipped(self, tmp_path):
        base = tmp_path / "one-pace-for-plex"
        base.mkdir()
        (base / "seasons.json").write_text("{}", encoding="utf-8")
        (base / "exceptions.json").write_text("{}", encoding="utf-8")
        (base / "episodes_index.json").write_text(
            json.dumps([{"season": 1}]),  # missing required fields
            encoding="utf-8",
        )

        lookup, _, _ = get_reference_index(base_dir=base)
        assert lookup == {}


class TestRefreshReferenceIndex:
    def _mock_response(self, status_code=200, json_data=None, text=None):
        resp = MagicMock()
        resp.status_code = status_code
        if json_data is not None:
            resp.json.return_value = json_data
        if text is not None:
            resp.text = text
        return resp

    @patch("reference_index.requests")
    def test_successful_refresh_writes_files(self, mock_requests, tmp_path):
        tree_json = {
            "sha": "abc123",
            "tree": [
                {
                    "path": "One Pace/Season 1/One Pace - S01E01 - Romance Dawn, the Dawn of an Adventure.nfo",
                    "type": "blob",
                },
                {"path": "One Pace/Season 1/season.nfo", "type": "blob"},
                {"path": "One Pace/tvshow.nfo", "type": "blob"},
                {"path": "README.md", "type": "blob"},
            ],
        }
        seasons_json = {"Romance Dawn": 1}
        exceptions_json = {}

        mock_requests.get.side_effect = [
            self._mock_response(json_data=tree_json),
            self._mock_response(json_data=seasons_json),
            self._mock_response(json_data=exceptions_json),
            self._mock_response(text="<tvshow></tvshow>"),
        ]
        mock_requests.RequestException = Exception

        base_dir = tmp_path / "one-pace-for-plex"
        result = refresh_reference_index(base_dir=base_dir, timeout=5)

        assert result is True
        assert (base_dir / "episodes_index.json").is_file()
        assert (base_dir / "seasons.json").is_file()
        assert (base_dir / "exceptions.json").is_file()
        assert (base_dir / "metadata.json").is_file()

        episodes = json.loads((base_dir / "episodes_index.json").read_text())
        assert len(episodes) == 1
        assert episodes[0]["season"] == 1
        assert episodes[0]["number"] == 1

    @patch("reference_index.requests")
    def test_failed_tree_fetch_keeps_existing_vendored_data(self, mock_requests, vendored_dir):
        mock_requests.get.return_value = self._mock_response(status_code=500)
        mock_requests.RequestException = Exception

        before = (vendored_dir / "seasons.json").read_text()
        result = refresh_reference_index(base_dir=vendored_dir, timeout=5)

        assert result is False
        after = (vendored_dir / "seasons.json").read_text()
        assert before == after

    @patch("reference_index.requests")
    def test_network_exception_keeps_existing_vendored_data(self, mock_requests, vendored_dir):
        class FakeRequestException(Exception):
            pass

        mock_requests.RequestException = FakeRequestException
        mock_requests.get.side_effect = FakeRequestException("boom")

        before = (vendored_dir / "episodes_index.json").read_text()
        result = refresh_reference_index(base_dir=vendored_dir, timeout=5)

        assert result is False
        after = (vendored_dir / "episodes_index.json").read_text()
        assert before == after

    def test_refresh_without_requests_installed(self, vendored_dir):
        with patch.object(reference_index, "requests", None):
            result = refresh_reference_index(base_dir=vendored_dir, timeout=5)
        assert result is False


class TestVendoredRepoSnapshot:
    """Sanity checks against the real vendored data committed to the repo."""

    def test_real_vendored_snapshot_loads(self):
        lookup, seasons, exceptions = get_reference_index()
        assert len(seasons) > 0
        assert len(lookup) > 0
        # Spot check a couple of well-known entries.
        assert (1, 1, False) in lookup
        assert lookup[(1, 1, False)].title.startswith("Romance Dawn")
