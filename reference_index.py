"""Reference data module for the one-pace-for-plex canonical episode metadata.

This module fetches (and vendors a snapshot of) the canonical episode list
published by https://github.com/SpykerNZ/one-pace-for-plex, so Ace-Pace can
build a deterministic, Plex-friendly rename target without depending on live
network access at run time.

Vendored data lives under ``reference/one-pace-for-plex/`` (relative to this
file) and consists of:

- ``seasons.json``      -- arc name -> season number (37 entries upstream).
- ``exceptions.json``   -- season name -> {filename substring -> episode number}.
- ``episodes_index.json`` -- flat list of {season, number, title, extended,
  nfo_path} derived directly from the reference project's ``.nfo`` file paths
  (no XML content is vendored in this pass -- the path alone is enough to
  derive season/episode/title for naming purposes).
- ``metadata.json``     -- bookkeeping (last_refresh timestamp, source commit).
- ``tvshow.nfo``        -- vendored for later poster/season-name use.

Network access only happens inside :func:`refresh_reference_index`; reads
(:func:`get_reference_index`) are always local/offline by default.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

try:  # pragma: no cover - exercised indirectly via refresh_reference_index
    import requests  # type: ignore
except ImportError:  # pragma: no cover
    requests = None  # type: ignore


# --- Constants -------------------------------------------------------------

GITHUB_OWNER = "SpykerNZ"
GITHUB_REPO = "one-pace-for-plex"
GITHUB_BRANCH = "main"

GITHUB_TREE_URL = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/trees/"
    f"{GITHUB_BRANCH}?recursive=1"
)
RAW_BASE_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}"
)
SEASONS_JSON_URL = f"{RAW_BASE_URL}/dist/seasons.json"
EXCEPTIONS_JSON_URL = f"{RAW_BASE_URL}/dist/exceptions.json"
TVSHOW_NFO_URL = f"{RAW_BASE_URL}/One%20Pace/tvshow.nfo"

HTTP_OK = 200

DEFAULT_BASE_DIR = Path(__file__).resolve().parent / "reference" / "one-pace-for-plex"

SEASONS_FILENAME = "seasons.json"
EXCEPTIONS_FILENAME = "exceptions.json"
EPISODES_INDEX_FILENAME = "episodes_index.json"
METADATA_FILENAME = "metadata.json"
TVSHOW_NFO_FILENAME = "tvshow.nfo"

# Matches paths like:
#   One Pace/Season 16/One Pace - S16E24 - Title.nfo
#   One Pace/Season 16/One Pace - S16E25 - Finale (Alternate (G-8)).nfo
#   One Pace/Specials/One Pace - S00E01 - Strong World.nfo
NFO_PATH_PATTERN = re.compile(
    r"^One Pace/(?:Season \d+|Specials)/"
    r".*? - S(\d+)E(\d+) - (.*?)(?:\s\((\w[\w\s\(\)-]+)\))?\.nfo$"
)


@dataclass
class Episode:
    """A single canonical episode, as published by one-pace-for-plex."""

    season: int
    number: int
    title: str
    extended: str = ""
    nfo_path: str = ""


ReferenceLookup = Dict[Tuple[int, int, bool], Episode]


# --- Internal helpers --------------------------------------------------------


def _parse_episode_paths(nfo_paths):
    """Parse a list of ``.nfo`` blob paths into a list of Episode dataclasses.

    Skips ``season.nfo``/``tvshow.nfo`` (and anything else that doesn't match
    the expected pattern).
    """
    episodes = []
    for path in nfo_paths:
        name = path.rsplit("/", 1)[-1]
        if name in ("season.nfo", "tvshow.nfo"):
            continue
        match = NFO_PATH_PATTERN.match(path)
        if not match:
            continue
        season = int(match.group(1))
        number = int(match.group(2))
        title = match.group(3)
        extended = match.group(4) or ""
        episodes.append(
            Episode(
                season=season,
                number=number,
                title=title,
                extended=extended,
                nfo_path=path,
            )
        )
    episodes.sort(key=lambda e: (e.season, e.number, e.extended))
    return episodes


def _episode_to_dict(episode: Episode) -> dict:
    return {
        "season": episode.season,
        "number": episode.number,
        "title": episode.title,
        "extended": episode.extended,
        "nfo_path": episode.nfo_path,
    }


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# --- Public API --------------------------------------------------------------


def refresh_reference_index(base_dir: Optional[Path] = None, timeout: int = 10) -> bool:
    """Pull the latest seasons/exceptions/episode-list data from GitHub and
    vendor it into ``base_dir`` (default: ``reference/one-pace-for-plex/``
    next to this module).

    On any network or parsing failure, prints a clear message and leaves the
    existing vendored files untouched (never partially overwrites them).

    Returns True on success, False on failure.
    """
    base_dir = Path(base_dir) if base_dir is not None else DEFAULT_BASE_DIR

    if requests is None:
        print("reference_index: 'requests' is not installed, cannot refresh reference index.")
        return False

    try:
        tree_resp = requests.get(GITHUB_TREE_URL, timeout=timeout)
        if tree_resp.status_code != HTTP_OK:
            print(
                f"reference_index: failed to fetch git tree "
                f"(HTTP {tree_resp.status_code}); keeping existing vendored data."
            )
            return False
        tree_json = tree_resp.json()
        blobs = tree_json.get("tree", [])
        nfo_paths = [
            node["path"]
            for node in blobs
            if node.get("type") == "blob"
            and node.get("path", "").startswith("One Pace/")
            and node.get("path", "").endswith(".nfo")
        ]
        episodes = _parse_episode_paths(nfo_paths)
        if not episodes:
            print("reference_index: git tree contained no parsable episodes; keeping existing vendored data.")
            return False

        seasons_resp = requests.get(SEASONS_JSON_URL, timeout=timeout)
        if seasons_resp.status_code != HTTP_OK:
            print(
                f"reference_index: failed to fetch seasons.json "
                f"(HTTP {seasons_resp.status_code}); keeping existing vendored data."
            )
            return False
        seasons = seasons_resp.json()

        exceptions_resp = requests.get(EXCEPTIONS_JSON_URL, timeout=timeout)
        if exceptions_resp.status_code != HTTP_OK:
            print(
                f"reference_index: failed to fetch exceptions.json "
                f"(HTTP {exceptions_resp.status_code}); keeping existing vendored data."
            )
            return False
        exceptions = exceptions_resp.json()

        tvshow_nfo_text = None
        try:
            tvshow_resp = requests.get(TVSHOW_NFO_URL, timeout=timeout)
            if tvshow_resp.status_code == HTTP_OK:
                tvshow_nfo_text = tvshow_resp.text
        except requests.RequestException as exc:  # pragma: no cover - best effort
            print(f"reference_index: warning, could not fetch tvshow.nfo: {exc}")

    except (requests.RequestException, ValueError) as exc:
        print(f"reference_index: network/parse error while refreshing: {exc}; keeping existing vendored data.")
        return False

    # Everything fetched successfully -- now write it out atomically-ish
    # (each file write is independent, but we only get here once everything
    # has already been fetched and parsed, so we never write a half-refresh).
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        _write_json(base_dir / EPISODES_INDEX_FILENAME, [_episode_to_dict(e) for e in episodes])
        _write_json(base_dir / SEASONS_FILENAME, seasons)
        _write_json(base_dir / EXCEPTIONS_FILENAME, exceptions)
        if tvshow_nfo_text is not None:
            (base_dir / TVSHOW_NFO_FILENAME).write_text(tvshow_nfo_text, encoding="utf-8")

        metadata = {
            "last_refresh": datetime.now(timezone.utc).isoformat(),
            "source": f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}",
            "commit_sha": tree_json.get("sha"),
            "episode_count": len(episodes),
        }
        _write_json(base_dir / METADATA_FILENAME, metadata)
    except OSError as exc:
        print(f"reference_index: failed to write vendored data: {exc}")
        return False

    print(f"reference_index: refreshed {len(episodes)} episodes into {base_dir}")
    return True


def get_reference_index(base_dir: Optional[Path] = None):
    """Load the vendored reference snapshot and return
    ``(lookup, seasons, exceptions)``.

    - ``lookup`` is a dict keyed ``(season: int, number: int,
      is_extended: bool) -> Episode``.
    - ``seasons`` is the raw ``{arc_name: season_number}`` dict.
    - ``exceptions`` is the raw ``{season_name: {substring: episode_number}}``
      dict.

    Missing/unreadable vendored files degrade gracefully: a warning is
    printed and an empty dict is substituted so callers can keep running.
    """
    base_dir = Path(base_dir) if base_dir is not None else DEFAULT_BASE_DIR

    episodes_raw = _load_json_or_warn(base_dir / EPISODES_INDEX_FILENAME, default=[])
    seasons = _load_json_or_warn(base_dir / SEASONS_FILENAME, default={})
    exceptions = _load_json_or_warn(base_dir / EXCEPTIONS_FILENAME, default={})

    lookup: ReferenceLookup = {}
    for entry in episodes_raw:
        try:
            episode = Episode(
                season=int(entry["season"]),
                number=int(entry["number"]),
                title=entry["title"],
                extended=entry.get("extended", "") or "",
                nfo_path=entry.get("nfo_path", ""),
            )
        except (KeyError, TypeError, ValueError):
            print(f"reference_index: skipping malformed episode entry: {entry!r}")
            continue
        is_extended = bool(episode.extended)
        lookup[(episode.season, episode.number, is_extended)] = episode

    return lookup, seasons, exceptions


def _load_json_or_warn(path: Path, default):
    if not path.is_file():
        print(f"reference_index: vendored file missing: {path}; using empty fallback.")
        return default
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"reference_index: failed to read/parse {path}: {exc}; using empty fallback.")
        return default
