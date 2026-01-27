import time
import csv
from datetime import datetime
import sqlite3
import re
import argparse
import zlib
import os
import signal
import sys
from bs4 import BeautifulSoup  # type: ignore
import requests  # type: ignore

from clients import get_client


# Check if running in Docker (non-interactive mode)
IS_DOCKER = "RUN_DOCKER" in os.environ

# Global flag for graceful shutdown
_shutdown_requested = False

# Shutdown message constant
_SHUTDOWN_MESSAGE = "Shutdown requested, stopping fetch operation..."


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

# Config directory and file names
CONFIG_DIR_DOCKER = "/config"
CONFIG_DIR_LOCAL = "."
DB_NAME = "crc32_files.db"
EPISODES_DB_NAME = "episodes_index.db"
MISSING_CSV_FILENAME = "Ace-Pace_Missing.csv"
DB_CSV_FILENAME = "Ace-Pace_DB.csv"


def get_config_dir():
    """Get the config directory path based on Docker mode.
    Returns the config directory path, creating it if necessary."""
    if IS_DOCKER:
        config_dir = CONFIG_DIR_DOCKER
    else:
        config_dir = CONFIG_DIR_LOCAL
    
    # Ensure config directory exists
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    
    return config_dir


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
            page_link TEXT
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


def _process_fname_entry(fname_text, seen_crc32, episodes, page_link):
    """Helper to extract CRC32 from fname_text and store if valid and unique.
    Only accepts episodes with 1080p quality."""
    m = CRC32_REGEX.findall(fname_text)
    found = False
    if m and ONE_PACE_MARKER in fname_text and _is_valid_quality(fname_text):
        crc32 = m[-1].upper()
        if crc32 not in seen_crc32:
            # print(f"New CRC32 detected: {crc32} -> Title: {fname_text}")
            episodes.append((crc32, fname_text, page_link))
            seen_crc32.add(crc32)
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


def _process_torrent_page(page_link, seen_crc32, episodes):
    """Process a torrent page to extract CRC32 information from file list."""
    try:
        torrent_resp = requests.get(page_link)
        if torrent_resp.status_code != HTTP_OK:
            print(f"Failed to fetch torrent page {page_link}")
            return False
        t_soup = BeautifulSoup(torrent_resp.text, HTML_PARSER)
        filenames = _extract_filenames_from_torrent_page(t_soup)
        found = False
        for fname in filenames:
            if _process_fname_entry(str(fname), seen_crc32, episodes, page_link):
                found = True
        return found
    except (requests.RequestException, AttributeError, TypeError):
        return False


def _process_episode_row(row, seen_crc32, episodes):
    """Process a single table row to extract episode information."""
    title_link = _extract_title_link_from_row(row)
    if not title_link:
        return False
    
    title = title_link.text.strip()
    page_link = NYAA_BASE_URL + title_link["href"]
    matches = CRC32_REGEX.findall(title)
    
    if matches:
        return _process_fname_entry(title, seen_crc32, episodes, page_link)
    else:
        return _process_torrent_page(page_link, seen_crc32, episodes)


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
    Fetch all One Pace episodes from Nyaa, collecting CRC32, title, and page link.
    If CRC32 not in title, fetch the torrent page and try to extract CRC32s from file list.
    Args:
        base_url: Base URL for Nyaa search. If None, uses default without quality filter.
                  Note: Quality filtering (1080p only) is always applied regardless of URL.
    Returns: List of (crc32, title, page_link)
    """
    if base_url is None:
        base_url = f"{NYAA_BASE_URL}/?f=0&c=0_0&q=one+pace"
    
    episodes = []
    seen_crc32 = set()
    print(f"Browsing {base_url}...")

    # Get total number of pages by parsing first page's pagination controls
    soup, success = _fetch_episodes_page(base_url, 1)
    if not success:
        return episodes
    total_pages = _get_total_pages(soup)

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


def update_episodes_index_db(base_url=None):
    """Update episodes index database from Nyaa.
    Args:
        base_url: Base URL for Nyaa search. If None, uses default.
    """
    conn = init_episodes_db()
    episodes = fetch_episodes_metadata(base_url)
    c = conn.cursor()
    count = 0
    for crc32, title, page_link in episodes:
        # Check for shutdown request during processing
        if _shutdown_requested:
            print("Shutdown requested, committing partial update...")
            break
        c.execute(
            "INSERT OR REPLACE INTO episodes_index (crc32, title, page_link) VALUES (?, ?, ?)",
            (crc32, title, page_link),
        )
        count += 1
    conn.commit()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_episodes_metadata(conn, "episodes_db_last_update", now_str)
    print(f"Episodes index updated with {count} entries.")
    print(f"Last update: {now_str}")
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
        if href.startswith("magnet:"):
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
    Returns True if any episodes were found, False otherwise."""
    table = soup.find("table", class_="torrent-list")
    if not table:
        print("No table found, stopping.")
        return False

    rows = table.find_all("tr")  # type: ignore
    if not rows:
        print("No rows found, stopping.")
        return False

    found_in_page = False
    for row in rows:
        if _shutdown_requested:
            print(_SHUTDOWN_MESSAGE)
            break
        success, filename_text, should_warn = _process_crc32_row(row, crc32_to_link, crc32_to_text, crc32_to_magnet)
        if success:
            found_in_page = True
        elif should_warn and filename_text:
            print(f"Warning: No CRC32 found in title '{filename_text}'")
    
    return found_in_page


def fetch_crc32_links(base_url):
    """Fetch CRC32 links from Nyaa.si search URL.
    Only accepts episodes with 1080p quality.
    Args:
        base_url: Nyaa.si search URL
    Returns: Tuple of (crc32_to_link, crc32_to_text, crc32_to_magnet, last_checked_page)"""
    crc32_to_link = {}
    crc32_to_text = {}
    crc32_to_magnet = {}
    page = 1
    last_checked_page = 0
    
    while True:
        if _shutdown_requested:
            print(_SHUTDOWN_MESSAGE)
            break
        
        soup, success = _fetch_crc32_page(base_url, page)
        if not success:
            break
        
        found_in_page = _process_crc32_page_rows(soup, crc32_to_link, crc32_to_text, crc32_to_magnet)
        
        if _shutdown_requested or not found_in_page:
            break
        
        last_checked_page = page
        page += 1

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
        print(f"Warning: No title found for {crc32}")
        return None
    else:
        print(f"Warning: Multiple titles found for CRC32 {crc32}: {matched_titles}")
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
        return True
    
    # Calculate CRC32
    parent_folder = os.path.basename(os.path.dirname(file_path))
    file_name = os.path.basename(file_path)
    print(f"Calculating CRC32 for {parent_folder}/{file_name}...")
    
    crc32 = _calculate_file_crc32(file_path)
    if crc32 is None:
        return False  # Calculation interrupted
    
    local_crc32s.add(crc32)
    c.execute(
        "INSERT OR REPLACE INTO crc32_cache (file_path, crc32) VALUES (?, ?)",
        (normalized_path, crc32),
    )
    conn.commit()
    return True


def calculate_local_crc32(folder, conn):
    """Calculate CRC32 checksums for all video files in the given folder.
    Uses cached values from database when available.
    Args:
        folder: Folder path to scan for video files
        conn: Database connection
    Returns: Set of CRC32 checksums found in the folder."""
    local_crc32s = set()
    c = conn.cursor()
    
    for root, dirs, files in os.walk(folder):
        if _shutdown_requested:
            print("Shutdown requested, stopping file processing...")
            break
        
        for file in files:
            if _shutdown_requested:
                break
            
            ext = os.path.splitext(file)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                file_path = os.path.join(root, file)
                _process_video_file(file_path, c, conn, local_crc32s)
    
    return local_crc32s


def _build_rename_plan(entries, crc32_to_title):
    """Build a plan of files to rename based on CRC32 matches."""
    rename_plan = []
    for file_path, crc32 in entries:
        title = crc32_to_title.get(crc32)
        if not title:
            continue  # No match found in index, skip
        dir_name = os.path.dirname(file_path)
        # Sanitize title for filename (remove problematic characters)
        sanitized_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
        new_filename = f"{sanitized_title}"
        new_path = os.path.join(dir_name, new_filename)
        if os.path.abspath(file_path) != os.path.abspath(new_path):
            rename_plan.append((file_path, new_path))
    return rename_plan


def _get_rename_confirmation():
    """Get user confirmation for renaming files."""
    if IS_DOCKER:
        return "y"
    return input("Proceed with renaming? (y/n): ").strip().lower()


def _execute_rename(rename_plan, conn):
    """Execute the rename plan and update the database."""
    c = conn.cursor()
    for old, new in rename_plan:
        try:
            if os.path.exists(new):
                print(f"Cannot rename {old} to {new}: target file already exists.")
                continue
            os.rename(old, new)
            print(f"Renamed {old} to {new}")
            # Normalize paths for consistent database updates
            normalized_old = normalize_file_path(old)
            normalized_new = normalize_file_path(new)
            # Update DB with new file path
            c.execute(
                "UPDATE crc32_cache SET file_path = ? WHERE file_path = ?", (normalized_new, normalized_old)
            )
            conn.commit()
        except Exception as e:
            print(f"Failed to rename {old} to {new}: {e}")


def rename_local_files(conn):
    """Rename local files based on CRC32 matching titles from episodes index.
    Matches local video files with episodes in the database and renames them
    to match the official episode titles.
    Args:
        conn: Database connection"""
    c = conn.cursor()
    c.execute("SELECT file_path, crc32 FROM crc32_cache")
    entries = c.fetchall()
    if not entries:
        print("No entries found in local CRC32 database.")
        return

    # Load CRC32 → title from episodes_index.db
    crc32_to_title = load_crc32_to_title_from_index()
    local_crc32s = set()
    for _, crc32 in entries:
        local_crc32s.add(crc32)

    total = len(local_crc32s)
    rename_plan = _build_rename_plan(entries, crc32_to_title)

    if not rename_plan:
        print("No files to rename.")
        print(f"0/{total} files matched in index.")
        return

    print("Rename plan:")
    for old, new in rename_plan:
        print(f"{os.path.basename(old)} -> {os.path.basename(new)}")
    print(f"{len(rename_plan)}/{total} files will be renamed.")

    confirm = _get_rename_confirmation()
    if confirm != "y":
        print("Renaming aborted.")
        return

    _execute_rename(rename_plan, conn)


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


def _get_folder_from_args(args, conn, needs_folder):
    """Get folder path from arguments or prompt user."""
    folder = args.folder
    if IS_DOCKER and needs_folder:
        # In Docker mode, use /media as default folder
        folder = "/media"
        set_metadata(conn, "last_folder", folder)
        return folder
    
    if needs_folder and not folder:
        # Try to load last_folder from metadata
        last_folder = get_metadata(conn, "last_folder")
        if last_folder:
            print(f"Last used folder: {last_folder}")
            user_input = input(
                "Press Enter to use this folder, or enter a new path: "
            ).strip()
            if user_input:
                folder = user_input
            else:
                folder = last_folder
        else:
            folder = input("Enter the folder containing local video files: ").strip()
        if not folder:
            print("Error: No folder specified.")
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
    download_folder = args.download_folder or "/media"
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
    """Load magnet links from the missing CSV file."""
    missing_csv_path = get_config_path(MISSING_CSV_FILENAME)
    if not os.path.exists(missing_csv_path):
        print(f"Missing file '{missing_csv_path}' not found. Run the script first!")
        return None

    magnets = []
    with open(missing_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            magnet_link = row.get("Magnet Link", "").strip()
            if magnet_link.startswith("magnet:"):
                magnets.append(magnet_link)

    if not magnets:
        print(f"No magnet links found in '{missing_csv_path}'.")
        return None

    return magnets


def _handle_download_command(args):
    """Handle the download command."""
    # Get connection parameters based on Docker mode
    if IS_DOCKER:
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
    else:
        client = _get_client_from_args_or_env(args)
        if not client:
            print("Error: --client is required when using --download.")
            return False
        host, port, username, password, download_folder = _get_non_docker_connection_params(args)

    magnets = _load_magnet_links()
    if magnets is None:
        return False

    try:
        client_obj = get_client(client, host, port, username, password)
        print(f"Adding {len(magnets)} missing episode(s) to {client}...")
        client_obj.add_torrents(
            magnets,
            download_folder=download_folder,
            tags=args.tag,
            category=args.category,
        )
        print(f"Successfully added {len(magnets)} episode(s) to {client}.")
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


def _handle_rename_command(conn, base_url=None):
    """Handle the rename command.
    Args:
        conn: Database connection
        base_url: Base URL for Nyaa search (optional)
    """
    episodes_db_conn = init_episodes_db()
    last_ep_update = get_episodes_metadata(
        episodes_db_conn, "episodes_db_last_update"
    )
    episodes_db_conn.close()
    
    prompt = _get_rename_prompt(last_ep_update)
    
    if prompt == "y":
        update_episodes_index_db(base_url)
    print(
        "Renaming local files based on matching titles from One Pace episodes index..."
    )
    rename_local_files(conn)


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
    with open(missing_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["Title", "Page Link", "Magnet Link"])
        for crc32 in missing:
            title = crc32_to_text[crc32]
            page_link = crc32_to_link[crc32]
            magnet = crc32_to_magnet.get(crc32, "")
            writer.writerow([title, page_link, magnet])
    print(f"Missing files list saved to {missing_csv_path}")


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


def _calculate_and_find_missing(folder, conn, args, last_run):
    """Calculate local CRC32s and find missing episodes."""
    crc32_to_link, crc32_to_text, crc32_to_magnet, last_checked_page = (
        fetch_crc32_links(args.url)
    )

    print(f"Found {len(crc32_to_link)} episodes from Nyaa.")

    if last_run:
        print("Calculating new local CRC32 hashes...")
    else:
        print(
            "Calculating local CRC32 hashes - this will take a while on first run!..."
        )

    local_crc32s = calculate_local_crc32(folder, conn)
    print(f"Found {len(local_crc32s)} local CRC32 hashes.")

    missing = [crc32 for crc32 in crc32_to_link if crc32 not in local_crc32s]

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
        for crc32 in new_crc32s:
            title = crc32_to_text.get(crc32, "(Unknown Title)")
            print(f"Missing: {title}")


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

    --episodes_update       Update episodes metadata database from Nyaa
                            Fetches all One Pace episodes from Nyaa and stores their
                            CRC32, title, and page link in the episodes index database.
                            This should be run periodically to keep the database current.

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

EXAMPLES:

  # Generate missing episodes report
  python acepace.py --folder /path/to/videos

  # Update episodes database
  python acepace.py --episodes_update

  # Rename local files to match episode titles
  python acepace.py --folder /path/to/videos --rename

  # Download missing episodes to qBittorrent
  python acepace.py --download --client qbittorrent --host localhost --port 8080

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
        help="Update episodes metadata database from Nyaa.",
    )
    parser.add_argument("--host", default="localhost", help="The BitTorrent client host.")
    parser.add_argument("--port", type=int, help="The BitTorrent client port.")
    parser.add_argument("--username", help="The BitTorrent client username.")
    parser.add_argument("--password", help="The BitTorrent client password.")
    parser.add_argument("--download-folder", help="The folder to download the torrents to.")
    parser.add_argument("--tag", action="append", help="Tag to add to the torrent in qBittorrent (can be used multiple times).")
    parser.add_argument("--category", help="Category to add to the torrent in qBittorrent.")
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


def _handle_main_commands(args, conn, folder):
    """Handle main command execution."""
    if args.download:
        _handle_download_command(args)
        return

    if args.rename:
        _handle_rename_command(conn, args.url)
        return

    if not folder:
        print("Error: --folder argument is required.")
        return

    if args.db:
        export_db_to_csv(conn)
        return

    _generate_missing_episodes_report(conn, folder, args)

    # Note: To download missing episodes, use --download flag with --client


def main():
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    
    try:
        args = _parse_arguments()

        # Show detailed help if requested
        if args.help:
            _print_help()
            return

        # Only show Docker mode message once, and not for --db or --episodes_update commands
        # Also suppress for help command
        if IS_DOCKER and not args.db and not args.episodes_update and not args.help:
            print("Running in Docker mode (non-interactive)")

        if not _validate_url(args.url):
            sys.exit(1)

        # Only show episodes metadata status for main command (not for --db or --episodes_update)
        if not args.db and not args.episodes_update:
            _show_episodes_metadata_status()

        if args.episodes_update:
            update_episodes_index_db(args.url)
            return

        # Suppress messages when exporting DB (since it's automated)
        conn = init_db(suppress_messages=args.db)

        # Folder selection logic: Always prompt if folder is required but not given
        needs_folder = not args.download  # All commands except --download need folder
        folder = _get_folder_from_args(args, conn, needs_folder)
        if folder is None:
            sys.exit(1)

        _handle_main_commands(args, conn, folder)
    except KeyboardInterrupt:
        print("\nInterrupted by user, exiting gracefully...")
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
