"""Parse One Pace release titles into a canonical (arc, season, number,
extended) tuple.

This is a port of the parsing logic in the reference project's
``dist/rename.py`` (``get_episode_from_media``), fetched from
https://raw.githubusercontent.com/SpykerNZ/one-pace-for-plex/main/dist/rename.py

It recognizes three release-title shapes, tried in this order:

1. Original One Pace format::

       [One Pace][12-19] Orange Town 02 [1080p][D7327225].mkv

   The bracket right after ``[One Pace]`` is the manga chapter range and is
   discarded. The arc name is everything between that bracket and the
   episode number. The episode number is ``\\d{1,2}(?:-\\d{1,2})?`` -- when a
   range is given (grouped episodes), the *leading* number is used. An
   optional extended/alternate suffix can appear in parentheses right before
   the quality/hash brackets.

2. "Paced One Piece" format::

       [One Pace] Paced One Piece - Skypiea Episode 24

3. Already-Plex format::

       One Pace - S16E24 - Some Title.mkv

   Season/episode are already explicit here, so no arc-name lookup is
   needed. ``arc`` is resolved via a reverse lookup into ``seasons`` (season
   number -> arc name) when possible/unambiguous, else left as ``None`` --
   this is documented behavior, not a bug: callers already have the season
   number they need.

Arc names go through normalization (``Whiskey`` -> ``Whisky``, ``Arabasta``
-> ``Alabasta``) before a case-insensitive lookup against the ``seasons``
dict (``{arc_name: season_number}``, as vendored by ``reference_index``).

Returns ``None`` when nothing matches, or when an arc-based format matches
but the arc name can't be resolved to a season -- callers decide how to
treat unrecognized/obsolete titles.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional


SHOW_NAME = "One Pace"
MEDIA_EXTENSIONS = r"(?:\.mkv|\.mp4)"

# Original One Pace format:
#   [One Pace][<chapters>] <Arc Name> <episode>[-<range end>] [<extended>] [<quality>][<hash>].<ext>
# The chapters tag is sometimes absent on older/April-Fools releases:
#   [One Pace] <Arc Name> <episode> [<quality>][<hash>].<ext>
_MEDIA_PATTERN = re.compile(
    r"\[One Pace\](?:\[(.*?)\])?\s(.*?)\s(\d{1,2}(?:-\d{1,2})?)"
    r"(?:\s(\w[\w\s\(\)-]+))?\s\[(?:.*?)\]\[(?:.*?)\]" + MEDIA_EXTENSIONS
)

# "Paced One Piece" format:
#   [One Pace] Paced One Piece - <Arc Name> Episode <NN>
_PACED_PATTERN = re.compile(
    r"\[One Pace\]\s+Paced One Piece\s*-\s*(.+?)\s+Episode\s+(\d+)", re.IGNORECASE
)

# Already-Plex format:
#   One Pace - S<NN>E<MM> - <Title>.<ext>
_PLEX_PATTERN = re.compile(
    rf"{re.escape(SHOW_NAME)}\s*-\s*S(\d+)E(\d+)\s*-\s*(.*?)" + MEDIA_EXTENSIONS + r"$",
    re.IGNORECASE,
)

# Arc-name normalization applied before season lookup.
_ARC_NORMALIZATION = {
    "whiskey": "Whisky",
    "arabasta": "Alabasta",
}


@dataclass
class ParsedEpisode:
    """Result of parsing a release title into its canonical identity."""

    arc: Optional[str]
    season: int
    number: int
    extended: str = ""


def _normalize_arc_name(arc_name: str) -> str:
    """Apply known historical Nyaa-vs-canonical arc name differences."""
    normalized = arc_name
    for needle, replacement in _ARC_NORMALIZATION.items():
        # Case-insensitive substring replace, preserving surrounding text.
        pattern = re.compile(re.escape(needle), re.IGNORECASE)
        normalized = pattern.sub(replacement, normalized)
    return normalized


def _lookup_season(arc_name: str, seasons: Dict[str, int]) -> Optional[int]:
    """Case-insensitive lookup of an arc name in the seasons dict."""
    normalized = _normalize_arc_name(arc_name)
    target = normalized.lower()
    for key, value in seasons.items():
        if key.lower() == target:
            return value
    return None


def _reverse_lookup_arc(season: int, seasons: Dict[str, int]) -> Optional[str]:
    """Best-effort reverse lookup: season number -> arc name.

    Not guaranteed unique (it isn't, in general) but the reference data only
    has one arc per season number, so in practice this resolves cleanly.
    Returns None if no arc maps to this season.
    """
    for key, value in seasons.items():
        if value == season:
            return key
    return None


def parse_release_title(title: str, seasons: Dict[str, int]) -> Optional[ParsedEpisode]:
    """Parse a release title (Nyaa or local filename) into a
    :class:`ParsedEpisode`, or ``None`` if it doesn't match any known format
    or its arc can't be resolved to a season.
    """
    # 1. "Paced One Piece" format (checked first: its "Episode NN" suffix can
    #    otherwise be mistaken for the original format's arc-name+episode).
    match = _PACED_PATTERN.search(title)
    if match:
        arc_name = match.group(1).strip()
        episode_number = int(match.group(2))
        season = _lookup_season(arc_name, seasons)
        if season is not None:
            return ParsedEpisode(
                arc=_normalize_arc_name(arc_name),
                season=season,
                number=episode_number,
                extended="",
            )

    # 2. Original One Pace format.
    match = _MEDIA_PATTERN.search(title)
    if match:
        arc_name = match.group(2).strip()
        episode_number = int(match.group(3).split("-")[0])
        extended = (match.group(4) or "").strip()
        season = _lookup_season(arc_name, seasons)
        if season is not None:
            return ParsedEpisode(
                arc=_normalize_arc_name(arc_name),
                season=season,
                number=episode_number,
                extended=extended,
            )

    # 3. Already-Plex format: season/episode are explicit, arc is optional.
    match = _PLEX_PATTERN.search(title)
    if match:
        season = int(match.group(1))
        episode_number = int(match.group(2))
        remainder = match.group(3).strip()
        extended = ""
        if remainder.endswith(")"):
            # Find the matching opening paren for the trailing ")" to peel
            # off an (Extended)/(Alternate ...) suffix, tolerating nested
            # parens (mirrors reference rename.py's logic).
            depth = 0
            for i in range(len(remainder) - 1, -1, -1):
                if remainder[i] == ")":
                    depth += 1
                elif remainder[i] == "(":
                    depth -= 1
                    if depth == 0:
                        extended = remainder[i + 1 : -1]
                        remainder = remainder[:i].strip()
                        break
        arc = _reverse_lookup_arc(season, seasons)
        return ParsedEpisode(arc=arc, season=season, number=episode_number, extended=extended)

    return None
