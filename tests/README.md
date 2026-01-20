# Ace-Pace Test Suite

This directory contains unit tests for the Ace-Pace application.

## Test Structure

- `test_database.py` - Tests for database initialization and metadata operations
- `test_crc32.py` - Tests for CRC32 calculation and extraction
- `test_episodes.py` - Tests for episode metadata fetching from Nyaa
- `test_file_operations.py` - Tests for file operations and renaming
- `test_clients.py` - Tests for BitTorrent client integrations
- `test_missing_detection.py` - Tests for missing episode detection logic
- `conftest.py` - Shared fixtures and test utilities

## Running Tests

To run all tests:

```bash
pytest tests/
```

To run a specific test file:

```bash
pytest tests/test_database.py
```

To run a specific test:

```bash
pytest tests/test_database.py::TestDatabaseInitialization::test_init_db_creates_tables
```

To run with verbose output:

```bash
pytest tests/ -v
```

To run with coverage:

```bash
pytest tests/ --cov=acepace --cov=clients
```

## Test Coverage

The test suite covers:

1. **Database Operations**
   - Database initialization
   - Metadata get/set operations
   - Episodes index operations

2. **CRC32 Operations**
   - CRC32 extraction from filenames
   - CRC32 calculation from file content
   - Caching of CRC32 values

3. **Episode Metadata**
   - Fetching episodes from Nyaa
   - Handling pagination
   - Extracting CRC32 from titles and file lists
   - Updating episodes index database

4. **File Operations**
   - File renaming based on CRC32 matching
   - Filename sanitization
   - CSV export functionality

5. **BitTorrent Clients**
   - qBittorrent client initialization and operations
   - Transmission client initialization and operations
   - Client factory function
   - Error handling

6. **Missing Episode Detection**
   - Comparing local and remote CRC32s
   - Generating missing episode lists
   - Fetching CRC32 links from Nyaa

## Mocking

Tests use mocking for:
- Network requests (requests.get)
- File system operations
- BitTorrent client APIs
- User input prompts
- Time delays

## Fixtures

Common fixtures are defined in `conftest.py`:
- `temp_dir` - Temporary directory for test files
- `temp_db_path` - Temporary database path
- `sample_video_content` - Sample video content for testing
- `sample_crc32` - Sample CRC32 value
- `sample_episode_data` - Sample episode data
- `mock_nyaa_html_*` - Mock HTML responses from Nyaa
