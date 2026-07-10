"""Unit tests for onepace_parser.parse_release_title."""
import os
import sys

import pytest

# Add parent directory to path to import onepace_parser
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from onepace_parser import ParsedEpisode, parse_release_title


@pytest.fixture
def seasons():
    """A small representative slice of seasons.json (arc -> season number)."""
    return {
        "Orange Town": 2,
        "Little Garden": 12,
        "Alabasta": 14,
        "Skypiea": 16,
        "Whisky Peak": 10,
        "Thriller Bark": 21,
        "Wano": 35,
    }


class TestOriginalOnePaceFormat:
    """Original `[One Pace][chapters] Arc NN [quality][hash].ext` format."""

    def test_simple_single_chapter_bracket(self, seasons):
        title = "[One Pace][301] Skypiea 24 [1080p][3F695862].mkv"
        result = parse_release_title(title, seasons)
        assert result == ParsedEpisode(arc="Skypiea", season=16, number=24, extended="")

    def test_grouped_chapter_range(self, seasons):
        title = "[One Pace][12-19] Orange Town 02 [1080p][D7327225].mkv"
        result = parse_release_title(title, seasons)
        assert result == ParsedEpisode(arc="Orange Town", season=2, number=2, extended="")

    def test_multi_word_arc_name(self, seasons):
        title = "[One Pace][117-119] Little Garden 02 [1080p][64714640].mkv"
        result = parse_release_title(title, seasons)
        assert result == ParsedEpisode(arc="Little Garden", season=12, number=2, extended="")

    def test_comma_separated_chapter_list(self, seasons):
        title = "[One Pace][159, 161-162] Arabasta 03 [1080p][73003149].mp4"
        result = parse_release_title(title, seasons)
        assert result == ParsedEpisode(arc="Alabasta", season=14, number=3, extended="")

    def test_extended_suffix(self, seasons):
        title = "[One Pace][900-905] Wano 02 Extended [1080p][DEADBEEF].mkv"
        result = parse_release_title(title, seasons)
        assert result is not None
        assert result.arc == "Wano"
        assert result.season == 35
        assert result.number == 2
        assert result.extended == "Extended"

    def test_whiskey_normalized_to_whisky(self, seasons):
        title = "[One Pace][106-109] Whiskey Peak 01 [480p][26D6F22A].mkv"
        result = parse_release_title(title, seasons)
        assert result == ParsedEpisode(arc="Whisky Peak", season=10, number=1, extended="")

    def test_arabasta_normalized_to_alabasta(self, seasons):
        title = "[One Pace][155-157] Arabasta 01 [1080p][BB1D093C].mp4"
        result = parse_release_title(title, seasons)
        assert result == ParsedEpisode(arc="Alabasta", season=14, number=1, extended="")

    def test_unknown_arc_returns_none(self, seasons):
        title = "[One Pace][1-1] Nonexistent Arc 01 [1080p][00000000].mkv"
        assert parse_release_title(title, seasons) is None

    def test_missing_chapter_bracket(self, seasons):
        """Older/April-Fools releases sometimes omit the [chapters] tag."""
        title = "[One Pace] Skypiea 24 [1080p][3F695862].mkv"
        result = parse_release_title(title, seasons)
        assert result == ParsedEpisode(arc="Skypiea", season=16, number=24, extended="")


class TestFormatFallthrough:
    """A pattern matching but failing arc lookup must not block later formats."""

    def test_paced_format_not_shadowed_by_original_format(self, seasons):
        # Without arc-name grouping via seasons.json, this could otherwise be
        # mistaken by the original-format regex for arc="Paced One Piece -
        # Thriller Bark", episode="Episode" -- which has no season and must
        # not swallow the match before the Paced-format pattern gets a turn.
        title = "[One Pace] Paced One Piece - Thriller Bark Episode 14 [720p][7CAE5640].mkv"
        result = parse_release_title(title, seasons)
        assert result == ParsedEpisode(arc="Thriller Bark", season=21, number=14, extended="")


class TestPacedOnePieceFormat:
    """`[One Pace] Paced One Piece - Arc Episode NN` format."""

    def test_paced_format(self, seasons):
        title = "[One Pace] Paced One Piece - Thriller Bark Episode 01 [720p][30D0916C].mkv"
        result = parse_release_title(title, seasons)
        assert result == ParsedEpisode(arc="Thriller Bark", season=21, number=1, extended="")

    def test_paced_format_unknown_arc_returns_none(self, seasons):
        title = "[One Pace] Paced One Piece - Nowhere Land Episode 03 [720p][11111111].mkv"
        assert parse_release_title(title, seasons) is None


class TestAlreadyPlexFormat:
    """`One Pace - S##E## - Title.ext` format."""

    def test_plex_format_resolves_arc_via_reverse_lookup(self, seasons):
        title = "One Pace - S16E24 - Some Title.mkv"
        result = parse_release_title(title, seasons)
        assert result is not None
        assert result.season == 16
        assert result.number == 24
        assert result.extended == ""
        assert result.arc == "Skypiea"

    def test_plex_format_extended_suffix_extracted(self, seasons):
        title = "One Pace - S35E02 - Seppuku (Extended).mkv"
        result = parse_release_title(title, seasons)
        assert result is not None
        assert result.season == 35
        assert result.number == 2
        assert result.extended == "Extended"

    def test_plex_format_nested_parens_extended_suffix(self, seasons):
        title = "One Pace - S16E25 - Finale (Alternate (G-8)).mkv"
        result = parse_release_title(title, seasons)
        assert result is not None
        assert result.season == 16
        assert result.number == 25
        assert result.extended == "Alternate (G-8)"

    def test_plex_format_unknown_season_arc_is_none(self, seasons):
        title = "One Pace - S99E01 - Mystery Season.mkv"
        result = parse_release_title(title, seasons)
        assert result is not None
        assert result.season == 99
        assert result.number == 1
        assert result.arc is None


class TestNoMatch:
    def test_unrelated_title_returns_none(self, seasons):
        assert parse_release_title("Some Random Show S01E01.mkv", seasons) is None

    def test_empty_string_returns_none(self, seasons):
        assert parse_release_title("", seasons) is None
