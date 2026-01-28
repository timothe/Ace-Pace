# Ace-Pace Project Rules

This file contains the development rules, guidelines, and technical reference for the Ace-Pace project. These rules should be followed by all AI agents working on this codebase.

## Core Workflow Requirements

When working on this project, you MUST:

1. **Always update tests when making changes**
   - Update existing tests if functionality changes
   - Add new tests for new features
   - **Always run tests and verify they pass** before completing work
   - Fix any failing tests
   - Run: `pytest` with coverage before completing work

2. **Always check for linter and SonarQube problems**
   - Run linter checks and fix any issues
   - Check SonarQube for code quality issues
   - Fix all identified problems

3. **Update documentation when appropriate**
   - Review README.md after significant changes
   - Update function documentation when signatures change
   - Keep technical documentation accurate

## Git Workflow Rules

**CRITICAL: Follow these git rules strictly:**

- **ABSOLUTELY NEVER run destructive git operations** (e.g., `git reset --hard`, `rm`, `git checkout`/`git restore` to an older commit) unless the user gives an explicit, written instruction. Treat these commands as catastrophic; if you are even slightly unsure, stop and ask before touching them.

- **Never use `git restore`** (or similar commands) to revert files you didn't author—coordinate with other agents instead so their in-progress work stays intact.

- **Always double-check git status** before any commit

- **Keep commits atomic**: commit only the files you touched and list each path explicitly
  - For tracked files: `git commit -m "<scoped message>" -- path/to/file1 path/to/file2`
  - For brand-new files: `git restore --staged :/ && git add "path/to/file1" "path/to/file2" && git commit -m "<scoped message>" -- path/to/file1 path/to/file2`

- **Quote any git paths** containing brackets or parentheses (e.g., `src/app/[candidate]/**`) when staging or committing so the shell does not treat them as globs or subshells.

- **When running `git rebase`**, avoid opening editors—export `GIT_EDITOR=:` and `GIT_SEQUENCE_EDITOR=:` (or pass `--no-edit`) so the default messages are used automatically.

- **Never amend commits** unless you have explicit written approval in the task thread.

- **Delete unused or obsolete files** when your changes make them irrelevant (refactors, feature removals, etc.), and revert files only when the change is yours or explicitly requested.

- **Before attempting to delete a file** to resolve a local type/lint failure, stop and ask the user. Other agents are often editing adjacent files; deleting their work to silence an error is never acceptable without explicit approval.

- **NEVER edit `.env`** or any environment variable files—only the user may change them.

- **Coordinate with other agents** before removing their in-progress edits—don't revert or delete work you didn't author unless everyone agrees.

- **Moving/renaming and restoring files** is allowed.

## Code Quality Standards

- Follow PEP 8 Python style guide
- Maintain cognitive complexity ≤ 15 per function
- Use descriptive variable names
- Add docstrings for functions
- Keep functions focused and single-purpose
- Use `_` prefix for private/internal helper functions
- Comprehensive test suite exists in `tests/` directory (100+ tests)
- Ensure all tests pass before completing work

## Project Overview

**Ace-Pace** is a Python-based tool designed to help users manage and organize their One-Pace anime library. It automates:
- Identifying which One-Pace episodes are already in the user's local library
- Detecting missing episodes
- Automatically downloading missing episodes via BitTorrent clients
- Renaming local files to match official One-Pace naming conventions
- Maintaining a database of episode metadata and file checksums

## Core Functionality

### Episode Discovery and Indexing
- Scrapes Nyaa.si torrent tracker for One-Pace episodes
- Extracts CRC32 checksums from episode filenames or torrent file lists
- **Quality Filtering**: Only extracts episodes with 1080p quality
  - Episodes without quality markers are excluded
  - Episodes with quality other than 1080p are excluded
  - Quality filtering is applied in both `fetch_episodes_metadata()` and `fetch_crc32_links()`
  - Filtering is case-insensitive (accepts 1080P, etc.)
- **URL Parameter Support**: Both `fetch_episodes_metadata()` and `update_episodes_index_db()` accept a `base_url` parameter
  - Quality filtering still applies regardless of URL parameters
- Builds and maintains an episodes index database (`episodes_index.db`)
- Supports both single-file and multi-file torrent structures
- Handles pagination to fetch all available episodes

### Local Library Management
- Scans local directories recursively for video files (`.mkv`, `.mp4`, `.avi`)
- Calculates CRC32 checksums for local video files
- **Path Normalization**: All file paths are normalized before storage and lookup
  - Uses `normalize_file_path()` to resolve symlinks and convert to absolute paths
  - Ensures consistent path representation across different OS and environments
  - Prevents cache misses when same file is accessed via different path representations
  - **CRITICAL**: Always use `normalize_file_path()` before storing/querying file paths in database
- Caches CRC32 values in `crc32_files.db` to avoid recalculating
- Tracks file paths and their corresponding checksums (using normalized paths)

### Missing Episode Detection
- Fetches episode list from Nyaa.si using the provided URL (default: One-Pace 1080p search)
- **Quality Filtering**: `fetch_crc32_links()` applies quality filtering via `_process_crc32_row()`
  - Only accepts episodes with 1080p quality
  - Requires "[One Pace]" marker in filename
- Compares local CRC32 checksums against fetched episodes (using normalized paths)
- Generates a CSV report (`Ace-Pace_Missing.csv`) listing missing episodes
- Uses `fetch_crc32_links()` for real-time fetching, not the cached episodes index

### Automated Downloading
- Integrates with BitTorrent clients (Transmission, qBittorrent)
- Adds missing episodes to client via magnet links
- Supports custom download folders, tags, and categories
- Prevents duplicate torrent additions by checking existing torrents

### File Renaming
- Matches local files to episodes index by CRC32
- Renames files to match official One-Pace naming conventions
- Sanitizes filenames to remove problematic characters
- Updates database with new file paths after renaming (using normalized paths)

## Technical Architecture

### Databases

#### `crc32_files.db`
- **Table: `crc32_cache`**
  - `file_path` (TEXT, PRIMARY KEY): Normalized absolute path to local video file
  - `crc32` (TEXT, UNIQUE): CRC32 checksum of the file
  - **Note**: File paths are normalized using `normalize_file_path()` before storage
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

## Key Public API Functions

- `main()`: Entry point for the application
- `init_db(suppress_messages=False)`: Initializes the local CRC32 cache database
- `init_episodes_db()`: Initializes the episodes index database
- `get_config_dir()`: Gets config directory path based on Docker mode (`/config` in Docker, `.` locally)
- `get_config_path(filename)`: Gets full path to a config file in the appropriate config directory
- `normalize_file_path(file_path)`: Normalizes file path for consistent storage and lookup
  - **CRITICAL**: Always use this before storing/querying file paths in database
- `get_metadata(conn, key)`: Retrieves metadata value from database
- `set_metadata(conn, key, value)`: Stores metadata value in database
- `get_episodes_metadata(conn, key)`: Retrieves episodes database metadata
- `set_episodes_metadata(conn, key, value)`: Stores episodes database metadata
- `fetch_episodes_metadata(base_url=None)`: Fetches episodes from Nyaa.si
  - `base_url`: Optional Nyaa.si search URL (defaults to One-Pace search without quality filter)
  - Quality filtering (1080p only) is always applied regardless of URL
- `update_episodes_index_db(base_url=None, force_update=False)`: Updates the episodes index database
  - `base_url`: Optional Nyaa.si search URL (passed to `fetch_episodes_metadata()`)
  - `force_update`: If True, force update even if recently updated. If False, skip if updated within last 10 minutes
- `fetch_crc32_links(base_url)`: Fetches CRC32 links from a Nyaa.si URL
  - Applies quality filtering (1080p only) via `_process_crc32_row()`
- `fetch_title_by_crc32(crc32)`: Searches for a title by CRC32
- `calculate_local_crc32(folder, conn)`: Calculates CRC32 for local files
  - Uses normalized paths for database storage and lookup
- `rename_local_files(conn)`: Renames local files based on episodes index
  - Uses normalized paths when updating database after renaming
- `export_db_to_csv(conn)`: Exports database to CSV
- `load_crc32_to_title_from_index()`: Loads CRC32-to-title mapping

## Private Helper Functions

Helper functions are prefixed with `_` to indicate they are internal implementation details.

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

## Docker Support

- **Docker Mode**: Detected via `RUN_DOCKER` environment variable
- **Non-Interactive Operation**: In Docker mode, skips user prompts and uses defaults
- **Default Folder**: Uses `/media` as default folder in Docker mode
- **Config Directory**: Uses `/config` directory in Docker mode for databases and CSV files
  - Local mode uses current directory (`.`)
  - Config directory is automatically created if it doesn't exist
- **Message Suppression**: In Docker mode, suppresses informational messages for automated commands
- **Environment Variables**: Supports configuration via Docker environment variables
  - `DOWNLOAD`: Set to "true" to download missing episodes after generating report
  - `TORRENT_CLIENT`: BitTorrent client type (default: transmission)
  - `TORRENT_HOST`: Client host address (default: localhost)
  - `TORRENT_PORT`: Client port number (default: 9091 for transmission, 8080 for qBittorrent)
  - `TORRENT_USER`: Client authentication username (optional)
  - `TORRENT_PASSWORD`: Client authentication password (optional)
  - `NYAA_URL`: Custom Nyaa.si search URL (optional, defaults to 1080p search)
  - `EPISODES_UPDATE`: Set to "true" to update episodes index on container start
  - `DB`: Set to "true" to export database on container start
  - `RUN_DOCKER`: Flag to enable Docker mode (non-interactive)
  - `DEBUG`: Enable debug output (set to `true`, `1`, `yes`, or `on`)

## Critical Implementation Notes

1. **CRC32 is the primary identifier** - All episode matching relies on CRC32 checksums
2. **Always use `normalize_file_path()`** before storing/querying file paths in database
   - Ensures consistent path representation across different OS and environments
   - Critical for consistent behavior between Python and Docker versions
   - Resolves symlinks and converts to absolute paths
3. **Quality filtering (1080p only)** is always applied regardless of URL parameters
   - Applied in both `fetch_episodes_metadata()` and `fetch_crc32_links()` via `_is_valid_quality()`
   - Requires "[One Pace]" marker in filename
4. **Config directory handling**: Use `get_config_dir()` and `get_config_path()` for consistent file location handling
   - Returns `/config` in Docker mode, `.` in local mode
   - Automatically creates directory if it doesn't exist
5. **URL parameter consistency**: Both `fetch_episodes_metadata()` and `fetch_crc32_links()` accept URL parameters
   - Always pass `args.url` to ensure consistent URL usage across functions
6. **Docker download logic**: Use `DOWNLOAD=true` environment variable to enable downloads
   - Missing episodes CSV is always generated/updated before download (if download enabled)
7. **Default connection values**: In Docker mode, use defaults if not specified via environment variables
   - Client: transmission
   - Host: localhost
   - Port: 9091 (transmission) or 8080 (qbittorrent)
8. **Debug mode**: Use `DEBUG` environment variable to control troubleshooting output
   - Defaults to `false` (no debug output)
   - Set to `true`, `1`, `yes`, or `on` to enable
   - All debug output uses `debug_print()` function which checks `DEBUG_MODE` flag

## BitTorrent Client Abstraction

- Abstract base class `Client` (in `clients.py`) defines interface using `abc.ABC`
- Concrete implementations: `QBittorrentClient`, `TransmissionClient`
- Factory function `get_client(client_name, host, port, username, password)` instantiates appropriate client
- Methods: `add_torrents(magnets, download_folder, tags, category)`
- **qBittorrentClient**: Uses `qbittorrentapi` library, checks for existing torrents by info hash, supports tags and categories
- **TransmissionClient**: Uses Transmission RPC API via HTTP requests, handles session ID management, does not support tags/categories

## Error Handling

- Network errors: HTTP request failures are caught and logged, continues processing remaining items
- File system errors: Checks for file existence before operations, handles permission errors gracefully
- Database errors: Uses `INSERT OR REPLACE` for idempotent operations, handles connection failures
- Rate limiting: Uses `time.sleep(0.2)` between requests

## Testing

- Comprehensive test suite exists in `tests/` directory (100+ tests)
- Run `pytest` with coverage before completing work
- Ensure all tests pass
- Test coverage includes: clients, CRC32, database, debug mode, episodes, file operations, main commands, missing detection, path normalization
