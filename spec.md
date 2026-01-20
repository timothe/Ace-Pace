# Ace-Pace Project Specification

## Project Overview

**Ace-Pace** is a Python-based tool designed to help users manage and organize their One-Pace anime library. One-Pace is a fan project that edits the One Piece anime to remove filler content and improve pacing. Ace-Pace automates the process of:

- Identifying which One-Pace episodes are already in the user's local library
- Detecting missing episodes
- Automatically downloading missing episodes via BitTorrent clients
- Renaming local files to match official One-Pace naming conventions
- Maintaining a database of episode metadata and file checksums

## Core Functionality

### 1. Episode Discovery and Indexing
- Scrapes Nyaa.si torrent tracker for One-Pace episodes
- Extracts CRC32 checksums from episode filenames or torrent file lists
- **Quality Filtering**: Only extracts episodes with 1080p quality, or 720p as fallback
  - Episodes without quality markers are excluded
  - Episodes with quality lower than 720p (480p, 360p, etc.) are excluded
  - Episodes with quality higher than 1080p (1440p, 2160p/4K, etc.) are excluded
- Builds and maintains an episodes index database (`episodes_index.db`)
- Supports both single-file and multi-file torrent structures
- Handles pagination to fetch all available episodes

### 2. Local Library Management
- Scans local directories recursively for video files (`.mkv`, `.mp4`, `.avi`)
- Calculates CRC32 checksums for local video files
- Caches CRC32 values in `crc32_files.db` to avoid recalculating
- Tracks file paths and their corresponding checksums

### 3. Missing Episode Detection
- Fetches episode list from Nyaa.si using the provided URL (default: One-Pace 1080p search)
- Compares local CRC32 checksums against fetched episodes
- Generates a CSV report (`Ace-Pace_Missing.csv`) listing missing episodes
- Includes title, page link, and magnet link for each missing episode
- Tracks new missing episodes since last export by comparing with previous CSV
- Note: Uses `fetch_crc32_links()` for real-time fetching, not the cached episodes index

### 4. Automated Downloading
- Integrates with BitTorrent clients (Transmission, qBittorrent)
- Adds missing episodes to client via magnet links
- Supports custom download folders, tags, and categories
- Prevents duplicate torrent additions by checking existing torrents

### 5. File Renaming
- Matches local files to episodes index by CRC32
- Renames files to match official One-Pace naming conventions
- Sanitizes filenames to remove problematic characters
- Updates database with new file paths after renaming

## Technical Architecture

### Databases

#### `crc32_files.db`
- **Table: `crc32_cache`**
  - `file_path` (TEXT, PRIMARY KEY): Full path to local video file
  - `crc32` (TEXT, UNIQUE): CRC32 checksum of the file
- **Table: `metadata`**
  - `key` (TEXT, PRIMARY KEY): Metadata key
  - `value` (TEXT): Metadata value
  - Stores: `last_folder`, `last_run`, `last_checked_page`, `last_db_export`, `last_missing_export`

#### `episodes_index.db`
- **Table: `episodes_index`**
  - `crc32` (TEXT, PRIMARY KEY): CRC32 checksum from episode
  - `title` (TEXT): Episode title/filename
  - `page_link` (TEXT): URL to Nyaa.si torrent page
- **Table: `metadata`**
  - `key` (TEXT, PRIMARY KEY): Metadata key
  - `value` (TEXT): Metadata value
  - Stores: `episodes_db_last_update`

### Key Algorithms

#### CRC32 Calculation
- Reads video files in 8KB chunks
- Uses Python's `zlib.crc32()` for incremental calculation
- Formats result as uppercase 8-character hexadecimal string
- Caches results to avoid redundant calculations

#### CRC32 Extraction from Filenames
- Uses regex pattern: `\[([A-Fa-f0-9]{8})\]`
- Extracts CRC32 from square brackets in filenames
- Takes the last match if multiple CRC32s are present
- Validates that filename contains "[One Pace]" marker

#### Web Scraping
- Uses BeautifulSoup4 for HTML parsing
- Handles Nyaa.si pagination by detecting max page number
- Extracts torrent metadata from listing pages
- Falls back to individual torrent pages when CRC32 not in title
- Processes both folder-based and single-file torrent structures

### File Structure

```
Ace-Pace/
├── acepace.py              # Main application entry point
├── clients.py              # BitTorrent client abstraction layer
├── requirements.txt        # Python dependencies
├── docker-compose.yml      # Docker configuration (if applicable)
├── spec.md                 # This specification document
├── crc32_files.db          # Local file checksum database (generated)
├── episodes_index.db       # Episodes metadata database (generated)
├── Ace-Pace_Missing.csv    # Missing episodes report (generated)
└── Ace-Pace_DB.csv         # Database export (generated)
```

## Dependencies

### Python Packages
- `requests`: HTTP requests for web scraping and API calls
- `beautifulsoup4`: HTML parsing for Nyaa.si scraping
- `qbittorrent-api`: qBittorrent client integration
- Standard library: `sqlite3`, `argparse`, `csv`, `datetime`, `os`, `re`, `zlib`, `getpass`, `time`, `abc`

### External Services
- **Nyaa.si**: Torrent tracker for One-Pace episodes
  - Base URL: `https://nyaa.si`
  - Search endpoint: `/?f=0&c=0_0&q=one+pace&o=asc`
  - Supports pagination via `&p=<page_number>`
- **BitTorrent Clients**:
  - Transmission (RPC API on port 9091 by default)
  - qBittorrent (Web API on port 8080 by default)

## Command-Line Interface

### Main Arguments
- `--folder <path>`: Local video library directory
- `--url <url>`: Nyaa.si search URL (default: One-Pace 1080p search)
- `--db`: Export database to CSV

### Download Arguments
- `--client {transmission,qbittorrent}`: BitTorrent client to use
- `--download`: Enable automatic downloading
- `--host <host>`: Client host (default: localhost)
- `--port <port>`: Client port
- `--username <username>`: Client authentication username
- `--password <password>`: Client authentication password
- `--download-folder <path>`: Target download directory
- `--tag <tag>`: Tag(s) for qBittorrent (repeatable)
- `--category <category>`: Category for qBittorrent

### Utility Arguments
- `--rename`: Rename local files based on episodes index
- `--episodes_update`: Update episodes metadata database from Nyaa

## Workflow

### Standard Workflow
1. User runs script with `--folder` to scan local library
2. Script validates URL and shows episodes metadata status
3. Script calculates/retrieves CRC32 checksums for local files
4. Script fetches episode list from Nyaa.si using `fetch_crc32_links()`
5. Script compares local CRC32s against fetched episodes
6. Script generates `Ace-Pace_Missing.csv` with missing episodes
7. Script reports new missing episodes since last export
8. User optionally runs `--download --client <client>` to add missing episodes to BitTorrent client

### Episodes Index Update Workflow
1. User runs `--episodes_update` to refresh episodes database
2. Script scrapes all pages of Nyaa.si One-Pace search results
3. For each torrent, extracts CRC32 from title or file list
4. Stores CRC32, title, and page link in `episodes_index.db`
5. Updates metadata with last update timestamp

### File Renaming Workflow
1. User runs `--rename` with `--folder`
2. Script prompts to update episodes index if outdated
3. Script loads CRC32-to-title mapping from episodes index
4. Script matches local files by CRC32
5. Script generates rename plan and prompts for confirmation
6. Script renames files and updates database

## Integration Points

### BitTorrent Client Abstraction
- Abstract base class `Client` defines interface
- Concrete implementations: `QBittorrentClient`, `TransmissionClient`
- Factory function `get_client()` instantiates appropriate client
- Methods: `add_torrents(magnets, download_folder, tags, category)`

### Database Management
- SQLite databases for persistence
- Connection management via context or explicit close
- Metadata storage for tracking state and timestamps
- Transaction support for atomic operations

## Error Handling

### Network Errors
- HTTP request failures are caught and logged
- Continues processing remaining items on individual failures
- Rate limiting via `time.sleep(0.2)` between requests

### File System Errors
- Checks for file existence before operations
- Handles permission errors gracefully
- Validates file paths and extensions

### Database Errors
- Uses `INSERT OR REPLACE` for idempotent operations
- Handles connection failures
- Validates data before insertion

## Configuration and State

### Persistent State
- Last used folder path
- Last run timestamp
- Last database export timestamp
- Last missing export timestamp
- Last episodes index update timestamp
- Last checked page number

### User Prompts
- Folder selection (with last folder suggestion)
- Episodes index update confirmation (when using `--rename`)
- File renaming confirmation

## Future Considerations

### Potential Enhancements
- Support for additional BitTorrent clients
- Configuration file for default settings
- Web UI for easier interaction
- Automatic episode index updates on schedule
- Support for additional video formats
- Integration with media server APIs (Plex, Jellyfin)
- Episode quality filtering (720p, 1080p, etc.)
- Duplicate detection and cleanup
- Episode metadata enrichment (thumbnails, descriptions)

### Technical Improvements
- Async/await for concurrent web scraping
- Better error recovery and retry logic
- Unit tests and integration tests (✅ implemented)
- Logging framework instead of print statements
- Type hints for better code documentation
- Configuration validation
- Better handling of edge cases in filename parsing
- Code refactoring for reduced cognitive complexity (✅ completed)

## Code Architecture

### Function Organization
The codebase follows a modular structure with clear separation of concerns:

#### Public API Functions
- `main()`: Entry point for the application
- `fetch_episodes_metadata()`: Fetches episodes from Nyaa.si
- `update_episodes_index_db()`: Updates the episodes index database
- `fetch_crc32_links()`: Fetches CRC32 links from a Nyaa.si URL
- `fetch_title_by_crc32()`: Searches for a title by CRC32
- `calculate_local_crc32()`: Calculates CRC32 for local files
- `rename_local_files()`: Renames local files based on episodes index
- `export_db_to_csv()`: Exports database to CSV
- `load_crc32_to_title_from_index()`: Loads CRC32-to-title mapping

#### Private Helper Functions (prefixed with `_`)
Helper functions are prefixed with `_` to indicate they are internal implementation details:

- **Extraction functions**: `_extract_*` - Extract data from HTML/structures
- **Processing functions**: `_process_*` - Process data structures
- **Validation functions**: `_is_*`, `_validate_*` - Validate inputs/data
- **Command handlers**: `_handle_*` - Handle specific command-line operations
- **Utility functions**: `_get_*`, `_load_*`, `_save_*`, `_print_*`, `_report_*` - Utility operations
- **Workflow functions**: `_generate_*`, `_calculate_*` - Orchestrate multi-step workflows

This naming convention improves code readability and makes the public API clear.

## Development Guidelines

### Code Style
- Follow PEP 8 Python style guide
- Use descriptive variable names
- Add docstrings for functions
- Keep functions focused and single-purpose
- Use `_` prefix for private/internal helper functions
- Maintain cognitive complexity ≤ 15 per function

### Database Schema
- Use SQLite for simplicity
- Maintain backward compatibility when possible
- Document schema changes

### API Compatibility
- Maintain backward compatibility with command-line arguments
- Handle missing optional arguments gracefully
- Provide clear error messages

## Notes for AI Agents

When working on this project:

1. **CRC32 is the primary identifier** - All episode matching relies on CRC32 checksums
2. **Nyaa.si structure** - Understand the HTML structure of Nyaa.si pages for scraping
3. **Database state** - Always consider existing database state when making changes
4. **File paths** - Handle both absolute and relative paths correctly
5. **User interaction** - Some operations require user confirmation (renaming, downloads)
6. **Client abstraction** - New BitTorrent clients should implement the `Client` interface
7. **Error tolerance** - The tool should continue processing even if individual items fail
8. **Performance** - CRC32 calculation can be slow; caching is essential
9. **Web scraping** - Be respectful with rate limiting and error handling
10. **File naming** - Sanitize filenames to be filesystem-safe across platforms
