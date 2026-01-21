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
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker Compose configuration
├── entrypoint.sh           # Docker entrypoint script
├── spec.md                 # This specification document
├── NAMING_CONVENTIONS.md   # Function naming conventions documentation
├── pytest.ini             # Pytest configuration
├── tests/                  # Test suite
│   ├── conftest.py
│   ├── test_clients.py
│   ├── test_crc32.py
│   ├── test_database.py
│   ├── test_episodes.py
│   ├── test_file_operations.py
│   └── test_missing_detection.py
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
- `pytest` (>=7.0.0): Testing framework
- `pytest-mock` (>=3.10.0): Mocking utilities for tests
- Standard library: `sqlite3`, `argparse`, `csv`, `datetime`, `os`, `re`, `zlib`, `getpass`, `time`, `abc`

### External Services
- **Nyaa.si**: Torrent tracker for One-Pace episodes
  - Base URL: `https://nyaa.si`
  - Search endpoint: `/?f=0&c=0_0&q=one+pace&o=asc`
  - Supports pagination via `&p=<page_number>`
- **BitTorrent Clients**:
  - Transmission (RPC API on port 9091 by default)
  - qBittorrent (Web API on port 8080 by default)

### Docker Support
- **Docker Mode**: Detected via `RUN_DOCKER` environment variable
- **Non-Interactive Operation**: In Docker mode, skips user prompts and uses defaults
- **Default Folder**: Uses `/media` as default folder in Docker mode
- **Environment Variables**: Supports configuration via Docker environment variables
  - `TORRENT_CLIENT`: BitTorrent client type (transmission/qbittorrent)
  - `TORRENT_HOST`: Client host address
  - `TORRENT_PORT`: Client port number
  - `TORRENT_USER`: Client authentication username
  - `TORRENT_PASSWORD`: Client authentication password
  - `RUN_DOCKER`: Flag to enable Docker mode (non-interactive)

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
2. Script checks episodes index update status
3. Script prompts to update episodes index if outdated (skipped in Docker mode)
4. Script loads CRC32-to-title mapping from episodes index
5. Script matches local files by CRC32
6. Script generates rename plan and prompts for confirmation (auto-confirms in Docker mode)
7. Script renames files and updates database

### Docker Workflow
1. Container starts with `RUN_DOCKER` environment variable set
2. Script operates in non-interactive mode (no user prompts)
3. Default folder is `/media` (configurable via volume mount)
4. BitTorrent client connection parameters read from environment variables
5. All user prompts automatically answered with defaults
6. Database files and CSV reports persist via volume mounts

## Integration Points

### BitTorrent Client Abstraction
- Abstract base class `Client` (in `clients.py`) defines interface using `abc.ABC`
- Concrete implementations: `QBittorrentClient`, `TransmissionClient`
- Factory function `get_client(client_name, host, port, username, password)` instantiates appropriate client
- Methods: `add_torrents(magnets, download_folder, tags, category)`
- **qBittorrentClient**:
  - Uses `qbittorrentapi` library for API access
  - Checks for existing torrents by info hash to prevent duplicates
  - Supports tags and categories
  - Adds tags to existing torrents if they already exist
- **TransmissionClient**:
  - Uses Transmission RPC API via HTTP requests
  - Handles session ID management for authentication
  - Does not support tags/categories (warns if provided)
  - Uses `requests` library for API calls

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

**Note**: In Docker mode (when `RUN_DOCKER` environment variable is set), user prompts are automatically answered with defaults to enable non-interactive operation.

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

## Refactoring History

### Code Refactoring (Completed)
The codebase underwent significant refactoring to reduce cognitive complexity and improve maintainability:

- **Function Decomposition**: Large functions were broken down into smaller, focused helper functions
- **Naming Conventions**: Established consistent naming patterns for helper functions (see `NAMING_CONVENTIONS.md`)
- **Separation of Concerns**: Clear separation between public API and private implementation details
- **Docker Support**: Added Docker mode with non-interactive operation support
- **Environment Variable Support**: Added support for configuration via environment variables in Docker mode
- **Connection Parameter Abstraction**: Separated Docker and non-Docker connection parameter handling
- **Workflow Functions**: Created dedicated workflow functions for complex multi-step operations
- **Error Handling**: Improved error handling with better separation of concerns

All helper functions follow the naming convention documented in `NAMING_CONVENTIONS.md`, making the codebase more maintainable and easier to understand.

## Code Architecture

### Function Organization
The codebase follows a modular structure with clear separation of concerns:

#### Public API Functions
- `main()`: Entry point for the application
- `init_db()`: Initializes the local CRC32 cache database
- `init_episodes_db()`: Initializes the episodes index database
- `get_metadata(conn, key)`: Retrieves metadata value from database
- `set_metadata(conn, key, value)`: Stores metadata value in database
- `get_episodes_metadata(conn, key)`: Retrieves episodes database metadata
- `set_episodes_metadata(conn, key, value)`: Stores episodes database metadata
- `fetch_episodes_metadata()`: Fetches episodes from Nyaa.si
- `update_episodes_index_db()`: Updates the episodes index database
- `fetch_crc32_links(base_url)`: Fetches CRC32 links from a Nyaa.si URL
- `fetch_title_by_crc32(crc32)`: Searches for a title by CRC32
- `calculate_local_crc32(folder, conn)`: Calculates CRC32 for local files
- `rename_local_files(conn)`: Renames local files based on episodes index
- `export_db_to_csv(conn)`: Exports database to CSV
- `load_crc32_to_title_from_index()`: Loads CRC32-to-title mapping

#### Private Helper Functions (prefixed with `_`)
Helper functions are prefixed with `_` to indicate they are internal implementation details. See `NAMING_CONVENTIONS.md` for detailed documentation.

**Extraction functions** (`_extract_*`): Extract data from HTML/structures
- `_extract_title_link_from_row(row)`: Extracts title link from table row
- `_extract_filenames_from_folder_structure(filelist_div)`: Extracts filenames from folder structure
- `_extract_filenames_from_torrent_page(torrent_soup)`: Extracts filenames from torrent page
- `_extract_matching_titles_from_rows(rows, crc32)`: Extracts titles matching CRC32

**Processing functions** (`_process_*`): Process data structures
- `_process_fname_entry(fname_text, ...)`: Processes filename entry to extract CRC32
- `_process_torrent_page(page_link, ...)`: Processes torrent page to extract CRC32
- `_process_episode_row(row, ...)`: Processes table row to extract episode info
- `_process_crc32_row(row, ...)`: Processes row to extract CRC32 for missing episodes

**Validation functions** (`_is_*`, `_validate_*`): Validate inputs/data
- `_is_valid_quality(fname_text)`: Checks if filename has valid quality (1080p/720p)
- `_validate_url(url)`: Validates URL points to valid Nyaa domain

**Command handlers** (`_handle_*`): Handle specific command-line operations
- `_handle_download_command(args)`: Handles the `--download` command
- `_handle_rename_command(conn)`: Handles the `--rename` command
- `_handle_main_commands(args, conn, folder)`: Routes and handles main commands

**Getter functions** (`_get_*`): Retrieve or compute values
- `_get_total_pages(soup)`: Extracts total pages from pagination
- `_get_folder_from_args(args, conn, needs_folder)`: Gets folder from args or prompts
- `_get_client_from_args_or_env(args)`: Gets client type from args or env vars
- `_get_default_port(client)`: Gets default port for client
- `_get_docker_connection_params(args)`: Gets connection params from Docker env vars
- `_get_non_docker_connection_params(args)`: Gets connection params from CLI args
- `_get_rename_confirmation()`: Gets user confirmation for renaming
- `_get_rename_prompt(last_ep_update)`: Gets prompt for updating episodes DB

**Load/Save functions** (`_load_*`, `_save_*`): Load or save data
- `_load_magnet_links()`: Loads magnet links from missing CSV
- `_load_old_missing_crc32s()`: Loads CRC32s from previous missing CSV
- `_save_missing_episodes_csv(...)`: Saves missing episodes to CSV

**Print/Report functions** (`_print_*`, `_report_*`, `_show_*`): Display information
- `_print_report_header(conn, folder, args)`: Prints report header
- `_report_new_missing_episodes(missing, crc32_to_text)`: Reports new missing episodes
- `_show_episodes_metadata_status()`: Shows episodes metadata update status

**Workflow functions** (`_generate_*`, `_calculate_*`): Orchestrate multi-step workflows
- `_generate_missing_episodes_report(conn, folder, args)`: Generates missing episodes report
- `_calculate_and_find_missing(folder, conn, args, last_run)`: Calculates CRC32s and finds missing

**Utility functions** (`_parse_*`, `_count_*`, `_build_*`, `_execute_*`): General utilities
- `_parse_arguments()`: Parses command-line arguments
- `_count_video_files(folder, conn)`: Counts video files and recorded files
- `_build_rename_plan(entries, crc32_to_title)`: Builds plan of files to rename
- `_execute_rename(rename_plan, conn)`: Executes rename plan and updates DB

This naming convention improves code readability and makes the public API clear. All helper functions follow consistent patterns documented in `NAMING_CONVENTIONS.md`.

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
5. **User interaction** - Some operations require user confirmation (renaming, downloads), but are auto-confirmed in Docker mode
6. **Client abstraction** - New BitTorrent clients should implement the `Client` interface from `clients.py`
7. **Error tolerance** - The tool should continue processing even if individual items fail
8. **Performance** - CRC32 calculation can be slow; caching is essential
9. **Web scraping** - Be respectful with rate limiting and error handling
10. **File naming** - Sanitize filenames to be filesystem-safe across platforms
11. **Docker mode** - Check `IS_DOCKER` flag (from `RUN_DOCKER` env var) to determine if running in Docker
12. **Function naming** - Follow the naming conventions in `NAMING_CONVENTIONS.md` when adding new helper functions
13. **Code complexity** - Maintain cognitive complexity ≤ 15 per function (refactoring completed)
14. **Testing** - Comprehensive test suite exists in `tests/` directory
15. **Environment variables** - In Docker mode, prefer environment variables over CLI args for configuration
