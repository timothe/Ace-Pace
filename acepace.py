import time
import csv
import json
import shutil
from datetime import datetime
import sqlite3
import re
import argparse
import zlib
import os
import signal
import sys
from xml.sax.saxutils import escape as _xml_escape
from bs4 import BeautifulSoup  # type: ignore
import requests  # type: ignore

try:  # pragma: no cover - trivial import guard
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore

try:  # pragma: no cover - trivial import guard
    from tqdm import tqdm  # type: ignore
except ImportError:  # pragma: no cover
    tqdm = None  # type: ignore

from clients import get_client
import onepace_parser
from reference_index import get_reference_index, DEFAULT_BASE_DIR as REFERENCE_BASE_DIR, TVSHOW_NFO_FILENAME


# Check if running in Docker (non-interactive mode)
IS_DOCKER = "RUN_DOCKER" in os.environ

# Check if debug mode is enabled (via DEBUG environment variable)
# Defaults to False if not set or empty
DEBUG_MODE = os.getenv("DEBUG", "").lower() in ("true", "1", "yes", "on")

# Quiet mode (via --quiet) suppresses non-essential informational prints.
QUIET_MODE = False

# Global flag for graceful shutdown
_shutdown_requested = False

# Shutdown message constant
_SHUTDOWN_MESSAGE = "Shutdown requested, stopping fetch operation..."


def _truthy_env(value):
    """Interpret a string env-var-style value as a boolean."""
    return str(value or "").strip().lower() in ("true", "1", "yes", "on")


def _refresh_debug_mode_from_env():
    """Recompute DEBUG_MODE from the DEBUG env var.
    Needed because acepace.toml (Part H4) may inject DEBUG into os.environ
    *after* this module was first imported (when DEBUG_MODE was computed)."""
    global DEBUG_MODE
    DEBUG_MODE = _truthy_env(os.getenv("DEBUG", ""))


def set_debug_mode(value):
    """Explicitly enable/disable debug mode (used by --verbose)."""
    global DEBUG_MODE
    DEBUG_MODE = bool(value)


def set_quiet_mode(value):
    """Explicitly enable/disable quiet mode (used by --quiet)."""
    global QUIET_MODE
    QUIET_MODE = bool(value)


def debug_print(*args, **kwargs):
    """Print debug messages only if DEBUG mode is enabled.
    Works exactly like print() but only outputs when DEBUG environment variable is set."""
    if DEBUG_MODE:
        print(*args, **kwargs)


def info_print(*args, **kwargs):
    """Print informational (non-essential) messages, suppressed by --quiet."""
    if not QUIET_MODE:
        print(*args, **kwargs)


def _signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global _shutdown_requested
    _shutdown_requested = True
    print("\nShutdown signal received, finishing current operation...")

# Define regex to extract CRC32 from filename text (commonly in [xxxxx])
CRC32_REGEX = re.compile(r"\[([A-Fa-f0-9]{8})\]")

# Quality regex patterns - matches [1080p], etc. (case insensitive)
QUALITY_REGEX = re.compile(r"\[(\d+p)\]", re.IGNORECASE)

# Video file extensions we care about
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi"}

# Constants for repeated string literals
HTML_PARSER = "html.parser"
NYAA_BASE_URL = "https://nyaa.si"
ONE_PACE_MARKER = "[One Pace]"

# HTTP and network constants
HTTP_OK = 200
REQUEST_DELAY_SECONDS = 0.2
CRC32_CHUNK_SIZE = 8192
MAGNET_LINK_PREFIX = "magnet:"

# Config and media directory defaults (override via env: ACEPACE_CONFIG_DIR_*, ACEPACE_MEDIA_DIR_*)
CONFIG_DIR_DOCKER_DEFAULT = "/config"
CONFIG_DIR_LOCAL_DEFAULT = "."
MEDIA_DIR_DOCKER_DEFAULT = "/media"
MEDIA_DIR_LOCAL_DEFAULT = ""
DB_NAME = "crc32_files.db"
EPISODES_DB_NAME = "episodes_index.db"
MISSING_CSV_FILENAME = "Ace-Pace_Missing.csv"
DB_CSV_FILENAME = "Ace-Pace_DB.csv"
CSV_COLUMN_MAGNET_LINK = "Magnet Link"
RENAME_LOG_FILENAME = "Ace-Pace_rename_log.json"
CONFIG_TOML_FILENAME = "acepace.toml"

# acepace.toml keys map 1:1 to these env var names (Part H4).
TOML_ENV_KEYS = (
    "NYAA_URL",
    "VERSION",
    "RENAME",
    "DOWNLOAD",
    "DRY_RUN",
    "RENAME_FORCE",
    "TORRENT_CLIENT",
    "TORRENT_HOST",
    "TORRENT_PORT",
    "TORRENT_USER",
    "TORRENT_PASSWORD",
    "EPISODES_UPDATE",
    "REFERENCE_UPDATE",
    "DEBUG",
)


def load_toml_config():
    """Load acepace.toml (if present) and inject any keys not already set as
    environment variables, so downstream os.getenv(...) call sites (and
    argparse defaults, if this runs before _parse_arguments) pick them up
    automatically. Precedence: CLI flag > env var > acepace.toml > built-in default.
    Never overrides an already-set environment variable.
    """
    try:
        config_path = get_config_path(CONFIG_TOML_FILENAME)
    except OSError as e:
        # Config dir couldn't be created/accessed (e.g. read-only /config in
        # a container without the volume mounted); skip toml config silently
        # rather than crash startup over an optional feature.
        debug_print(f"DEBUG: could not resolve config dir for acepace.toml: {e}")
        return {}
    if not os.path.isfile(config_path):
        return {}

    if tomllib is None:  # pragma: no cover - Python < 3.11 fallback
        print(f"acepace.toml found at {config_path} but 'tomllib' is unavailable (needs Python 3.11+); ignoring.")
        return {}

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        print(f"WARNING: failed to parse {config_path}: {e}; ignoring config file.")
        return {}

    applied = {}
    for key in TOML_ENV_KEYS:
        if key not in data:
            continue
        if key in os.environ:
            continue  # env var already set takes precedence over the config file
        value = data[key]
        os.environ[key] = str(value)
        applied[key] = value

    if applied:
        info_print(f"Loaded {len(applied)} setting(s) from {config_path}.")
    return applied


def _get_release_date():
    """Release date from modification time of this file (no repo commits, no extra file)."""
    try:
        mtime = os.path.getmtime(os.path.abspath(__file__))
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except (OSError, ValueError):
        return ""


def get_config_dir():
    """Get the config directory path based on Docker mode.
    Returns the config directory path, creating it if necessary.
    Override via ACEPACE_CONFIG_DIR_DOCKER (Docker) or ACEPACE_CONFIG_DIR_LOCAL (local).
    """
    if IS_DOCKER:
        config_dir = os.getenv("ACEPACE_CONFIG_DIR_DOCKER", CONFIG_DIR_DOCKER_DEFAULT)
    else:
        config_dir = os.getenv("ACEPACE_CONFIG_DIR_LOCAL", CONFIG_DIR_LOCAL_DEFAULT)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    return config_dir


def _get_default_media_dir():
    """Default media/library folder for the current mode (Docker vs local).
    Override via ACEPACE_MEDIA_DIR_DOCKER (Docker) or ACEPACE_MEDIA_DIR_LOCAL (local).
    """
    if IS_DOCKER:
        return os.getenv("ACEPACE_MEDIA_DIR_DOCKER", MEDIA_DIR_DOCKER_DEFAULT)
    return os.getenv("ACEPACE_MEDIA_DIR_LOCAL", MEDIA_DIR_LOCAL_DEFAULT)


def get_config_path(filename):
    """Get the full path to a config file.
    Args:
        filename: The name of the config file
    Returns:
        Full path to the config file in the appropriate config directory
    """
    config_dir = get_config_dir()
    return os.path.join(config_dir, filename)


def normalize_file_path(file_path):
    """Normalize a file path for consistent storage and lookup.
    Resolves symlinks and converts to absolute path to ensure the same file
    always maps to the same path string, regardless of OS or environment.
    Args:
        file_path: The file path to normalize
    Returns:
        Normalized absolute path
    """
    try:
        # Use realpath to resolve symlinks and get canonical path
        return os.path.realpath(os.path.abspath(file_path))
    except (OSError, ValueError):
        # Fallback to abspath if realpath fails (e.g., file doesn't exist yet)
        return os.path.normpath(os.path.abspath(file_path))


def init_db(suppress_messages=False):
    """Initialize the database.
    Args:
        suppress_messages: If True, suppress informational messages (useful for automated runs)
    """
    db_path = get_config_path(DB_NAME)
    exists = os.path.exists(db_path)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS crc32_cache (
            file_path TEXT PRIMARY KEY,
            crc32 TEXT UNIQUE
        )
    """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """
    )
    conn.commit()
    if exists and not suppress_messages:
        print("Database already exists. You can export it using the --db option.")
    return conn


# --- New: Episodes metadata DB ---
def init_episodes_db():
    """Initialize the episodes index database.
    Creates the episodes_index and metadata tables if they don't exist.
    Returns: Database connection object."""
    episodes_db_path = get_config_path(EPISODES_DB_NAME)
    conn = sqlite3.connect(episodes_db_path)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS episodes_index (
            crc32 TEXT PRIMARY KEY,
            title TEXT,
            page_link TEXT,
            magnet_link TEXT,
            pub_date TEXT
        )
        """
    )
    # Add magnet_link column if it doesn't exist (for existing databases)
    try:
        c.execute("ALTER TABLE episodes_index ADD COLUMN magnet_link TEXT")
    except sqlite3.OperationalError:
        # Column already exists, ignore
        pass
    # Add pub_date column if it doesn't exist (for existing databases)
    try:
        c.execute("ALTER TABLE episodes_index ADD COLUMN pub_date TEXT")
    except sqlite3.OperationalError:
        # Column already exists, ignore
        pass
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    conn.commit()
    return conn


def get_episodes_metadata(conn, key):
    """Get metadata value from episodes database.
    Args:
        conn: Database connection
        key: Metadata key
    Returns: Metadata value or None if not found."""
    c = conn.cursor()
    c.execute("SELECT value FROM metadata WHERE key = ?", (key,))
    row = c.fetchone()
    return row[0] if row else None


def set_episodes_metadata(conn, key, value):
    """Set metadata value in episodes database.
    Args:
        conn: Database connection
        key: Metadata key
        value: Metadata value"""
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", (key, value)
    )
    conn.commit()


# --- Part E: pub_date side channel -----------------------------------------
# fetch_episodes_metadata()'s return shape (list of 4-tuples) is relied upon
# by existing tests/callers, so the per-CRC32 Nyaa publish date discovered
# while scraping is threaded through this module-level side channel instead
# of being added as a 5th tuple element. Reset at the start of each fetch.
_last_fetch_pub_dates = {}


def get_last_fetched_pub_dates():
    """Return a copy of the crc32 -> pub_date map collected during the most
    recent fetch_episodes_metadata() call."""
    return dict(_last_fetch_pub_dates)


def _extract_pub_date_from_row(row):
    """Extract Nyaa's publish timestamp from a torrent-list table row.
    Nyaa renders it as: <td class="text-center" data-timestamp="171...">...
    Returns the raw timestamp string, or None if not present/parseable."""
    try:
        cells = row.find_all("td", class_="text-center")
    except AttributeError:
        return None
    for cell in cells:
        timestamp = cell.get("data-timestamp") if hasattr(cell, "get") else None
        if timestamp:
            return str(timestamp)
    return None


# --- New: Fetch and update episodes_index table ---
def _is_valid_quality(fname_text):
    """Check if filename has valid quality (1080p only).
    Returns True if quality is 1080p, False otherwise."""
    quality_matches = QUALITY_REGEX.findall(fname_text)
    if not quality_matches:
        return False  # No quality marker found, exclude
    # Check if quality is exactly 1080p (not higher, not lower)
    for quality in quality_matches:
        quality_num = int(quality.lower().replace('p', ''))
        if quality_num == 1080:
            return True
    return False  # Quality not 1080p


def _process_fname_entry(fname_text, seen_crc32, episodes, page_link, magnet_link="", pub_date=None):
    """Helper to extract CRC32 from fname_text and store if valid and unique.
    Only accepts episodes with 1080p quality."""
    m = CRC32_REGEX.findall(fname_text)
    found = False
    if m and ONE_PACE_MARKER in fname_text and _is_valid_quality(fname_text):
        crc32 = m[-1].upper()
        if crc32 not in seen_crc32:
            # print(f"New CRC32 detected: {crc32} -> Title: {fname_text}")
            episodes.append((crc32, fname_text, page_link, magnet_link))
            seen_crc32.add(crc32)
            if pub_date:
                _last_fetch_pub_dates[crc32] = pub_date
            found = True
    return found


def _get_total_pages(soup):
    """Extract total number of pages from pagination controls."""
    total_pages = 1
    pagination = soup.find("ul", class_="pagination")
    if pagination:
        page_links = pagination.find_all("a", href=True)
        page_numbers = []
        for a in page_links:
            text = a.text.strip()
            if text.isdigit():
                try:
                    page_numbers.append(int(text))
                except (ValueError, TypeError):
                    pass
        if page_numbers:
            total_pages = max(page_numbers)
    return total_pages


def _extract_title_link_from_row(row):
    """Extract title link from a table row."""
    links = row.find_all("a", href=True)
    for a in links:
        href = a.get("href", "")
        if href.startswith("/view/") and a.has_attr("title"):
            return a
    return None


def _extract_filenames_from_folder_structure(filelist_div):
    """Extract filenames from folder structure in file list."""
    all_uls = filelist_div.find_all("ul")
    filenames = []
    for ul in all_uls:
        for file_li in ul.find_all("li"):
            if not file_li.find("ul"):
                direct_texts = [
                    t for t in file_li.contents if isinstance(t, str)
                ]
                fname_text = "".join(direct_texts).strip()
                if fname_text:
                    filenames.append(fname_text)
    return filenames


def _extract_filenames_from_torrent_page(torrent_soup):
    """Extract filenames from a torrent page's file list."""
    filelist_div = torrent_soup.find("div", class_="torrent-file-list")
    if not filelist_div:
        return []
    
    has_folder = bool(filelist_div.find("a", class_="folder"))
    
    if has_folder:
        return _extract_filenames_from_folder_structure(filelist_div)
    else:
        li = filelist_div.find("li")
        if li:
            direct_texts = [t for t in li.contents if isinstance(t, str)]
            fname_text = "".join(direct_texts).strip()
            if fname_text:
                return [fname_text]
    return []


def _process_torrent_page(page_link, seen_crc32, episodes, magnet_link="", pub_date=None):
    """Process a torrent page to extract CRC32 information from file list.
    For grouped episodes, all episodes in the group share the same magnet_link."""
    try:
        torrent_resp = requests.get(page_link)
        if torrent_resp.status_code != HTTP_OK:
            print(f"Failed to fetch torrent page {page_link}")
            return False
        t_soup = BeautifulSoup(torrent_resp.text, HTML_PARSER)
        filenames = _extract_filenames_from_torrent_page(t_soup)
        found = False
        for fname in filenames:
            if _process_fname_entry(str(fname), seen_crc32, episodes, page_link, magnet_link, pub_date):
                found = True
        return found
    except (requests.RequestException, AttributeError, TypeError):
        return False


def _process_episode_row(row, seen_crc32, episodes):
    """Process a single table row to extract episode information."""
    title_link, magnet_link = _extract_links_from_row(row)
    if not title_link:
        return False

    title = title_link.text.strip()
    page_link = NYAA_BASE_URL + title_link["href"]
    pub_date = _extract_pub_date_from_row(row)
    matches = CRC32_REGEX.findall(title)

    if matches:
        return _process_fname_entry(title, seen_crc32, episodes, page_link, magnet_link or "", pub_date)
    else:
        # CRC32 not in title, need to visit torrent page
        # The magnet_link from the row applies to all episodes in the group
        return _process_torrent_page(page_link, seen_crc32, episodes, magnet_link or "", pub_date)


def _fetch_episodes_page(base_url, page, soup=None):
    """Fetch a single page of episodes.
    Returns tuple: (page_soup, success) where success indicates if page was fetched."""
    if page == 1 and soup is not None:
        return soup, True
    
    resp = requests.get(f"{base_url}&p={page}")
    if resp.status_code != HTTP_OK:
        print(f"Failed to fetch page {page}, status code: {resp.status_code}")
        return None, False
    return BeautifulSoup(resp.text, HTML_PARSER), True


def _process_episodes_page_rows(page_soup, seen_crc32, episodes):
    """Process all rows from an episodes page."""
    table = page_soup.find("table", class_="torrent-list")
    if not table:
        return
    rows = table.find_all("tr")  # type: ignore
    for row in rows:
        if _shutdown_requested:
            break
        _process_episode_row(row, seen_crc32, episodes)


def fetch_episodes_metadata(base_url=None):
    """
    Fetch all One Pace episodes from Nyaa, collecting CRC32, title, page link, and magnet link.
    If CRC32 not in title, fetch the torrent page and try to extract CRC32s from file list.
    For grouped episodes (multiple episodes in one torrent), all episodes share the same magnet link.
    Args:
        base_url: Base URL for Nyaa search. If None, uses default without quality filter.
                  Note: Quality filtering (1080p only) is always applied regardless of URL.
    Returns: List of (crc32, title, page_link, magnet_link)
    """
    if base_url is None:
        base_url = f"{NYAA_BASE_URL}/?f=0&c=0_0&q=one+pace"

    episodes = []
    seen_crc32 = set()
    _last_fetch_pub_dates.clear()
    print(f"Browsing {base_url}...")

    # Get total number of pages by parsing first page's pagination controls
    soup, success = _fetch_episodes_page(base_url, 1)
    if not success:
        debug_print("DEBUG: Failed to fetch first page for episodes metadata")
        return episodes
    total_pages = _get_total_pages(soup)
    debug_print(f"DEBUG: Found {total_pages} total pages to process for episodes metadata")

    # Loop from page 1 to total_pages
    page = 1
    while page <= total_pages:
        if _shutdown_requested:
            print(_SHUTDOWN_MESSAGE)
            break
            
        print(f"Fetching page {page}/{total_pages}...")
        page_soup, success = _fetch_episodes_page(base_url, page, soup if page == 1 else None)
        if not success:
            break
        
        _process_episodes_page_rows(page_soup, seen_crc32, episodes)
        
        if _shutdown_requested:
            break
        page += 1
        time.sleep(REQUEST_DELAY_SECONDS)
    
    print(f"Fetched {len(episodes)} unique episodes with CRC32s.")
    return episodes


def _should_skip_episodes_update(force_update, last_update_str):
    """Check if episodes update should be skipped due to recent update.
    Args:
        force_update: If True, never skip
        last_update_str: String timestamp of last update, or None
    Returns: True if should skip, False if should proceed"""
    if force_update:
        return False
    
    if not last_update_str:
        return False
    
    try:
        last_update = datetime.strptime(last_update_str, "%Y-%m-%d %H:%M:%S")
        time_diff = datetime.now() - last_update
        # Skip update if updated within last 10 minutes to avoid unnecessary double updates
        if time_diff.total_seconds() < 600:  # 10 minutes = 600 seconds
            print(f"Episodes were recently updated ({last_update_str}), skipping update to avoid duplicate fetch.")
            print("Set EPISODES_UPDATE=true or use --episodes_update to force update.")
            return True
    except (ValueError, TypeError):
        # If parsing fails, proceed with update
        pass
    
    return False


def update_episodes_index_db(base_url=None, force_update=False):
    """Update episodes index database from Nyaa.
    Args:
        base_url: Base URL for Nyaa search. If None, uses default.
        force_update: If True, force update even if recently updated. If False, skip if updated within last 10 minutes.
    """
    debug_print(f"DEBUG: Starting update_episodes_index_db with URL: {base_url}, force_update: {force_update}")
    
    # Check if episodes were recently updated (within last 10 minutes)
    conn = init_episodes_db()
    if not force_update:
        last_update_str = get_episodes_metadata(conn, "episodes_db_last_update")
        
        if _should_skip_episodes_update(force_update, last_update_str):
            conn.close()
            return
    episodes = fetch_episodes_metadata(base_url)
    debug_print(f"DEBUG: Fetched {len(episodes)} episodes from Nyaa")
    c = conn.cursor()
    
    # Prepare data for batch insert (allowing for shutdown during processing)
    episode_rows = []
    pub_dates_by_crc32 = get_last_fetched_pub_dates()
    for episode_data in episodes:
        # Check for shutdown request during processing
        if _shutdown_requested:
            print("Shutdown requested, committing partial update...")
            break
        # Handle both old format (3 items) and new format (4 items) for backward compatibility
        if len(episode_data) == 3:
            crc32, title, page_link = episode_data
            magnet_link = ""
        else:
            crc32, title, page_link, magnet_link = episode_data
        pub_date = pub_dates_by_crc32.get(crc32)
        episode_rows.append((crc32, title, page_link, magnet_link or "", pub_date))

    # Batch insert for better performance
    if episode_rows:
        c.executemany(
            "INSERT OR REPLACE INTO episodes_index (crc32, title, page_link, magnet_link, pub_date) VALUES (?, ?, ?, ?, ?)",
            episode_rows
        )
    conn.commit()
    count = len(episode_rows)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_episodes_metadata(conn, "episodes_db_last_update", now_str)
    print(f"Episodes index updated with {count} entries.")
    print(f"Last update: {now_str}")
    debug_print(f"DEBUG: Updated {count} entries in episodes_index database")
    conn.close()


def load_crc32_to_title_from_index():
    """Load CRC32 to title mapping from episodes index database.
    Returns: Dictionary mapping CRC32 to episode title."""
    conn = init_episodes_db()
    c = conn.cursor()
    c.execute("SELECT crc32, title FROM episodes_index")
    d = dict(c.fetchall())
    conn.close()
    return d


def load_1080p_episodes_from_index():
    """Load only 1080p episodes from episodes_index database.
    Returns: Tuple of (crc32_to_link, crc32_to_text, crc32_to_magnet) dictionaries with only 1080p episodes."""
    conn = init_episodes_db()
    c = conn.cursor()
    # Handle both old schema (without magnet_link) and new schema (with magnet_link)
    try:
        c.execute("SELECT crc32, title, page_link, magnet_link FROM episodes_index")
        has_magnet_column = True
    except sqlite3.OperationalError:
        # Old schema, magnet_link column doesn't exist yet
        c.execute("SELECT crc32, title, page_link FROM episodes_index")
        has_magnet_column = False
    crc32_to_link = {}
    crc32_to_text = {}
    crc32_to_magnet = {}
    for row in c.fetchall():
        if has_magnet_column:
            crc32, title, page_link, magnet_link = row
        else:
            crc32, title, page_link = row
            magnet_link = ""
        # Only include 1080p episodes (same filter as fetch_crc32_links)
        if _is_valid_quality(title):
            crc32_to_link[crc32] = page_link
            crc32_to_text[crc32] = title
            crc32_to_magnet[crc32] = magnet_link or ""
    conn.close()
    return crc32_to_link, crc32_to_text, crc32_to_magnet


def load_1080p_episodes_with_pubdates_from_index():
    """Like load_1080p_episodes_from_index(), but also returns a crc32 ->
    pub_date map (Part E: newest-version detection). Separate function so the
    original 3-tuple return shape (relied upon by existing callers/tests) is
    left untouched.
    Returns: (crc32_to_link, crc32_to_text, crc32_to_magnet, crc32_to_pubdate)"""
    conn = init_episodes_db()
    c = conn.cursor()
    try:
        c.execute("SELECT crc32, title, page_link, magnet_link, pub_date FROM episodes_index")
        rows = c.fetchall()
        has_pub_date_column = True
    except sqlite3.OperationalError:
        c.execute("SELECT crc32, title, page_link, magnet_link FROM episodes_index")
        rows = c.fetchall()
        has_pub_date_column = False
    crc32_to_link = {}
    crc32_to_text = {}
    crc32_to_magnet = {}
    crc32_to_pubdate = {}
    for row in rows:
        if has_pub_date_column:
            crc32, title, page_link, magnet_link, pub_date = row
        else:
            crc32, title, page_link, magnet_link = row
            pub_date = None
        if _is_valid_quality(title):
            crc32_to_link[crc32] = page_link
            crc32_to_text[crc32] = title
            crc32_to_magnet[crc32] = magnet_link or ""
            crc32_to_pubdate[crc32] = pub_date
    conn.close()
    return crc32_to_link, crc32_to_text, crc32_to_magnet, crc32_to_pubdate


def _group_episodes_for_missing_detection(crc32_to_text, crc32_to_magnet, crc32_to_pubdate):
    """Group Nyaa episodes by canonical (season, number, is_extended) identity
    (Part E). Unparseable titles fall back to their own singleton group keyed
    by crc32, so they're never silently dropped.

    Returns: dict of group_key -> list of crc32 (each group's members, in no
    particular order)."""
    _, seasons, _ = get_reference_index()
    groups = {}
    for crc32, title in crc32_to_text.items():
        parsed = onepace_parser.parse_release_title(title, seasons)
        if parsed is not None:
            key = ("canon", parsed.season, parsed.number, bool(parsed.extended))
        else:
            key = ("unparsed", crc32)
        groups.setdefault(key, []).append(crc32)
    return groups


def _pub_date_sort_key(pub_date):
    """Sort key for pub_date strings (Nyaa unix timestamps as TEXT); None/
    unparseable values sort lowest (oldest) so a real date always wins."""
    try:
        return int(pub_date)
    except (TypeError, ValueError):
        return -1


def _calculate_missing_episodes_grouped(crc32_to_text, crc32_to_magnet, crc32_to_pubdate, local_crc32s):
    """Version-aware missing-episode detection (Part E).

    A canonical episode is considered present locally if ANY version's CRC32
    within its (season, number, is_extended) group is present in
    ``local_crc32s``. Missing episodes are reported using the CRC32/magnet of
    the NEWEST version (highest pub_date) in the group, so downloads always
    fetch the newest release. Titles that don't parse fall back to a
    singleton group (behaves like the legacy ungrouped comparison).

    Returns: list of crc32 (the newest-version crc32 for each missing group).
    """
    groups = _group_episodes_for_missing_detection(crc32_to_text, crc32_to_magnet, crc32_to_pubdate)
    missing = []
    for _key, crc32_list in groups.items():
        present = any(crc32 in local_crc32s for crc32 in crc32_list)
        if present:
            continue
        newest_crc32 = max(crc32_list, key=lambda c: _pub_date_sort_key(crc32_to_pubdate.get(c)))
        missing.append(newest_crc32)
    return missing


def _validate_row_links(title_link, magnet_link):
    """Validate that row links are valid and properly formatted."""
    return (title_link and magnet_link and 
            isinstance(magnet_link, str) and 
            magnet_link.startswith(MAGNET_LINK_PREFIX) and
            hasattr(title_link, 'text'))


def _is_valid_one_pace_episode(filename_text):
    """Check if filename is a valid One Pace episode with 1080p quality."""
    if ONE_PACE_MARKER not in filename_text:
        return False
    return _is_valid_quality(filename_text)


def _extract_crc32_from_text(text):
    """Extract CRC32 from text if present."""
    matches = CRC32_REGEX.findall(text)
    if matches:
        return matches[-1].upper()
    return None


def _check_crc32_in_title(filename_text, crc32_set, magnet_link):
    """Check if CRC32 is in the title and matches the set."""
    crc32 = _extract_crc32_from_text(filename_text)
    if crc32 and crc32 in crc32_set:
        return crc32, magnet_link
    return None, None


def _fetch_crc32_from_torrent_page(link, crc32_set, magnet_link):
    """Fetch torrent page and extract CRC32 from file list."""
    try:
        torrent_resp = requests.get(link)
        if torrent_resp.status_code != HTTP_OK:
            return None, None
        
        t_soup = BeautifulSoup(torrent_resp.text, HTML_PARSER)
        filenames = _extract_filenames_from_torrent_page(t_soup)
        for fname in filenames:
            fname_str = str(fname)
            if ONE_PACE_MARKER in fname_str and _is_valid_quality(fname_str):
                crc32 = _extract_crc32_from_text(fname_str)
                if crc32 and crc32 in crc32_set:
                    return crc32, magnet_link
    except (requests.RequestException, AttributeError, TypeError):
        pass
    
    return None, None


def _extract_magnet_link_from_row(row, crc32_set):
    """Extract magnet link from a table row if it matches a CRC32 in the set.
    First checks title, then visits torrent page if CRC32 not in title.
    Args:
        row: BeautifulSoup table row element
        crc32_set: Set of CRC32 values to match against
    Returns: Tuple of (crc32, magnet_link) if found, (None, None) otherwise"""
    title_link, magnet_link = _extract_links_from_row(row)
    if not _validate_row_links(title_link, magnet_link):
        return None, None
    
    # Type guard: after validation, title_link is guaranteed to be non-None
    assert title_link is not None and magnet_link is not None
    
    filename_text = title_link.text
    if not _is_valid_one_pace_episode(filename_text):
        return None, None
    
    # Check if CRC32 is in title
    crc32, found_magnet = _check_crc32_in_title(filename_text, crc32_set, magnet_link)
    if crc32:
        return crc32, found_magnet
    
    # CRC32 not in title, try fetching torrent page to extract from file list
    link = NYAA_BASE_URL + title_link["href"]
    return _fetch_crc32_from_torrent_page(link, crc32_set, magnet_link)


def _process_magnet_links_page(page_soup, crc32_set, crc32_to_magnet):
    """Process a single page to extract magnet links matching CRC32s in the set.
    Args:
        page_soup: BeautifulSoup object for the page
        crc32_set: Set of CRC32 values to match against
        crc32_to_magnet: Dictionary to update with found magnet links
    Returns: Number of new magnet links found on this page"""
    found_count = 0
    table = page_soup.find("table", class_="torrent-list")
    if not table:
        return found_count
    
    rows = table.find_all("tr")
    for row in rows:
        if _shutdown_requested:
            break
        crc32, magnet_link = _extract_magnet_link_from_row(row, crc32_set)
        if crc32 and magnet_link:
            crc32_to_magnet[crc32] = magnet_link
            found_count += 1
    
    return found_count


def _get_page_soup_for_magnet_links(base_url, page, first_page_soup):
    """Get BeautifulSoup object for a specific page when fetching magnet links.
    Args:
        base_url: Nyaa search URL
        page: Page number (1-indexed)
        first_page_soup: BeautifulSoup object for page 1 (already fetched)
    Returns: Tuple of (soup, success)"""
    if page == 1:
        return first_page_soup, True
    return _fetch_crc32_page(base_url, page)


def fetch_magnet_links_for_episodes_from_search(base_url, crc32_to_link):
    """Fetch magnet links from Nyaa search results for episodes already in crc32_to_link.
    This is more efficient than fetching all episodes again.
    Args:
        base_url: Nyaa search URL
        crc32_to_link: Dictionary mapping CRC32 to page_link (episodes we need magnet links for)
    Returns: Dictionary mapping CRC32 to magnet_link"""
    crc32_to_magnet = {}
    crc32_set = set(crc32_to_link.keys())
    
    if not crc32_set:
        return crc32_to_magnet
    
    # Get total number of pages (fetch page 1 silently first to get total pages)
    resp = requests.get(f"{base_url}&p=1")
    if resp.status_code != HTTP_OK:
        return crc32_to_magnet
    soup = BeautifulSoup(resp.text, HTML_PARSER)
    total_pages = _get_total_pages(soup)
    print(f"Fetching magnet links from {total_pages} pages...")
    
    # Process pages to extract magnet links for episodes we need
    # Continue searching until we've found all requested episodes or searched all pages
    page = 1
    while page <= total_pages and len(crc32_to_magnet) < len(crc32_set):
        if _shutdown_requested:
            break
        
        if page == 1:
            page_soup = soup
            success = True
        else:
            page_soup, success = _get_page_soup_for_magnet_links(base_url, page, soup)
        
        if not success or page_soup is None:
            break
        
        _process_magnet_links_page(page_soup, crc32_set, crc32_to_magnet)
        
        page += 1
        if page <= total_pages:
            time.sleep(REQUEST_DELAY_SECONDS)
    
    return crc32_to_magnet




def get_metadata(conn, key):
    """Get metadata value from database.
    Args:
        conn: Database connection
        key: Metadata key
    Returns: Metadata value or None if not found."""
    c = conn.cursor()
    c.execute("SELECT value FROM metadata WHERE key = ?", (key,))
    row = c.fetchone()
    return row[0] if row else None


def set_metadata(conn, key, value):
    """Set metadata value in database.
    Args:
        conn: Database connection
        key: Metadata key
        value: Metadata value"""
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", (key, value)
    )
    conn.commit()


def _extract_links_from_row(row):
    """Extract title link and magnet link from a table row.
    Returns tuple: (title_link, magnet_link) or (None, "") if not found."""
    links = row.find_all("a", href=True)
    title_link = None
    magnet_link = ""
    for a in links:
        if a.has_attr("title"):
            title_link = a
        href = a.get("href", "")
        if href.startswith(MAGNET_LINK_PREFIX):
            magnet_link = href
    return title_link, magnet_link


def _process_title_with_crc32(filename_text, link, magnet_link, crc32_to_link, crc32_to_text, crc32_to_magnet):
    """Process a title that has CRC32 in it.
    Returns True if successfully processed, False otherwise."""
    matches = CRC32_REGEX.findall(filename_text)
    if matches:
        crc32 = matches[-1].upper()
        crc32_to_link[crc32] = link
        crc32_to_text[crc32] = filename_text
        crc32_to_magnet[crc32] = magnet_link
        return True
    return False


def _process_torrent_page_for_crc32(link, magnet_link, crc32_to_link, crc32_to_text, crc32_to_magnet):
    """Fetch torrent page and extract CRC32 from file list.
    Returns True if CRC32 found, False otherwise."""
    try:
        torrent_resp = requests.get(link)
        if torrent_resp.status_code == HTTP_OK:
            t_soup = BeautifulSoup(torrent_resp.text, HTML_PARSER)
            filenames = _extract_filenames_from_torrent_page(t_soup)
            for fname in filenames:
                fname_str = str(fname)
                if ONE_PACE_MARKER in fname_str and _is_valid_quality(fname_str):
                    fname_matches = CRC32_REGEX.findall(fname_str)
                    if fname_matches:
                        crc32 = fname_matches[-1].upper()
                        crc32_to_link[crc32] = link
                        crc32_to_text[crc32] = fname_str
                        crc32_to_magnet[crc32] = magnet_link
                        return True
    except (requests.RequestException, AttributeError, TypeError):
        pass
    return False


def _process_crc32_row(row, crc32_to_link, crc32_to_text, crc32_to_magnet):
    """Process a single table row to extract CRC32 information.
    Only accepts episodes with 1080p quality.
    If CRC32 not in title, fetches torrent page to extract from file list.
    Returns tuple: (success: bool, filename_text: str or None, should_warn: bool)
    where should_warn indicates if a warning should be shown (only when CRC32 is missing, not when quality is wrong)."""
    title_link, magnet_link = _extract_links_from_row(row)
    if not title_link:
        return False, None, False
    
    filename_text = title_link.text
    link = NYAA_BASE_URL + title_link["href"]
    
    # Check if it's a One Pace episode first
    if ONE_PACE_MARKER not in filename_text:
        return False, filename_text, False
    
    # Check quality first - if not 1080p, silently skip (don't warn)
    if not _is_valid_quality(filename_text):
        return False, filename_text, False
    
    # Quality is valid (1080p), now check for CRC32
    if _process_title_with_crc32(filename_text, link, magnet_link, crc32_to_link, crc32_to_text, crc32_to_magnet):
        return True, filename_text, False
    
    # CRC32 not in title, try fetching torrent page
    if _process_torrent_page_for_crc32(link, magnet_link, crc32_to_link, crc32_to_text, crc32_to_magnet):
        return True, filename_text, False
    
    # CRC32 not found in title or torrent page, but quality is valid - should warn
    return False, filename_text, True


def _fetch_crc32_page(base_url, page):
    """Fetch a single page for CRC32 links.
    Returns tuple: (soup, success) where success indicates if page was fetched."""
    print(f"Fetching page {page}...")
    resp = requests.get(f"{base_url}&p={page}")
    if resp.status_code != HTTP_OK:
        print(f"Failed to fetch page {page}, status code: {resp.status_code}")
        return None, False
    return BeautifulSoup(resp.text, HTML_PARSER), True


def _process_crc32_page_rows(soup, crc32_to_link, crc32_to_text, crc32_to_magnet):
    """Process all rows from a CRC32 links page.
    Returns the number of episodes found on this page."""
    table = soup.find("table", class_="torrent-list")
    if not table:
        return 0

    rows = table.find_all("tr")  # type: ignore
    if not rows:
        return 0

    found_count = 0
    for row in rows:
        if _shutdown_requested:
            print(_SHUTDOWN_MESSAGE)
            break
        success, filename_text, should_warn = _process_crc32_row(row, crc32_to_link, crc32_to_text, crc32_to_magnet)
        if success:
            found_count += 1
        elif should_warn and filename_text:
            debug_print(f"Warning: No CRC32 found in title '{filename_text}'")
    
    return found_count


def fetch_crc32_links(base_url):
    """Fetch CRC32 links from Nyaa.si search URL.
    Only accepts episodes with 1080p quality.
    Uses pagination to fetch all pages, similar to fetch_episodes_metadata.
    Args:
        base_url: Nyaa.si search URL
    Returns: Tuple of (crc32_to_link, crc32_to_text, crc32_to_magnet, last_checked_page)"""
    crc32_to_link = {}
    crc32_to_text = {}
    crc32_to_magnet = {}
    
    debug_print(f"DEBUG: Starting fetch_crc32_links with URL: {base_url}")
    
    # Get total number of pages by parsing first page's pagination controls
    soup, success = _fetch_crc32_page(base_url, 1)
    if not success:
        debug_print("DEBUG: Failed to fetch first page for CRC32 links")
        return crc32_to_link, crc32_to_text, crc32_to_magnet, 0
    
    total_pages = _get_total_pages(soup)
    debug_print(f"DEBUG: Found {total_pages} total pages to process for CRC32 links")
    last_checked_page = 0
    
    # Loop from page 1 to total_pages (similar to fetch_episodes_metadata)
    page = 1
    while page <= total_pages:
        if _shutdown_requested:
            print(_SHUTDOWN_MESSAGE)
            break
        
        # Use cached soup for page 1, fetch for others
        if page == 1:
            page_soup = soup
            success = True
        else:
            page_soup, success = _fetch_crc32_page(base_url, page)
        
        if not success:
            break
        
        episodes_found = _process_crc32_page_rows(page_soup, crc32_to_link, crc32_to_text, crc32_to_magnet)
        debug_print(f"DEBUG: Page {page}/{total_pages}: Found {episodes_found} valid episodes (total so far: {len(crc32_to_link)})")
        
        if _shutdown_requested:
            break
        
        last_checked_page = page
        page += 1
        if page <= total_pages:  # Don't sleep after last page
            time.sleep(REQUEST_DELAY_SECONDS)
    
    debug_print(f"DEBUG: Completed fetch_crc32_links: {len(crc32_to_link)} total episodes found across {last_checked_page} pages")

    return crc32_to_link, crc32_to_text, crc32_to_magnet, last_checked_page


def _extract_matching_titles_from_rows(rows, crc32):
    """Extract titles matching the given CRC32 from table rows."""
    matched_titles = []
    for row in rows:
        links = row.find_all("a", href=True)
        for a in links:
            href = a.get("href", "")
            if href.startswith("/view/") and a.has_attr("title"):
                filename_text = a.text
                matches = CRC32_REGEX.findall(filename_text)
                if matches and matches[-1].upper() == crc32:
                    matched_titles.append(filename_text)
    return matched_titles


def fetch_title_by_crc32(crc32):
    """Search on Nyaa for the given CRC32 and return the episode title.
    Args:
        crc32: CRC32 checksum to search for
    Returns: Episode title if exactly one match found, None otherwise."""
    # Search on Nyaa for the given CRC32
    search_url = f"{NYAA_BASE_URL}/?f=0&c=0_0&q={crc32}&o=asc"
    resp = requests.get(search_url)
    if resp.status_code != HTTP_OK:
        print(f"Failed to fetch search results for CRC32 {crc32}")
        return None
    soup = BeautifulSoup(resp.text, HTML_PARSER)
    table = soup.find("table", class_="torrent-list")
    if not table:
        return None
    rows = table.find_all("tr")  # type: ignore
    matched_titles = _extract_matching_titles_from_rows(rows, crc32)
    
    if len(matched_titles) == 1:
        print(f"Found {crc32} on Nyaa!")
        return matched_titles[0]
    elif len(matched_titles) == 0:
        debug_print(f"Warning: No title found for {crc32}")
        return None
    else:
        debug_print(f"Warning: Multiple titles found for CRC32 {crc32}: {matched_titles}")
        return None


def _calculate_file_crc32(file_path):
    """Calculate CRC32 for a single file.
    Returns the CRC32 as a string, or None if calculation was interrupted."""
    with open(file_path, "rb") as f:
        crc = 0
        while chunk := f.read(CRC32_CHUNK_SIZE):
            if _shutdown_requested:
                return None
            crc = zlib.crc32(chunk, crc)
        return f"{crc & 0xFFFFFFFF:08X}"


def _process_video_file(file_path, c, conn, local_crc32s):
    """Process a single video file: check cache or calculate CRC32.
    Returns True if file was processed successfully."""
    normalized_path = normalize_file_path(file_path)
    
    # Check if already in DB
    c.execute("SELECT crc32 FROM crc32_cache WHERE file_path = ?", (normalized_path,))
    row = c.fetchone()
    if row:
        local_crc32s.add(row[0])
        debug_print(f"DEBUG: Using cached CRC32 for {os.path.basename(file_path)}: {row[0]}")
        return True
    
    # Calculate CRC32
    parent_folder = os.path.basename(os.path.dirname(file_path))
    file_name = os.path.basename(file_path)
    print(f"Calculating CRC32 for {parent_folder}/{file_name}...")
    
    crc32 = _calculate_file_crc32(file_path)
    if crc32 is None:
        debug_print(f"DEBUG: CRC32 calculation interrupted for {file_path}")
        return False  # Calculation interrupted
    
    debug_print(f"DEBUG: Calculated CRC32 for {file_name}: {crc32}")
    local_crc32s.add(crc32)
    c.execute(
        "INSERT OR REPLACE INTO crc32_cache (file_path, crc32) VALUES (?, ?)",
        (normalized_path, crc32),
    )
    conn.commit()
    return True


def _process_single_file_for_crc32(file_path, c, conn, local_crc32s):
    """Process a single file for CRC32 calculation.
    Returns tuple: (success: bool, was_cached: bool)"""
    normalized_path = normalize_file_path(file_path)
    # Check if already in DB
    c.execute("SELECT crc32 FROM crc32_cache WHERE file_path = ?", (normalized_path,))
    row = c.fetchone()
    was_cached = bool(row)
    
    if _process_video_file(file_path, c, conn, local_crc32s):
        return True, was_cached
    return False, was_cached


def _process_files_in_directory(root, files, c, conn, local_crc32s, stats):
    """Process files in a directory, updating stats.
    Returns True if processing should continue, False if shutdown requested."""
    for file in files:
        if _shutdown_requested:
            return False
        
        ext = os.path.splitext(file)[1].lower()
        if ext in VIDEO_EXTENSIONS:
            file_path = os.path.join(root, file)
            success, was_cached = _process_single_file_for_crc32(file_path, c, conn, local_crc32s)
            if success:
                stats['processed'] += 1
                if was_cached:
                    stats['cached'] += 1
                else:
                    stats['calculated'] += 1
    return True


def _count_video_files_total(folder):
    """Quick pre-count of video files under folder, used to size the tqdm
    progress bar in calculate_local_crc32 (Part H2)."""
    total = 0
    for _root, _dirs, files in os.walk(folder):
        for file in files:
            if os.path.splitext(file)[1].lower() in VIDEO_EXTENSIONS:
                total += 1
    return total


def _tqdm_progress_enabled():
    """Progress bar is only shown when tqdm is installed, output is a real
    TTY, and we're not in --quiet mode (Part H2)."""
    return tqdm is not None and not QUIET_MODE and sys.stdout.isatty()


def _make_crc32_progress_bar(folder):
    """Build a tqdm progress bar for calculate_local_crc32(), or None if
    progress display is disabled/unavailable (Part H2)."""
    if not _tqdm_progress_enabled():
        return None
    total = _count_video_files_total(folder)
    return tqdm(total=total, desc="Calculating CRC32", unit="file")


def _walk_and_process_for_crc32(folder, c, conn, local_crc32s, stats, progress):
    """Walk folder, processing video files directory-by-directory, advancing
    the optional progress bar as files are processed. Returns nothing;
    mutates local_crc32s/stats in place."""
    for root, dirs, files in os.walk(folder):
        if _shutdown_requested:
            print("Shutdown requested, stopping file processing...")
            break

        before = stats['processed']
        keep_going = _process_files_in_directory(root, files, c, conn, local_crc32s, stats)
        if progress is not None:
            progress.update(stats['processed'] - before)
        if not keep_going:
            break


def calculate_local_crc32(folder, conn):
    """Calculate CRC32 checksums for all video files in the given folder.
    Uses cached values from database when available.
    Args:
        folder: Folder path to scan for video files
        conn: Database connection
    Returns: Set of CRC32 checksums found in the folder."""
    local_crc32s = set()
    c = conn.cursor()
    stats = {'processed': 0, 'cached': 0, 'calculated': 0}

    debug_print(f"DEBUG: Starting calculate_local_crc32 for folder: {folder}")

    progress = _make_crc32_progress_bar(folder)
    try:
        _walk_and_process_for_crc32(folder, c, conn, local_crc32s, stats, progress)
    finally:
        if progress is not None:
            progress.close()

    debug_print(f"DEBUG: Processed {stats['processed']} video files ({stats['cached']} from cache, {stats['calculated']} calculated)")
    debug_print(f"DEBUG: Found {len(local_crc32s)} unique CRC32s")

    return local_crc32s


def _is_extended_mode(version=None):
    """True if VERSION (CLI/env, default 'normal') resolves to 'extended'."""
    if version is None:
        version = os.getenv("VERSION", "normal")
    return str(version).strip().lower() == "extended"


def _rename_force_enabled():
    """RENAME_FORCE env var: gates the actual destructive move in Docker mode."""
    return _truthy_env(os.getenv("RENAME_FORCE", ""))


def _lookup_reference_episode(lookup, season, number, extended_mode):
    """Look up a canonical Episode for (season, number), honoring VERSION.
    Normal mode prefers the non-extended entry, falling back to the extended
    one if that's all that exists; extended mode does the opposite."""
    primary = lookup.get((season, number, extended_mode))
    if primary is not None:
        return primary
    return lookup.get((season, number, not extended_mode))


def _season_folder_name(season):
    """Season subfolder name: 'Specials' for season 0, else 'Season NN'."""
    if season == 0:
        return "Specials"
    return f"Season {season:02d}"


def _canonical_episode_filename(episode, ext):
    """Canonical Plex-friendly filename for a reference Episode."""
    suffix = f" ({episode.extended})" if episode.extended else ""
    return f"One Pace - S{episode.season:02d}E{episode.number:02d} - {episode.title}{suffix}{ext}"


def _build_rename_plan(entries, crc32_to_title, seasons, lookup, extended_mode=False):
    """Build a plan of files to rename/move based on CRC32 -> title -> canonical episode.
    Args:
        entries: iterable of (file_path, crc32) from crc32_cache.
        crc32_to_title: dict CRC32 -> stored Nyaa release title.
        seasons: {arc_name: season_number}, from get_reference_index().
        lookup: {(season, number, is_extended): Episode}, from get_reference_index().
        extended_mode: True to prefer extended entries (VERSION=extended).
    Returns: (rename_plan, unrecognized, already_correct)
        rename_plan: list of dicts {old_path, new_path, crc32, episode}.
        unrecognized: list of (file_path, crc32, reason) - not renamed, not an error.
        already_correct: list of file_path already at their canonical location.
    """
    rename_plan = []
    unrecognized = []
    already_correct = []
    for file_path, crc32 in entries:
        title = crc32_to_title.get(crc32)
        if not title:
            unrecognized.append((file_path, crc32, "no title found in episodes index"))
            continue

        parsed = onepace_parser.parse_release_title(title, seasons)
        if parsed is None:
            unrecognized.append((file_path, crc32, "unrecognized/obsolete release title"))
            continue

        episode = _lookup_reference_episode(lookup, parsed.season, parsed.number, extended_mode)
        if episode is None:
            unrecognized.append((
                file_path, crc32,
                f"episodes_without_nfo: no canonical episode found for "
                f"S{parsed.season:02d}E{parsed.number:02d}",
            ))
            continue

        ext = os.path.splitext(file_path)[1]
        new_filename = _canonical_episode_filename(episode, ext)
        dir_name = os.path.dirname(file_path)
        new_path = os.path.join(dir_name, _season_folder_name(episode.season), new_filename)

        if os.path.abspath(file_path) == os.path.abspath(new_path):
            already_correct.append(file_path)
            continue

        rename_plan.append({
            "old_path": file_path,
            "new_path": new_path,
            "crc32": crc32,
            "episode": episode,
        })
    return rename_plan, unrecognized, already_correct


def _get_rename_confirmation():
    """Get user confirmation for renaming files."""
    if IS_DOCKER:
        return "y"
    return input("Proceed with renaming? (y/n): ").strip().lower()


NFO_EPISODE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<episodedetails>
  <title>{title}</title>
  <showtitle>One Pace</showtitle>
  <season>{season}</season>
  <episode>{number}</episode>
</episodedetails>
"""


def _write_episode_nfo(video_path, episode):
    """Write a minimal synthesized companion .nfo next to a renamed episode file.
    Note: only path-derived metadata is vendored (see reference_index.py), so this
    is a minimal-but-valid <episodedetails> nfo, not a copy of the real upstream XML."""
    nfo_path = os.path.splitext(video_path)[0] + ".nfo"
    content = NFO_EPISODE_TEMPLATE.format(
        title=_xml_escape(episode.title),
        season=episode.season,
        number=episode.number,
    )
    try:
        with open(nfo_path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        print(f"WARNING: failed to write nfo for {video_path}: {e}")


def _copy_tvshow_nfo_once(library_root):
    """Copy the vendored tvshow.nfo to the library root, once, if not already present."""
    if not library_root:
        return
    src = os.path.join(str(REFERENCE_BASE_DIR), TVSHOW_NFO_FILENAME)
    dst = os.path.join(library_root, TVSHOW_NFO_FILENAME)
    if os.path.isfile(src) and not os.path.exists(dst):
        try:
            shutil.copyfile(src, dst)
        except OSError as e:
            print(f"WARNING: failed to copy tvshow.nfo to {library_root}: {e}")


def _write_rename_journal(journal_entries):
    """Persist the most recent rename run's journal (overwrites any previous run)."""
    path = get_config_path(RENAME_LOG_FILENAME)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(journal_entries, f, indent=2)
    except OSError as e:
        print(f"WARNING: failed to write rename journal to {path}: {e}")


def _load_rename_journal():
    """Load the rename journal, or an empty list if missing/unreadable."""
    path = get_config_path(RENAME_LOG_FILENAME)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"WARNING: failed to read rename journal at {path}: {e}")
        return []


def undo_last_rename(conn):
    """Reverse the most recently journaled --rename run: moves files back to
    their old_path and reverts crc32_cache.file_path entries. Clears the
    journal on completion. Returns (reverted_count, skipped_count)."""
    entries = _load_rename_journal()
    if not entries:
        print("No rename journal found; nothing to undo.")
        return 0, 0

    c = conn.cursor()
    reverted = 0
    skipped = 0
    for entry in entries:
        old_path = entry.get("old_path")
        new_path = entry.get("new_path")
        if not old_path or not new_path:
            skipped += 1
            continue
        if not os.path.exists(new_path):
            print(f"Skipping undo for {new_path}: file not found (already reverted or moved).")
            skipped += 1
            continue
        if os.path.exists(old_path):
            print(f"Skipping undo for {new_path}: target {old_path} already exists.")
            skipped += 1
            continue
        try:
            old_dir = os.path.dirname(old_path)
            if old_dir:
                os.makedirs(old_dir, exist_ok=True)
            os.rename(new_path, old_path)
            c.execute(
                "UPDATE crc32_cache SET file_path = ? WHERE file_path = ?",
                (normalize_file_path(old_path), normalize_file_path(new_path)),
            )
            conn.commit()
            reverted += 1
            print(f"Reverted {new_path} -> {old_path}")
        except (sqlite3.Error, OSError) as e:
            print(f"Failed to revert {new_path}: {e}")
            skipped += 1

    _write_rename_journal([])  # "undo last run" - clear journal after attempting undo
    print(f"Undo complete: {reverted} reverted, {skipped} skipped.")
    return reverted, skipped


def _execute_rename(rename_plan, conn, folder=None):
    """Execute the rename plan: move each file into its Season NN/ (or
    Specials/) subfolder under canonical name, write a companion .nfo, copy
    tvshow.nfo once, update crc32_cache paths, and journal the run for undo.
    Returns: (renamed_count, error_count)."""
    c = conn.cursor()
    journal = []
    renamed = 0
    errors = 0
    now_iso = datetime.now().isoformat()

    for item in rename_plan:
        old = item["old_path"]
        new = item["new_path"]
        episode = item["episode"]
        crc32 = item["crc32"]
        try:
            if os.path.exists(new):
                print(f"Cannot rename {old} to {new}: target file already exists.")
                errors += 1
                continue

            new_dir = os.path.dirname(new)
            if new_dir:
                os.makedirs(new_dir, exist_ok=True)

            os.rename(old, new)
            print(f"Renamed {old} to {new}")

            _write_episode_nfo(new, episode)

            normalized_old = normalize_file_path(old)
            normalized_new = normalize_file_path(new)
            c.execute(
                "UPDATE crc32_cache SET file_path = ? WHERE file_path = ?",
                (normalized_new, normalized_old),
            )
            conn.commit()

            journal.append({
                "old_path": normalized_old,
                "new_path": normalized_new,
                "crc32": crc32,
                "timestamp": now_iso,
            })
            renamed += 1
        except (sqlite3.Error, OSError) as e:
            print(f"Failed to rename {old} to {new}: {e}")
            errors += 1

    if folder:
        _copy_tvshow_nfo_once(folder)

    _write_rename_journal(journal)
    return renamed, errors


def _print_rename_summary(total, renamed, skipped_already_correct, unrecognized_count, errors):
    """Print the final rename-run summary table (Part H2)."""
    print("\n=== Rename Summary ===")
    print(f"Total: {total}")
    print(f"Renamed: {renamed}")
    print(f"Skipped (already correct): {skipped_already_correct}")
    print(f"Unrecognized/obsolete: {unrecognized_count}")
    print(f"Errors: {errors}")


def rename_local_files(conn, dry_run=False, extended_mode=False, folder=None):
    """Rename+move local files based on CRC32 -> Nyaa title -> canonical
    one-pace-for-plex episode. Unrecognized/obsolete local files are reported
    but never touched.
    Args:
        conn: Database connection.
        dry_run: If True, only print the rename plan; never renames or prompts.
        extended_mode: True to prefer extended episodes (VERSION=extended).
        folder: Library root, used to copy tvshow.nfo once on real execution.
    """
    c = conn.cursor()
    c.execute("SELECT file_path, crc32 FROM crc32_cache")
    entries = c.fetchall()
    if not entries:
        print("No entries found in local CRC32 database.")
        return

    crc32_to_title = load_crc32_to_title_from_index()
    lookup, seasons, _exceptions = get_reference_index()

    total = len(entries)
    rename_plan, unrecognized, already_correct = _build_rename_plan(
        entries, crc32_to_title, seasons, lookup, extended_mode
    )

    if unrecognized:
        print(f"{len(unrecognized)} local file(s) unrecognized/obsolete (left untouched):")
        for file_path, crc32, reason in unrecognized:
            print(f"  {os.path.basename(file_path)} [{crc32}]: {reason}")

    if not rename_plan:
        print("No files to rename.")
        print(
            f"0/{total} files matched for renaming "
            f"({len(already_correct)} already correct, {len(unrecognized)} unrecognized)."
        )
        _print_rename_summary(total, 0, len(already_correct), len(unrecognized), 0)
        return

    print("Rename plan:")
    for item in rename_plan:
        print(f"{item['old_path']} -> {item['new_path']}")
    print(f"{len(rename_plan)}/{total} files will be renamed and moved.")

    if dry_run:
        print("DRY RUN: would rename/move the above files (no changes made).")
        _print_rename_summary(total, 0, len(already_correct), len(unrecognized), 0)
        return

    confirm = _get_rename_confirmation()
    if confirm != "y":
        print("Renaming aborted.")
        return

    if IS_DOCKER and not _rename_force_enabled():
        print(
            "RENAME_FORCE is not set to 'true': running as DRY RUN ONLY in Docker mode. "
            "Set RENAME_FORCE=true to actually move/rename files."
        )
        _print_rename_summary(total, 0, len(already_correct), len(unrecognized), 0)
        return

    renamed, errors = _execute_rename(rename_plan, conn, folder=folder)
    _print_rename_summary(total, renamed, len(already_correct), len(unrecognized), errors)


def export_db_to_csv(conn):
    """Export local CRC32 database to CSV file.
    Args:
        conn: Database connection"""
    c = conn.cursor()
    c.execute("SELECT file_path, crc32 FROM crc32_cache")
    rows = c.fetchall()
    export_csv_path = get_config_path(DB_CSV_FILENAME)
    with open(export_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["File Path", "CRC32"])
        for row in rows:
            writer.writerow(row)
    print(f"Database exported to {export_csv_path}")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_metadata(conn, "last_db_export", now_str)


def _prompt_folder_interactive(conn):
    """Prompt user for folder using last_folder metadata or raw input. Returns folder or None."""
    last_folder = get_metadata(conn, "last_folder")
    if last_folder:
        print(f"Last used folder: {last_folder}")
        user_input = input(
            "Press Enter to use this folder, or enter a new path: "
        ).strip()
        folder = user_input if user_input else last_folder
    else:
        folder = input("Enter the folder containing local video files: ").strip()
    if not folder:
        print("Error: No folder specified.")
        return None
    return folder


def _get_folder_from_args(args, conn, needs_folder):
    """Get folder path from arguments or prompt user.
    In Docker uses ACEPACE_MEDIA_DIR_DOCKER (default /media); locally uses ACEPACE_MEDIA_DIR_LOCAL if set.
    """
    folder = args.folder
    if IS_DOCKER and needs_folder:
        folder = _get_default_media_dir()
        set_metadata(conn, "last_folder", folder)
        return folder
    if needs_folder and not folder:
        default_media = _get_default_media_dir()
        if default_media:
            folder = default_media
            set_metadata(conn, "last_folder", folder)
            return folder
        folder = _prompt_folder_interactive(conn)
        if folder is None:
            return None
        set_metadata(conn, "last_folder", folder)
    elif folder:
        set_metadata(conn, "last_folder", folder)
    return folder


def _get_client_from_args_or_env(args):
    """Get client type from args or environment variables.
    In Docker mode, defaults to 'transmission' if not specified.
    """
    if IS_DOCKER and not args.client:
        return os.getenv("TORRENT_CLIENT", "transmission")
    return args.client


def _get_default_port(client):
    """Get default port for a given client."""
    return 9091 if client == "transmission" else 8080


def _get_docker_connection_params(args):
    """Get connection parameters from Docker environment variables.
    Uses default values: localhost, 9091, transmission if not specified.
    """
    # Get client (defaults to transmission in Docker)
    client = _get_client_from_args_or_env(args)
    
    # Get host (defaults to localhost)
    host = os.getenv("TORRENT_HOST", args.host or "localhost")
    
    # Get port (defaults to 9091 for transmission, 8080 for qbittorrent)
    port_env = os.getenv("TORRENT_PORT")
    port = int(port_env) if port_env else None
    if not port:
        default_port = _get_default_port(client)
        port = args.port if args.port else default_port
    
    username = os.getenv("TORRENT_USER", args.username or "")
    password = os.getenv("TORRENT_PASSWORD", args.password or "")
    download_folder = args.download_folder or _get_default_media_dir()
    return host, port, username, password, download_folder, client


def _get_non_docker_connection_params(args):
    """Get connection parameters from command-line arguments."""
    host = args.host or "localhost"
    port = args.port
    if not port:
        port = _get_default_port(args.client)
    username = args.username or ""
    password = args.password or ""
    download_folder = args.download_folder
    return host, port, username, password, download_folder


def _load_magnet_links():
    """Load magnet links from the missing CSV file.
    Deduplicates magnet links so grouped episodes (sharing same magnet) are only added once."""
    missing_csv_path = get_config_path(MISSING_CSV_FILENAME)
    if not os.path.exists(missing_csv_path):
        print(f"Missing file '{missing_csv_path}' not found. Run the script first!")
        return None

    magnets_set = set()
    total_magnets = 0
    with open(missing_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            magnet_link = row.get(CSV_COLUMN_MAGNET_LINK, "").strip()
            if magnet_link.startswith(MAGNET_LINK_PREFIX):
                total_magnets += 1
                magnets_set.add(magnet_link)

    if not magnets_set:
        print(f"No magnet links found in '{missing_csv_path}'.")
        return None

    # Convert to list and return (sorted for consistent ordering)
    magnets = sorted(list(magnets_set))
    duplicates = total_magnets - len(magnets_set)
    if duplicates > 0:
        print(f"Deduplicated {duplicates} duplicate magnet links (grouped episodes share same magnet).")
    
    return magnets


def _setup_docker_connection(args):
    """Setup connection parameters for Docker mode."""
    host, port, username, password, download_folder, client = _get_docker_connection_params(args)
    # Log connection parameters in Docker mode
    print("Download configuration:")
    print(f"  Client: {client}")
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    if username:
        print(f"  Username: {username}")
    if download_folder:
        print(f"  Download folder: {download_folder}")
    if args.dry_run:
        print("  Mode: DRY RUN (no torrents will be added)")
    return host, port, username, password, download_folder, client


def _setup_non_docker_connection(args):
    """Setup connection parameters for non-Docker mode."""
    client = _get_client_from_args_or_env(args)
    if not client:
        print("Error: --client is required when using --download.")
        return None, None, None, None, None, None
    host, port, username, password, download_folder = _get_non_docker_connection_params(args)
    if args.dry_run:
        print("DRY RUN MODE: Testing connection without adding torrents...")
    return host, port, username, password, download_folder, client


def _execute_download_dry_run(client_obj, magnets, client, download_folder, tags, category):
    """Execute download in dry-run mode."""
    print(f"DRY RUN: Would add {len(magnets)} missing episode(s) to {client}...")
    print("DRY RUN: Testing connection and validating magnet links...")
    client_obj.add_torrents(
        magnets,
        download_folder=download_folder,
        tags=tags,
        category=category,
        dry_run=True,
    )
    print(f"DRY RUN: Successfully validated connection to {client}.")
    print(f"DRY RUN: {len(magnets)} magnet link(s) would be added (no torrents were actually added).")


def _execute_download(client_obj, magnets, client, download_folder, tags, category):
    """Execute actual download."""
    print(f"Adding {len(magnets)} missing episode(s) to {client}...")
    client_obj.add_torrents(
        magnets,
        download_folder=download_folder,
        tags=tags,
        category=category,
    )
    print(f"Successfully added {len(magnets)} episode(s) to {client}.")


def _handle_download_command(args):
    """Handle the download command."""
    # Get connection parameters based on Docker mode
    if IS_DOCKER:
        result = _setup_docker_connection(args)
    else:
        result = _setup_non_docker_connection(args)
    
    if result[0] is None:  # Check if setup failed
        return False
    
    host, port, username, password, download_folder, client = result

    magnets = _load_magnet_links()
    if magnets is None:
        return False

    try:
        client_obj = get_client(client, host, port, username, password)
        if args.dry_run:
            _execute_download_dry_run(client_obj, magnets, client, download_folder, args.tag, args.category)
        else:
            _execute_download(client_obj, magnets, client, download_folder, args.tag, args.category)
    except ConnectionError as e:
        print(f"Connection Error: {e}")
        print(f"Please verify that {client} is running and accessible at {host}:{port}")
        return False
    except ValueError as e:
        print(f"Configuration Error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return False

    return True


def _get_rename_prompt(last_ep_update):
    """Get user prompt for updating episodes database before renaming."""
    if IS_DOCKER:
        # In Docker mode, always update if database hasn't been updated
        return "y" if not last_ep_update else "n"
    
    if not last_ep_update:
        print("WARNING: Episodes metadata database has not been updated yet.")
        return input("Update episodes metadata database before renaming? (y/n): ").strip().lower()
    else:
        return input(
            f"Update episodes metadata database before renaming? (last update: {last_ep_update}) (y/n): "
        ).strip().lower()


def _ensure_crc32_cache_complete(folder, conn):
    """Ensure CRC32 cache includes all local video files for the folder.
    If any video files in folder are not in the cache, runs calculate_local_crc32.
    Respects config/data paths from get_config_dir (Docker vs local via env).
    """
    total_files, recorded_files = _count_video_files(folder, conn)
    if total_files == 0:
        print("No video files found in folder; skipping CRC32 cache check.")
        return
    if recorded_files < total_files:
        missing_count = total_files - recorded_files
        print(
            f"CRC32 cache missing {missing_count} of {total_files} files. "
            "Calculating CRC32s for local files..."
        )
        calculate_local_crc32(folder, conn)
    else:
        print("CRC32 cache is up to date for local files.")


def _handle_rename_command(conn, base_url=None, dry_run=False, folder=None, extended_mode=False):
    """Handle the rename command.
    Args:
        conn: Database connection
        base_url: Base URL for Nyaa search (optional)
        dry_run: If True, only show rename plan and do not rename or ask for confirmation.
        folder: Local media folder for CRC32 cache check (uses version-specific default if not set).
        extended_mode: True to prefer extended episodes (VERSION=extended).
    """
    episodes_db_conn = init_episodes_db()
    last_ep_update = get_episodes_metadata(
        episodes_db_conn, "episodes_db_last_update"
    )
    episodes_db_conn.close()

    prompt = _get_rename_prompt(last_ep_update)

    if prompt == "y":
        update_episodes_index_db(base_url)
    if folder:
        _ensure_crc32_cache_complete(folder, conn)
    print(
        "Renaming local files based on matching titles from One Pace episodes index..."
    )
    rename_local_files(conn, dry_run=dry_run, extended_mode=extended_mode, folder=folder)


def _count_video_files(folder, conn):
    """Count total video files and files already recorded in DB."""
    total_files = 0
    recorded_files = 0
    c = conn.cursor()
    for root, dirs, files in os.walk(folder):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                total_files += 1
                file_path = os.path.join(root, file)
                # Normalize path for consistent lookup
                normalized_path = normalize_file_path(file_path)
                c.execute("SELECT 1 FROM crc32_cache WHERE file_path = ?", (normalized_path,))
                if c.fetchone():
                    recorded_files += 1
    return total_files, recorded_files


def _load_old_missing_crc32s():
    """Load CRC32s from previous missing CSV file."""
    old_missing_crc32s = set()
    missing_csv_path = get_config_path(MISSING_CSV_FILENAME)
    if os.path.exists(missing_csv_path):
        with open(missing_csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if len(row) >= 1:
                    title = row[0]
                    # Extract CRC32 from title if possible
                    matches = CRC32_REGEX.findall(title)
                    if matches:
                        old_missing_crc32s.add(matches[-1].upper())
    return old_missing_crc32s


def _save_missing_episodes_csv(missing, crc32_to_text, crc32_to_link, crc32_to_magnet):
    """Save missing episodes to CSV file."""
    missing_csv_path = get_config_path(MISSING_CSV_FILENAME)
    saved_count = 0
    error_count = 0
    with open(missing_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["Title", "Page Link", CSV_COLUMN_MAGNET_LINK])
        for crc32 in missing:
            try:
                title = crc32_to_text.get(crc32, f"[CRC32: {crc32}]")
                page_link = crc32_to_link.get(crc32, "")
                magnet = crc32_to_magnet.get(crc32, "")
                writer.writerow([title, page_link, magnet])
                saved_count += 1
            except (IOError, OSError, csv.Error) as e:
                error_count += 1
                print(f"ERROR: Failed to save missing episode with CRC32 '{crc32}': {e}")
                # Still write a row with available information
                writer.writerow([f"[ERROR: CRC32 {crc32}]", "", ""])
    
    print(f"Missing files list saved to {missing_csv_path}")
    if error_count > 0:
        print(f"WARNING: {error_count} episodes had errors while saving to CSV")
    if saved_count == 0 and len(missing) > 0:
        print(f"ERROR: No episodes were successfully saved to CSV despite {len(missing)} missing episodes!")
        print("This indicates a critical issue with the CRC32 mapping.")


def _print_report_header(conn, folder, args):
    """Print header information for the report."""
    last_missing_export = get_metadata(conn, "last_missing_export")
    if last_missing_export:
        print(f"Last missing files list generated on: {last_missing_export}")

    total_files, recorded_files = _count_video_files(folder, conn)

    last_run = get_metadata(conn, "last_run")
    if last_run:
        print(f"Last run was on: {last_run}")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_metadata(conn, "last_run", now_str)

    # Show URL, but note that quality filtering (1080p only) is applied regardless
    url_display = args.url
    if "1080p" not in url_display:
        url_display += " (quality filtering: 1080p only)"
    print(f"Using URL: {url_display}")
    print(f"Total video files detected: {total_files}")
    print(f"Episodes already recorded in DB: {recorded_files}")
    
    return last_run


def _print_troubleshooting_header(crc32_to_link, local_crc32s):
    """Print initial troubleshooting information header."""
    debug_print("\n=== DEBUG: TROUBLESHOOTING INFO ===")
    debug_print(f"Episodes from Nyaa (crc32_to_link keys): {len(crc32_to_link)}")
    debug_print(f"Local CRC32s: {len(local_crc32s)}")
    
    # Check for empty sets
    if len(crc32_to_link) == 0:
        debug_print("WARNING: No episodes fetched from Nyaa! Check URL and quality filtering.")
    if len(local_crc32s) == 0:
        debug_print("WARNING: No local CRC32s found! Check folder path and file extensions.")
    
    # Show sample CRC32s from both sources (first 5)
    if crc32_to_link:
        sample_nyaa = list(crc32_to_link.keys())[:5]
        debug_print(f"Sample Nyaa CRC32s (first 5): {sample_nyaa}")
        debug_print(f"Sample Nyaa CRC32 types: {[type(c).__name__ for c in sample_nyaa]}")
    if local_crc32s:
        sample_local = list(local_crc32s)[:5]
        debug_print(f"Sample local CRC32s (first 5): {sample_local}")
        debug_print(f"Sample local CRC32 types: {[type(c).__name__ for c in sample_local]}")


def _normalize_crc32_sets(crc32_to_link, local_crc32s):
    """Normalize CRC32 sets to uppercase strings for comparison.
    Returns tuple: (nyaa_crc32s_normalized, local_crc32s_normalized)"""
    nyaa_crc32s_normalized = {str(c).strip().upper() for c in crc32_to_link.keys()}
    local_crc32s_normalized = {str(c).strip().upper() for c in local_crc32s}
    
    debug_print("\nAfter normalization:")
    debug_print(f"Nyaa CRC32s: {len(nyaa_crc32s_normalized)}")
    debug_print(f"Local CRC32s: {len(local_crc32s_normalized)}")
    
    # Check for matches using normalized sets
    matches_normalized = nyaa_crc32s_normalized & local_crc32s_normalized
    debug_print(f"Matches after normalization: {len(matches_normalized)}")
    if matches_normalized:
        debug_print(f"Sample matches (first 3): {list(matches_normalized)[:3]}")
    
    return nyaa_crc32s_normalized, local_crc32s_normalized


def _print_comparison_results(nyaa_crc32s_normalized, local_crc32s_normalized,
                              crc32_to_link, local_crc32s, missing, missing_normalized):
    """Print comparison results and troubleshooting information.

    ``missing`` is the FINAL grouped/version-aware missing list (one entry
    per missing canonical episode, using the newest version's CRC32).
    ``missing_normalized`` is the raw, ungrouped per-CRC32 comparison (every
    Nyaa CRC32 not found locally, before grouping collapses multi-version
    episodes together) - it's kept purely as a diagnostic baseline.

    Because grouping only ever collapses multiple missing CRC32s belonging
    to the same canonical episode into a single entry, ``len(missing) <=
    len(missing_normalized)`` is the expected, healthy relationship - it is
    NOT a bug indicator by itself. The reverse (grouped count higher than
    the raw count) would indicate a real bug in the grouping logic."""
    # Also check the original (unnormalized) comparison for debugging
    original_missing_count = len([c for c in crc32_to_link.keys() if c not in local_crc32s])
    debug_print(f"Missing episodes (original comparison): {original_missing_count}")
    debug_print(f"Missing episodes (raw normalized comparison): {len(missing_normalized)}")
    debug_print(f"Missing episodes (grouped/version-aware, final): {len(missing)}")

    if original_missing_count != len(missing_normalized):
        debug_print(f"WARNING: Comparison mismatch detected! Original: {original_missing_count}, Raw normalized: {len(missing_normalized)}")
        debug_print("This suggests a data type or format issue. Using normalized comparison.")

    if len(missing) > len(missing_normalized):
        debug_print(f"ERROR: Grouped missing count ({len(missing)}) exceeds raw normalized missing count ({len(missing_normalized)})!")
        debug_print("Grouping should only ever reduce (or match) the missing count - this indicates a bug in grouped detection.")
    elif len(missing) < len(missing_normalized):
        debug_print(f"Grouped missing count ({len(missing)}) is lower than raw normalized missing count ({len(missing_normalized)}).")
        debug_print("This is expected when multiple versions of the same episode are grouped together (present-if-any-version-local semantics).")

    # Show intersection details
    intersection = nyaa_crc32s_normalized & local_crc32s_normalized
    debug_print(f"Intersection (episodes found locally): {len(intersection)}")
    if intersection:
        debug_print(f"Sample found episodes (first 3): {list(intersection)[:3]}")
    
    # Show difference details
    difference = nyaa_crc32s_normalized - local_crc32s_normalized
    debug_print(f"Difference (episodes NOT found locally): {len(difference)}")
    if difference:
        debug_print(f"Sample missing episodes (first 3): {list(difference)[:3]}")
    
    # Check if sets are suspiciously similar (potential bug indicator)
    if len(nyaa_crc32s_normalized) > 0 and len(local_crc32s_normalized) > 0:
        similarity_ratio = len(intersection) / len(nyaa_crc32s_normalized)
        debug_print(f"Similarity ratio (intersection/nyaa): {similarity_ratio:.2%}")
        if similarity_ratio > 0.95 and len(difference) == 0:
            debug_print("WARNING: Almost all Nyaa episodes appear to be found locally!")
            debug_print("This might indicate a comparison bug or data issue.")
            debug_print("Please verify that your local files actually contain all these episodes.")
    
    # Check for sets being identical (definite bug)
    if nyaa_crc32s_normalized == local_crc32s_normalized:
        debug_print("ERROR: Nyaa and local CRC32 sets are IDENTICAL!")
        debug_print("This indicates a critical bug - the sets should not be the same.")
        debug_print("Possible causes:")
        debug_print("  - Local CRC32s are being populated from Nyaa data (wrong source)")
        debug_print("  - Comparison is using the same set for both sides")
        debug_print("  - Database corruption or incorrect data")
    
    debug_print("=== END DEBUG: TROUBLESHOOTING INFO ===\n")


def _should_force_episodes_update(last_update_str):
    """Determine if episodes should be force updated based on last update time.
    Args:
        last_update_str: String timestamp of last update, or None
    Returns: True if should force update, False if recently updated (within 10 minutes)"""
    if not last_update_str:
        return True
    
    try:
        last_update = datetime.strptime(last_update_str, "%Y-%m-%d %H:%M:%S")
        time_diff = datetime.now() - last_update
        # If updated within last 10 minutes, skip to avoid double update
        if time_diff.total_seconds() < 600:  # 10 minutes = 600 seconds
            print("EPISODES_UPDATE=true: Episodes were recently updated, using existing database...")
            return False
    except (ValueError, TypeError):
        # If parsing fails, proceed with update
        pass
    return True


def _handle_episodes_update_decision(episodes_update_env, last_update_str, base_url):
    """Handle the decision to update episodes based on EPISODES_UPDATE environment variable.
    Args:
        episodes_update_env: True if EPISODES_UPDATE environment variable is set
        last_update_str: String timestamp of last update, or None
        base_url: Base URL for Nyaa search
    Returns: True if database should be used, False if should fetch from Nyaa"""
    if episodes_update_env:
        # EPISODES_UPDATE=true: Force update episodes even if recently updated
        if _should_force_episodes_update(last_update_str):
            print("EPISODES_UPDATE=true: Forcing episodes metadata update...")
            update_episodes_index_db(base_url, force_update=True)
        # After update (forced or skipped), always use database
        return True
    
    # EPISODES_UPDATE=false or not set: Use database only, never fetch from Nyaa
    if last_update_str:
        return True
    
    # Database doesn't exist, need to fetch (but this shouldn't happen in normal operation)
    print("Episodes database not found. Fetching from Nyaa...")
    return False


def _load_episodes_from_database(episodes_update_env, base_url, fetch_magnets=True):
    """Load episodes from database, including magnet links stored in database.
    Args:
        episodes_update_env: True if EPISODES_UPDATE environment variable is set
        base_url: Base URL for Nyaa search (unused now, kept for compatibility)
        fetch_magnets: If True, fetch missing magnet links from Nyaa. If False, use only database.
    Returns: Tuple of (crc32_to_link, crc32_to_text, crc32_to_magnet, crc32_to_pubdate,
    last_checked_page)"""
    if episodes_update_env:
        print("Using episodes index database (EPISODES_UPDATE=true, using updated database)...")
    else:
        print("Using episodes index database (EPISODES_UPDATE=false, checking database only)...")

    crc32_to_link, crc32_to_text, crc32_to_magnet, crc32_to_pubdate = (
        load_1080p_episodes_with_pubdates_from_index()
    )
    print(f"Loaded {len(crc32_to_link)} 1080p episodes from database.")
    
    # Count how many episodes have magnet links in database
    episodes_with_magnets_count = sum(1 for m in crc32_to_magnet.values() if m)
    print(f"Found {episodes_with_magnets_count} episodes with magnet links in database.")
    
    if fetch_magnets:
        # Find episodes missing magnet links
        missing_magnets = {crc32: crc32_to_link[crc32] for crc32 in crc32_to_link 
                          if not crc32_to_magnet.get(crc32)}
        if missing_magnets:
            print(f"Fetching {len(missing_magnets)} missing magnet links from search results...")
            fetched_magnets = fetch_magnet_links_for_episodes_from_search(base_url, missing_magnets)
            # Update database magnet links with newly fetched ones
            crc32_to_magnet.update(fetched_magnets)
            print(f"Fetched {len(fetched_magnets)} new magnet links.")
            
            # Update database with newly fetched magnet links (batch update for efficiency)
            conn = init_episodes_db()
            c = conn.cursor()
            c.executemany(
                "UPDATE episodes_index SET magnet_link = ? WHERE crc32 = ?",
                [(magnet_link, crc32) for crc32, magnet_link in fetched_magnets.items()]
            )
            conn.commit()
            conn.close()
    
    # Restrict to episodes we have magnet links for (matches previous behavior)
    # This ensures we only count episodes that can actually be downloaded
    # Filter to only episodes with non-empty magnet links that exist in crc32_to_link
    episodes_with_magnets = {c: m for c, m in crc32_to_magnet.items() if m and c in crc32_to_link}
    # Update all dictionaries to only include episodes with magnet links
    # Note: All keys in episodes_with_magnets are guaranteed to exist in crc32_to_link and crc32_to_text
    # since they're loaded together from the same database query
    crc32_to_link = {c: crc32_to_link[c] for c in episodes_with_magnets}
    crc32_to_text = {c: crc32_to_text[c] for c in episodes_with_magnets}
    crc32_to_pubdate = {c: crc32_to_pubdate.get(c) for c in episodes_with_magnets}
    crc32_to_magnet = episodes_with_magnets

    return crc32_to_link, crc32_to_text, crc32_to_magnet, crc32_to_pubdate, 0


def _calculate_missing_episodes(crc32_to_link, crc32_to_text, crc32_to_magnet,
                                crc32_to_pubdate, local_crc32s):
    """Calculate missing episodes using grouped, version-aware detection (Part E).

    This is the live/default missing-episode detection path. A canonical
    episode (season, number, is_extended) is considered present if ANY of
    its versions' CRC32s is found locally; when missing, it is reported
    using the CRC32/magnet of the NEWEST version (highest pub_date), so
    downloads always fetch the newest release. Titles that fail to parse
    fall back to a singleton group, so they behave like the legacy
    ungrouped comparison and are never silently dropped.

    CRC32 case is normalized (uppercase) before the grouped comparison so
    upper/lowercase mismatches between Nyaa-sourced and locally-computed
    CRC32s are tolerated, exactly like the legacy CRC32-only comparison.

    Args:
        crc32_to_link: Dictionary mapping CRC32 to page_link
        crc32_to_text: Dictionary mapping CRC32 to release title
        crc32_to_magnet: Dictionary mapping CRC32 to magnet link
        crc32_to_pubdate: Dictionary mapping CRC32 to Nyaa pub_date (may be
            sparse/empty, e.g. when episodes were fetched via the legacy
            bootstrap path that doesn't capture pub_date)
        local_crc32s: Set of local CRC32 checksums
    Returns: List of missing CRC32s (newest-version CRC32 per missing group)"""
    debug_print("DEBUG: Starting missing episode detection (grouped/version-aware)")
    debug_print(f"DEBUG: Episodes from Nyaa: {len(crc32_to_link)}")
    debug_print(f"DEBUG: Local CRC32s: {len(local_crc32s)}")

    # Print troubleshooting header
    _print_troubleshooting_header(crc32_to_link, local_crc32s)

    # Normalize CRC32 sets (uppercase) - preserves the legacy tolerance for
    # upper/lowercase CRC32 mismatches. Nyaa-sourced dict keys (crc32_to_text
    # etc.) are already uppercase (extraction always upper()s them), so only
    # local_crc32s realistically needs normalizing, but we normalize both for
    # parity with the original behavior and to feed the diagnostic prints.
    nyaa_crc32s_normalized, local_crc32s_normalized = _normalize_crc32_sets(
        crc32_to_link, local_crc32s
    )

    # Raw, ungrouped per-CRC32 comparison - kept purely as a diagnostic
    # baseline for _print_comparison_results (grouping is expected to
    # collapse this further, not replace it as ground truth).
    missing_normalized_set = nyaa_crc32s_normalized - local_crc32s_normalized

    # Grouped/version-aware detection: the actual, live decision.
    missing = _calculate_missing_episodes_grouped(
        crc32_to_text, crc32_to_magnet, crc32_to_pubdate, local_crc32s_normalized
    )

    # Print comparison results (adapted to compare raw vs. grouped counts)
    _print_comparison_results(
        nyaa_crc32s_normalized, local_crc32s_normalized,
        crc32_to_link, local_crc32s, missing, list(missing_normalized_set)
    )

    return missing


def _calculate_and_find_missing(folder, conn, args, last_run):
    """Calculate local CRC32s and find missing episodes."""
    # Check EPISODES_UPDATE environment variable
    episodes_update_env = os.getenv("EPISODES_UPDATE", "").lower() in ("true", "1", "yes", "on")
    
    # Check if episodes_index exists and has data
    conn_episodes = init_episodes_db()
    last_update_str = get_episodes_metadata(conn_episodes, "episodes_db_last_update")
    
    # Determine whether to use database or fetch from Nyaa
    use_database = _handle_episodes_update_decision(episodes_update_env, last_update_str, args.url)
    conn_episodes.close()
    
    # Load episodes (from database or fetch from Nyaa)
    # Magnet links are now stored in the database, so we load them directly
    if use_database:
        # Load episodes from database, including magnet links and pub_dates
        # fetch_magnets=True will fetch any missing magnet links from Nyaa
        crc32_to_link, crc32_to_text, crc32_to_magnet, crc32_to_pubdate, last_checked_page = (
            _load_episodes_from_database(episodes_update_env, args.url, fetch_magnets=True)
        )
    else:
        # Normal fetch from Nyaa (only when database doesn't exist and EPISODES_UPDATE=false)
        print("Fetching episodes metadata from Nyaa...")
        crc32_to_link, crc32_to_text, crc32_to_magnet, last_checked_page = (
            fetch_crc32_links(args.url)
        )
        # fetch_crc32_links() doesn't capture pub_date (only
        # fetch_episodes_metadata() does), so newest-version selection falls
        # back to arbitrary tie-breaking within a group in this bootstrap-only
        # path. Rare in practice: it only runs before the episodes DB exists.
        crc32_to_pubdate = {}

    print(f"Found {len(crc32_to_link)} episodes from Nyaa.")

    # Calculate local CRC32s
    if last_run:
        print("Calculating new local CRC32 hashes...")
    else:
        print(
            "Calculating local CRC32 hashes - this will take a while on first run!..."
        )

    local_crc32s = calculate_local_crc32(folder, conn)
    print(f"Found {len(local_crc32s)} local CRC32 hashes.")
    
    debug_print(f"DEBUG: Folder scanned: {folder}")

    # Calculate missing episodes (only those with magnet links can be downloaded)
    missing = _calculate_missing_episodes(
        crc32_to_link, crc32_to_text, crc32_to_magnet, crc32_to_pubdate, local_crc32s
    )
    # Filter to only missing episodes that have magnet links (redundant check removed)
    missing = [crc32 for crc32 in missing if crc32_to_magnet.get(crc32)]

    print(
        f"\nSummary: {len(missing)} missing episodes out of {len(crc32_to_link)} total found on Nyaa.\n"
    )
    
    return missing, crc32_to_text, crc32_to_link, crc32_to_magnet, last_checked_page


def _report_new_missing_episodes(missing, crc32_to_text):
    """Report newly detected missing episodes."""
    old_missing_crc32s = _load_old_missing_crc32s()
    new_crc32s = set(missing) - old_missing_crc32s
    if new_crc32s:
        print(f"New missing episodes detected since last export: {len(new_crc32s)}")
        # Only print individual episodes in DEBUG mode
        if DEBUG_MODE:
            for crc32 in new_crc32s:
                title = crc32_to_text.get(crc32, "(Unknown Title)")
                debug_print(f"Missing: {title}")


def _print_missing_report_summary(total, present, missing_count, unrecognized_local_count):
    """Print the final missing-report summary table (Part H2)."""
    print("\n=== Missing Report Summary ===")
    print(f"Total on Nyaa: {total}")
    print(f"Present locally: {present}")
    print(f"Missing: {missing_count}")
    if unrecognized_local_count:
        print(f"Unrecognized local files: {unrecognized_local_count}")


def _generate_missing_episodes_report(conn, folder, args):
    """Generate and save missing episodes report."""
    last_run = _print_report_header(conn, folder, args)

    missing, crc32_to_text, crc32_to_link, crc32_to_magnet, last_checked_page = (
        _calculate_and_find_missing(folder, conn, args, last_run)
    )

    _report_new_missing_episodes(missing, crc32_to_text)

    _save_missing_episodes_csv(missing, crc32_to_text, crc32_to_link, crc32_to_magnet)

    set_metadata(conn, "last_checked_page", str(last_checked_page))
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_metadata(conn, "last_missing_export", now_str)

    # Print missing count prominently
    print(f"Missing episodes: {len(missing)}")

    total_on_nyaa = len(crc32_to_link)
    _print_missing_report_summary(
        total_on_nyaa, total_on_nyaa - len(missing), len(missing), 0
    )

    return missing, crc32_to_text


def _print_help():
    """Print detailed help information about all available commands."""
    help_text = """
Ace-Pace - Find missing episodes from your personal One Pace library

AVAILABLE COMMANDS:

  Main Operations:
    (no flags)              Generate missing episodes report
                            Scans local folder, calculates CRC32 hashes, and compares
                            with episodes available on Nyaa to find missing episodes.
                            Outputs results to Ace-Pace_Missing.csv

    --episodes_update       Update episodes from Nyaa and generate missing report
                            First fetches all One Pace episodes from Nyaa and stores
                            CRC32, title, page link, and magnet link in the episodes index.
                            Then runs the missing episodes report (same as main command):
                            scans local folder, compares with Nyaa, outputs Ace-Pace_Missing.csv.
                            In Docker mode, --folder defaults to /media if not set.

    --rename                Rename local files based on CRC32 matching
                            Matches local video files with episodes in the database
                            and renames them to match the official episode titles.
                            Prompts to update episodes database if it's outdated.

    --db                    Export local CRC32 database to CSV
                            Exports the database of calculated CRC32 hashes for
                            local video files to Ace-Pace_DB.csv

    --download              Download missing episodes via BitTorrent client
                            Reads magnet links from Ace-Pace_Missing.csv and adds
                            them to the specified BitTorrent client (requires --client)

    --dry-run               Test connection to BitTorrent client without adding torrents
                            Validates magnet links and checks existing torrents but
                            does not add any downloads. Useful for verifying configuration.
                            Also makes --rename report its plan without touching the filesystem.

    --undo                  Undo the last real --rename run
                            Reverses the moves/renames journaled during the most recent
                            non-dry-run --rename, and reverts the crc32 cache's recorded
                            file paths. Only the last run is journaled (not full history).

    --doctor                Run diagnostics and exit
                            Checks: media folder readable, reference data present/fresh,
                            episodes_index.db has rows, torrent client connectivity (if
                            configured), and SQLite file integrity. Exit code is non-zero
                            if any hard check fails.

  Rename Options:
    --version {normal,extended}
                            Which episode version is canonical for rename/missing lookups
                            Default: normal (env: VERSION). "extended" prefers the
                            extended/alternate cut of an episode when both exist.

  Output Options:
    --quiet                 Suppress non-essential output (errors and final summaries still print)

    --verbose               Enable debug logging (equivalent to DEBUG=true)

  BitTorrent Client Options (for --download):
    --client {transmission,qbittorrent}
                            Specify which BitTorrent client to use
                            Required when using --download

    --host HOST             BitTorrent client host (default: localhost)

    --port PORT             BitTorrent client port
                            Defaults: Transmission=9091, qBittorrent=8080

    --username USERNAME     BitTorrent client username (if required)

    --password PASSWORD     BitTorrent client password (if required)

    --download-folder PATH  Folder where torrents should be downloaded
                            Default: /media (in Docker) or client default

    --tag TAG               Add tag to torrents in qBittorrent
                            Can be used multiple times to add multiple tags

    --category CATEGORY     Add category to torrents in qBittorrent

  General Options:
    --url URL               Custom Nyaa search URL
                            Default: https://nyaa.si/?f=0&c=0_0&q=one+pace&o=asc
                            Note: Quality filtering (1080p only) is applied in code regardless of URL
                            Must point to a valid Nyaa domain

    --folder PATH           Folder containing local video files
                            If not specified, will prompt for input
                            In Docker mode, defaults to /media

ENVIRONMENT VARIABLES:
  Most flags above have an equivalent env var (CLI flag > env var > acepace.toml
  > built-in default). Notably:
    VERSION                 "normal" or "extended" (see --version above)
    RENAME_FORCE            In Docker, must be "true" for --rename to perform real
                            (non-dry-run) moves; otherwise Docker runs are dry-run-only.
    REFERENCE_UPDATE        Refresh vendored one-pace-for-plex reference data at startup.
  See acepace.toml.example for the full list of config-file/env-var keys.

EXAMPLES:

  # Generate missing episodes report
  python acepace.py --folder /path/to/videos

  # Update episodes database
  python acepace.py --episodes_update

  # Rename local files to match episode titles
  python acepace.py --folder /path/to/videos --rename

  # Download missing episodes to qBittorrent
  python acepace.py --download --client qbittorrent --host localhost --port 8080

  # Test connection without downloading (dry run)
  python acepace.py --download --client transmission --dry-run

  # Export database to CSV
  python acepace.py --folder /path/to/videos --db

For more information, visit: https://github.com/your-repo/ace-pace
"""
    print(help_text)


def _parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Find missing episodes from your personal One Pace library.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,  # Disable automatic help to use custom one
        epilog="""
Examples:
  python acepace.py --folder /path/to/videos
  python acepace.py --episodes_update
  python acepace.py --rename --folder /path/to/videos
  python acepace.py --download --client qbittorrent

Use --help for detailed command descriptions.
        """
    )
    parser.add_argument(
        "--help", "-h",
        action="store_true",
        help="Show detailed help message with all available commands."
    )
    parser.add_argument(
        "--url",
        default=f"{NYAA_BASE_URL}/?f=0&c=0_0&q=one+pace&o=asc",
        help=f"Base URL without the page param. Default searches for 'one pace' without quality filter (quality filtering 1080p only is applied in code). Example: '{NYAA_BASE_URL}/?f=0&c=0_0&q=one+pace&o=asc' ",
    )
    parser.add_argument("--folder", help="Folder containing local video files.")
    parser.add_argument(
        "--db", action="store_true", help="Export database to CSV and exit."
    )
    parser.add_argument(
        "--client",
        choices=["transmission", "qbittorrent"],
        help="The BitTorrent client to use (required for --download).",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Import magnet links from missing CSV and add to the specified BitTorrent client.",
    )
    parser.add_argument(
        "--rename",
        action="store_true",
        help="Rename local files based on CRC32 matching titles from Nyaa.",
    )
    parser.add_argument(
        "--episodes_update",
        action="store_true",
        help="Update episodes from Nyaa, then run missing episodes report (like main command).",
    )
    parser.add_argument("--host", default="localhost", help="The BitTorrent client host.")
    parser.add_argument("--port", type=int, help="The BitTorrent client port.")
    parser.add_argument("--username", help="The BitTorrent client username.")
    parser.add_argument("--password", help="The BitTorrent client password.")
    parser.add_argument("--download-folder", help="The folder to download the torrents to.")
    parser.add_argument("--tag", action="append", help="Tag to add to the torrent in qBittorrent (can be used multiple times).")
    parser.add_argument("--category", help="Category to add to the torrent in qBittorrent.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download: test client without adding torrents. Rename: show rename plan without renaming.",
    )
    parser.add_argument(
        "--version",
        choices=["normal", "extended"],
        default=os.getenv("VERSION", "normal"),
        help="Which episode version to treat as canonical for rename/missing-detection: "
             "'normal' (default) or 'extended'. Also settable via VERSION env var.",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="Undo the most recent --rename run (reverses file moves and DB paths).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-essential output (errors and final summaries are still printed).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Equivalent to DEBUG=true: print detailed debug information.",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run diagnostics (folder, reference data, databases, torrent client) and exit.",
    )
    return parser.parse_args()


def _validate_url(url):
    """Validate that URL points to a valid Nyaa domain."""
    if not url.startswith((NYAA_BASE_URL, "https://nyaa.land")):
        print(
            f"Error: The --url argument must point to a valid Nyaa website ({NYAA_BASE_URL} or https://nyaa.land)."
        )
        return False
    return True


def _show_episodes_metadata_status():
    """Show last episodes metadata update status."""
    episodes_db_conn = init_episodes_db()
    last_ep_update = get_episodes_metadata(episodes_db_conn, "episodes_db_last_update")
    if last_ep_update:
        print(f"Episodes metadata last updated: {last_ep_update}")
    else:
        print("Episodes metadata database not yet updated.")
    episodes_db_conn.close()


def _doctor_check_folder(args):
    """Doctor check: media folder exists and is readable (informational if unconfigured)."""
    folder = getattr(args, "folder", None) or _get_default_media_dir()
    if not folder:
        print("[WARN] Media folder: not configured (no --folder given); skipping.")
        return True
    if os.path.isdir(folder) and os.access(folder, os.R_OK):
        print(f"[PASS] Media folder: '{folder}' exists and is readable.")
        return True
    print(f"[FAIL] Media folder: '{folder}' does not exist or is not readable.")
    return False


def _doctor_check_reference_data():
    """Doctor check: vendored reference data is present and reports its freshness."""
    index_path = os.path.join(str(REFERENCE_BASE_DIR), "episodes_index.json")
    if not os.path.isfile(index_path) or os.path.getsize(index_path) == 0:
        print(f"[FAIL] Reference data: '{index_path}' missing or empty.")
        return False
    print(f"[PASS] Reference data: '{index_path}' present.")
    _doctor_report_reference_data_age(os.path.join(str(REFERENCE_BASE_DIR), "metadata.json"))
    return True


def _doctor_report_reference_data_age(metadata_path):
    """Print an informational pass/warn line about reference data staleness."""
    if not os.path.isfile(metadata_path):
        return
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        last_refresh = metadata.get("last_refresh")
        if not last_refresh:
            return
        refreshed_at = datetime.fromisoformat(last_refresh)
        now = datetime.now(refreshed_at.tzinfo) if refreshed_at.tzinfo else datetime.now()
        age_days = (now - refreshed_at).days
        if age_days > 30:
            print(f"[WARN] Reference data last refreshed {age_days} day(s) ago ({last_refresh}).")
        else:
            print(f"[PASS] Reference data last refreshed {age_days} day(s) ago ({last_refresh}).")
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"[WARN] Reference data: could not read metadata.json: {e}")


def _doctor_check_episodes_db():
    """Doctor check: episodes_index.db exists and has rows."""
    db_path = get_config_path(EPISODES_DB_NAME)
    if not os.path.isfile(db_path):
        print(f"[FAIL] Episodes DB: '{db_path}' does not exist.")
        return False
    try:
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM episodes_index").fetchone()[0]
        conn.close()
    except sqlite3.Error as e:
        print(f"[FAIL] Episodes DB: '{db_path}' could not be read: {e}")
        return False
    if count == 0:
        print(f"[WARN] Episodes DB: '{db_path}' exists but has no rows yet.")
    else:
        print(f"[PASS] Episodes DB: '{db_path}' has {count} row(s).")
    return True


def _doctor_check_sqlite_integrity(db_name):
    """Doctor check: SQLite file opens and passes PRAGMA integrity_check."""
    db_path = get_config_path(db_name)
    if not os.path.isfile(db_path):
        print(f"[WARN] {db_name}: not created yet, skipping integrity check.")
        return True
    try:
        conn = sqlite3.connect(db_path)
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
    except sqlite3.Error as e:
        print(f"[FAIL] {db_name}: could not open/check: {e}")
        return False
    if result and result[0] == "ok":
        print(f"[PASS] {db_name}: integrity check ok.")
        return True
    print(f"[FAIL] {db_name}: integrity check failed: {result}")
    return False


def _doctor_check_torrent_client(args):
    """Doctor check: attempt a lightweight connection to the configured torrent client."""
    client = _get_client_from_args_or_env(args) or os.getenv("TORRENT_CLIENT")
    if not client:
        print("[SKIP] Torrent client: not configured.")
        return True
    host = os.getenv("TORRENT_HOST") or getattr(args, "host", None) or "localhost"
    port_env = os.getenv("TORRENT_PORT")
    port = int(port_env) if port_env else (getattr(args, "port", None) or _get_default_port(client))
    username = os.getenv("TORRENT_USER") or getattr(args, "username", None) or ""
    password = os.getenv("TORRENT_PASSWORD") or getattr(args, "password", None) or ""
    try:
        get_client(client, host, port, username, password)
        print(f"[PASS] Torrent client: connected to {client} at {host}:{port}.")
        return True
    except Exception as e:
        print(f"[FAIL] Torrent client: could not connect to {client} at {host}:{port}: {e}")
        return False


def handle_doctor_command(args):
    """Run --doctor diagnostics; each check prints a pass/fail/warn/skip line.
    Returns the process exit code: 0 if all hard checks pass (informational
    warnings/skips don't fail the run), non-zero if any hard check fails."""
    print("Ace-Pace Doctor")
    print("=" * 60)
    results = [
        _doctor_check_folder(args),
        _doctor_check_reference_data(),
        _doctor_check_episodes_db(),
        _doctor_check_torrent_client(args),
        _doctor_check_sqlite_integrity(DB_NAME),
        _doctor_check_sqlite_integrity(EPISODES_DB_NAME),
    ]
    print("=" * 60)
    if all(results):
        print("Doctor: all checks passed (or informational only).")
        return 0
    print("Doctor: one or more checks failed.")
    return 1


def _handle_main_commands(args, conn, folder):
    """Handle main command execution."""
    if args.download:
        _handle_download_command(args)
        return

    if args.rename:
        extended_mode = _is_extended_mode(getattr(args, "version", None))
        _handle_rename_command(conn, args.url, dry_run=args.dry_run, folder=folder, extended_mode=extended_mode)
        return

    if not folder:
        print("Error: --folder argument is required.")
        return

    if args.db:
        export_db_to_csv(conn)
        return

    _generate_missing_episodes_report(conn, folder, args)

    # Note: To download missing episodes, use --download flag with --client


def _print_header():
    """Print Ace-Pace header banner."""
    print("=" * 60)
    print(" " * 20 + "Ace-Pace")
    print(" " * 12 + "One Pace Library Manager")
    release = _get_release_date()
    if release:
        print(" " * (26 - len(release) // 2) + f"Release {release}")
    print("=" * 60)
    if IS_DOCKER:
        print("Running in Docker mode (non-interactive)")
        print("-" * 60)
    print()


def main():
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    # Load acepace.toml (Part H4) before argparse so its values become the
    # defaults argparse reads via os.getenv(...); real env vars / CLI flags
    # still take precedence (see load_toml_config docstring).
    load_toml_config()
    _refresh_debug_mode_from_env()

    try:
        args = _parse_arguments()

        # Show detailed help if requested
        if args.help:
            _print_help()
            sys.exit(0)

        # --doctor runs diagnostics and exits before any folder/DB requirement.
        if getattr(args, "doctor", False) is True:
            sys.exit(handle_doctor_command(args))

        if getattr(args, "verbose", False) is True:
            set_debug_mode(True)
        if getattr(args, "quiet", False) is True:
            set_quiet_mode(True)

        # --undo reverses the most recent --rename run; no folder required.
        if getattr(args, "undo", False) is True:
            conn = init_db(suppress_messages=True)
            undo_last_rename(conn)
            sys.exit(0)

        # Print header only for main command (not for --db or --episodes_update)
        # In Docker, entrypoint.sh already prints the header once; skip here to avoid duplicate
        if not IS_DOCKER and not args.db and not args.episodes_update and not args.help:
            _print_header()

        if not _validate_url(args.url):
            sys.exit(1)

        # Only show episodes metadata status for main command (not for --db or --episodes_update)
        if not args.db and not args.episodes_update:
            _show_episodes_metadata_status()

        if args.episodes_update:
            # When --episodes_update is used: update episodes from Nyaa, then run missing episodes report (like main command)
            update_episodes_index_db(args.url, force_update=True)
            conn = init_db(suppress_messages=False)
            needs_folder = True  # Missing report requires folder
            folder = _get_folder_from_args(args, conn, needs_folder)
            if folder is None:
                sys.exit(1)
            _generate_missing_episodes_report(conn, folder, args)
            sys.exit(0)

        # Suppress messages when exporting DB (since it's automated)
        conn = init_db(suppress_messages=args.db)

        # Folder selection logic: Always prompt if folder is required but not given
        needs_folder = not args.download  # All commands except --download need folder
        folder = _get_folder_from_args(args, conn, needs_folder)
        if folder is None:
            sys.exit(1)

        _handle_main_commands(args, conn, folder)
        
        # Exit cleanly (code 0) even if shutdown was requested during processing
        sys.exit(0)
    except KeyboardInterrupt:
        print("\nInterrupted by user, exiting gracefully...")
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
