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
- **Quality Filtering**: Only extracts episodes with 1080p quality
  - Episodes without quality markers are excluded
  - Episodes with quality other than 1080p (720p, 480p, 360p, 1440p, 2160p/4K, etc.) are excluded
  - Quality filtering is applied in both `fetch_episodes_metadata()` and `fetch_crc32_links()`
  - Filtering is case-insensitive (accepts 1080P, etc.)
- **URL Parameter Support**: Both `fetch_episodes_metadata()` and `update_episodes_index_db()` accept a `base_url` parameter
  - Allows consistent URL usage across all episode fetching functions
  - Default URL includes 1080p filter, but can be overridden
  - Quality filtering still applies regardless of URL parameters
- Builds and maintains an episodes index database (`episodes_index.db`)
- Supports both single-file and multi-file torrent structures
- Handles pagination to fetch all available episodes

### 2. Local Library Management
- Scans local directories recursively for video files (`.mkv`, `.mp4`, `.avi`)
- Calculates CRC32 checksums for local video files
- **Path Normalization**: All file paths are normalized before storage and lookup
  - Uses `normalize_file_path()` to resolve symlinks and convert to absolute paths
  - Ensures consistent path representation across different OS and environments
  - Prevents cache misses when same file is accessed via different path representations
  - Critical for consistent behavior between Python and Docker versions
- Caches CRC32 values in `crc32_files.db` to avoid recalculating
- Tracks file paths and their corresponding checksums (using normalized paths)

### 3. Missing Episode Detection
- Fetches episode list from Nyaa.si using the provided URL (default: One-Pace 1080p search)
- **Quality Filtering**: `fetch_crc32_links()` applies quality filtering via `_process_crc32_row()`
  - Only accepts episodes with 1080p quality
  - Requires "[One Pace]" marker in filename
  - Ensures consistent filtering regardless of URL parameters
- Compares local CRC32 checksums against fetched episodes (using normalized paths)
- Generates a CSV report (`Ace-Pace_Missing.csv`) listing missing episodes
- Includes title, page link, and magnet link for each missing episode
- Displays missing episode count prominently in output
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
  - `file_path` (TEXT, PRIMARY KEY): Normalized absolute path to local video file
  - `crc32` (TEXT, UNIQUE): CRC32 checksum of the file
  - Note: File paths are normalized using `normalize_file_path()` before storage
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
- Uses normalized file paths for cache lookups to ensure consistency

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
│   ├── test_missing_detection.py
│   ├── test_path_normalization.py
│   └── test_main_command.py
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
- **Config Directory**: Uses `/config` directory in Docker mode for databases and CSV files
  - Local mode uses current directory (`.`)
  - Config directory is automatically created if it doesn't exist
- **Message Suppression**: In Docker mode, suppresses informational messages for automated commands
  - "Running in Docker mode" message only shown once for main command (not for `--db` or `--episodes_update`)
  - Episodes metadata status only shown for main command (suppressed for `--db` and `--episodes_update`)
  - Database "already exists" message suppressed when `--db` flag is used
- **Entrypoint Script**: `entrypoint.sh` orchestrates Docker execution
  - Runs `--episodes_update` if `EPISODES_UPDATE=true` (with URL parameter if `NYAA_URL` is set)
  - Runs `--db` if `DB=true` (exports database to CSV)
  - **Always runs missing episodes report** (generates/updates `Ace-Pace_Missing.csv`)
  - Runs `--download` if `DOWNLOAD=true` (downloads missing episodes after report generation)
  - Always passes `--folder /media` to commands
  - Passes `NYAA_URL` parameter when set
- **Environment Variables**: Supports configuration via Docker environment variables
  - `DOWNLOAD`: Set to "true" to download missing episodes after generating report (default: not set/false)
  - `TORRENT_CLIENT`: BitTorrent client type (default: transmission)
    - Options: transmission, qbittorrent
  - `TORRENT_HOST`: Client host address (default: localhost)
  - `TORRENT_PORT`: Client port number (default: 9091 for transmission, 8080 for qbittorrent)
  - `TORRENT_USER`: Client authentication username (default: empty, not required)
  - `TORRENT_PASSWORD`: Client authentication password (default: empty, not required)
  - `NYAA_URL`: Custom Nyaa.si search URL (optional, defaults to 1080p search)
  - `EPISODES_UPDATE`: Set to "true" to update episodes index on container start (default: not set/false)
  - `DB`: Set to "true" to export database on container start (default: not set/false)
  - `RUN_DOCKER`: Flag to enable Docker mode (non-interactive)
  - `DEBUG`: Enable debug output for troubleshooting (default: `false`)
    - Set to `true`, `1`, `yes`, or `on` to enable detailed debug information
    - When enabled, shows troubleshooting info, sample CRC32s, comparison details, and processing statistics
    - Useful for diagnosing issues with missing episode detection or data processing
    - Works in both Docker and local Python execution

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
1. User runs `--episodes_update` (optionally with `--url` to specify search URL)
2. Script uses provided URL or defaults to One-Pace search (without quality filter in URL)
3. Script scrapes all pages of Nyaa.si search results
4. For each torrent, extracts CRC32 from title or file list
5. Applies quality filtering (1080p only) before storing
6. Stores CRC32, title, and page link in `episodes_index.db`
7. Updates metadata with last update timestamp
8. Note: Quality filtering is applied regardless of URL parameters

### File Renaming Workflow
1. User runs `--rename` with `--folder` (optionally with `--url` to specify search URL)
2. Script checks episodes index update status
3. Script prompts to update episodes index if outdated (skipped in Docker mode)
4. If update is needed, uses provided URL or default for `update_episodes_index_db()`
5. Script loads CRC32-to-title mapping from episodes index
6. Script matches local files by CRC32 (using normalized paths)
7. Script generates rename plan and prompts for confirmation (auto-confirms in Docker mode)
8. Script renames files and updates database with normalized paths

### Debug Mode
- **DEBUG Environment Variable**: Controls verbose troubleshooting output
  - Default: `false` (no debug output)
  - Set to `true`, `1`, `yes`, or `on` to enable
  - When enabled, provides detailed information about:
    - Episode fetching progress and page counts
    - CRC32 normalization and comparison details
    - Sample CRC32s from both Nyaa and local sources
    - File processing statistics (cached vs calculated)
    - Mapping issues and comparison mismatches
    - Intersection and difference analysis
  - Useful for diagnosing issues with missing episode detection
  - Works in both Docker and local Python execution
  - All debug output is prefixed with "DEBUG:" for easy filtering

### Docker Workflow
1. Container starts with `RUN_DOCKER` environment variable set
2. Entrypoint script (`entrypoint.sh`) orchestrates execution:
   - If `EPISODES_UPDATE=true`: Runs `--episodes_update` with URL from `NYAA_URL` (if set)
   - If `DB=true`: Runs `--db` to export database (suppresses informational messages)
   - **Always runs missing episodes report** (generates/updates `Ace-Pace_Missing.csv`)
   - If `DOWNLOAD=true`: Runs `--download` to download missing episodes
     - Uses default connection parameters if not specified:
       - Client: transmission
       - Host: localhost
       - Port: 9091 (transmission) or 8080 (qbittorrent)
     - Logs connection parameters used for download
3. Script operates in non-interactive mode (no user prompts)
4. Default folder is `/media` (always passed via `--folder` in entrypoint)
5. Config directory is `/config` (databases and CSV files stored here)
6. BitTorrent client connection parameters use defaults if not specified via environment variables
7. All user prompts automatically answered with defaults
8. Database files and CSV reports persist via volume mounts
9. Docker mode messages suppressed for automated commands (`--db`, `--episodes_update`)
10. Episodes metadata status only shown for main command
11. Missing episode count prominently displayed in output
12. Missing episodes CSV is always updated before download (if download is enabled)

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
- Duplicate detection and cleanup
- Episode metadata enrichment (thumbnails, descriptions)
- Note: Episode quality filtering (1080p only) is already implemented ✅

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
- `init_db(suppress_messages=False)`: Initializes the local CRC32 cache database
  - `suppress_messages`: If True, suppresses informational messages (useful for automated runs)
- `init_episodes_db()`: Initializes the episodes index database
- `get_config_dir()`: Gets config directory path based on Docker mode (`/config` in Docker, `.` locally)
- `get_config_path(filename)`: Gets full path to a config file in the appropriate config directory
- `normalize_file_path(file_path)`: Normalizes file path for consistent storage and lookup
  - Resolves symlinks and converts to absolute path
  - Ensures same file always maps to same path string regardless of OS/environment
- `get_metadata(conn, key)`: Retrieves metadata value from database
- `set_metadata(conn, key, value)`: Stores metadata value in database
- `get_episodes_metadata(conn, key)`: Retrieves episodes database metadata
- `set_episodes_metadata(conn, key, value)`: Stores episodes database metadata
- `fetch_episodes_metadata(base_url=None)`: Fetches episodes from Nyaa.si
  - `base_url`: Optional Nyaa.si search URL (defaults to One-Pace search without quality filter)
  - Quality filtering (1080p only) is always applied regardless of URL
- `update_episodes_index_db(base_url=None)`: Updates the episodes index database
  - `base_url`: Optional Nyaa.si search URL (passed to `fetch_episodes_metadata()`)
- `fetch_crc32_links(base_url)`: Fetches CRC32 links from a Nyaa.si URL
  - Applies quality filtering (1080p only) via `_process_crc32_row()`
- `fetch_title_by_crc32(crc32)`: Searches for a title by CRC32
- `calculate_local_crc32(folder, conn)`: Calculates CRC32 for local files
  - Uses normalized paths for database storage and lookup
- `rename_local_files(conn)`: Renames local files based on episodes index
  - Uses normalized paths when updating database after renaming
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
- `_is_valid_quality(fname_text)`: Checks if filename has valid quality (1080p only)
- `_validate_url(url)`: Validates URL points to valid Nyaa domain

**Command handlers** (`_handle_*`): Handle specific command-line operations
- `_handle_download_command(args)`: Handles the `--download` command
- `_handle_rename_command(conn, base_url=None)`: Handles the `--rename` command
  - `base_url`: Optional URL parameter passed to `update_episodes_index_db()` if update is needed
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
4. **File paths** - Always use `normalize_file_path()` before storing/querying file paths in database
   - Ensures consistent path representation across different OS and environments
   - Critical for consistent behavior between Python and Docker versions
   - Resolves symlinks and converts to absolute paths
5. **User interaction** - Some operations require user confirmation (renaming, downloads), but are auto-confirmed in Docker mode
6. **Client abstraction** - New BitTorrent clients should implement the `Client` interface from `clients.py`
7. **Error tolerance** - The tool should continue processing even if individual items fail
8. **Performance** - CRC32 calculation can be slow; caching is essential (uses normalized paths for cache keys)
9. **Web scraping** - Be respectful with rate limiting and error handling
10. **File naming** - Sanitize filenames to be filesystem-safe across platforms
11. **Docker mode** - Check `IS_DOCKER` flag (from `RUN_DOCKER` env var) to determine if running in Docker
    - Suppress informational messages for automated commands (`--db`, `--episodes_update`)
    - Use `/config` directory for databases and CSV files in Docker mode
    - Use `/media` as default folder in Docker mode
12. **Function naming** - Follow the naming conventions in `NAMING_CONVENTIONS.md` when adding new helper functions
13. **Code complexity** - Maintain cognitive complexity ≤ 15 per function (refactoring completed)
14. **Testing** - Comprehensive test suite exists in `tests/` directory (100+ tests covering all features)
15. **Environment variables** - In Docker mode, prefer environment variables over CLI args for configuration
16. **URL parameter consistency** - Both `fetch_episodes_metadata()` and `fetch_crc32_links()` accept URL parameters
    - Always pass `args.url` to ensure consistent URL usage across functions
    - Quality filtering is applied regardless of URL parameters
17. **Quality filtering** - Applied in both `fetch_episodes_metadata()` and `fetch_crc32_links()` via `_is_valid_quality()`
    - Only accepts 1080p episodes
    - Requires "[One Pace]" marker in filename
    - Ensures consistent filtering regardless of URL search parameters
18. **Config directory** - Use `get_config_dir()` and `get_config_path()` for consistent file location handling
    - Returns `/config` in Docker mode, `.` in local mode
    - Automatically creates directory if it doesn't exist
19. **Message suppression** - Use `suppress_messages=True` in `init_db()` for automated runs
    - Prevents "Database already exists" message when running `--db` in Docker
20. **Docker download logic** - Use `DOWNLOAD=true` environment variable to enable downloads (not `TORRENT_CLIENT` presence)
    - Missing episodes CSV is always generated/updated before download (if download enabled)
    - Download happens as a separate step after report generation
21. **Default connection values** - In Docker mode, use defaults if not specified via environment variables
    - Client: transmission
    - Host: localhost
    - Port: 9091 (transmission) or 8080 (qbittorrent)
22. **Download logging** - Log connection parameters used for download in Docker mode for transparency

23. **Debug mode** - Use `DEBUG` environment variable to control troubleshooting output
    - Defaults to `false` (no debug output)
    - Set to `true`, `1`, `yes`, or `on` to enable
    - All debug output uses `debug_print()` function which checks `DEBUG_MODE` flag
    - Debug output includes troubleshooting info, sample data, processing statistics, and comparison details
    - Useful for diagnosing issues without cluttering normal output
