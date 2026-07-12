# 🏴‍☠️ Ace-Pace

Welcome to **Ace-Pace**, your ultimate companion for organizing and managing your One-Pace library with precision and ease! Whether you're a casual viewer who wants a neat collection or a hardcore fan aiming for the perfect sync between episodes and the official One-Pace releases, Ace-Pace is designed to make your life simpler, your library cleaner, and your watching experience smoother.

One-Pace is a fantastic fan project that trims the One Piece anime down to its essential story arcs, removing filler and pacing issues to deliver a tighter, more engaging narrative.
However, managing your One-Pace episodes, ensuring you have all the latest releases can be a daunting task. That's where Ace-Pace comes in — it automates the heavy lifting, letting you focus on enjoying the adventure.

## 🚀 How to Install

To get started with Ace-Pace, you'll need Python 3.11+ (the `--doctor` command and `acepace.toml` config file support use `tomllib`, stdlib since 3.11). You can download Python from the [official website](https://www.python.org/downloads/).

Recommended: install with [uv](https://docs.astral.sh/uv/) (also used for tests/CI):

```
uv sync
```

Or plain pip, in the Ace-Pace directory:

```
pip install -r requirements.txt
```

This will install all necessary packages to ensure Ace-Pace runs smoothly.

## 🐳 Docker Usage

Ace-Pace can also be run using Docker, which simplifies deployment and ensures consistent execution across different environments.

### Using Docker Run

You can run Ace-Pace using `docker run` with environment variables and volume mounts:

```bash
docker run --rm \
  -v /path/to/OnePaceLibrary:/media:rw \
  -v /path/to/config:/config:rw \
  -e TZ=Europe/London \
  -e DB=true \
  -e EPISODES_UPDATE=true \
  -e DOWNLOAD=false \
  -e DRY_RUN=false \
  -e TORRENT_CLIENT=transmission \
  -e TORRENT_HOST=127.0.0.1 \
  -e TORRENT_PORT=9091 \
  -e NYAA_URL=https://nyaa.si/?f=0&c=0_0&q=one+pace&o=asc \
  -e DEBUG=true \
  timothe/ace-pace:latest
```

### Using Docker Compose

For easier management, you can use the provided `docker-compose.yml` file. First, edit the compose file to match your setup:

1. Update the volume paths:
   ```yaml
   volumes:
     - /path/to/OnePaceLibrary:/media:rw
     - /path/to/config:/config:rw
   ```

2. Configure environment variables as needed (Torrent client settings, Nyaa URL, etc.)

3. Run with:
   ```bash
   docker-compose up
   ```

Or run in detached mode:
```bash
docker-compose up -d
```

### Docker Environment Variables

The following environment variables can be used to configure Ace-Pace in Docker:

- `NYAA_URL` - Nyaa.si search URL (optional, default: `https://nyaa.si/?f=0&c=0_0&q=one+pace&o=asc`)
  - When not set, uses default URL without quality filter. Quality filtering (1080p only) is always applied in code.
- `DB` - Set to `true` to generate CSV database export on container start (default: `false`)
- `EPISODES_UPDATE` - Set to `true` to update episodes metadata from Nyaa on container start (default: `false`)
- `DOWNLOAD` - Set to `true` to automatically download missing episodes after generating report (default: `false`)
  - Missing/present detection is version-aware: episodes are grouped by canonical (season, episode, version), and an episode counts as "present" if any of its versions' releases is local. When missing, the newest-dated release of that episode is selected for download.
- `RENAME` - Set to `true` to rename local files in the media folder to the canonical Plex naming (default: `false`)
  - Target format: `One Pace - S{season}E{episode} - {Title}.ext` (season/episode/title sourced from the [one-pace-for-plex](https://github.com/SpykerNZ/one-pace-for-plex) reference index), with the matching `.nfo`/poster copied alongside
  - Non-interactive: no confirmation prompt; use `DRY_RUN=true` to simulate renaming without changing files
  - Before renaming, ensures CRC32 cache is complete for the media folder (calculates missing CRC32s if needed)
  - In Docker, real (non-dry-run) moves only happen when `RENAME_FORCE=true` — otherwise `RENAME=true` alone runs as dry-run-only
  - Every real rename is journaled; run `--undo` (local CLI) to reverse the last run
- `RENAME_FORCE` - Must be `true` for `RENAME=true` to perform real (non-dry-run) file moves in Docker (default: `false`). Without it, Docker rename runs print the plan only, regardless of `DRY_RUN`.
- `VERSION` - Which episode cut is canonical for rename and missing/download detection: `normal` or `extended` (default: `normal`). `extended` prefers the extended/alternate cut of an episode when both exist, falling back to normal if there isn't one.
- `REFERENCE_UPDATE` - Set to `true` to refresh the vendored one-pace-for-plex reference data (seasons/exceptions/episode list) from GitHub on container start (default: `false`). Falls back to the vendored snapshot shipped in the image on fetch failure, so rename works fully offline without this.
- `ACEPACE_MEDIA_DIR_DOCKER` - Media/library folder in Docker (default: `"/media"`). Entrypoint passes this as `--folder`.
- `ACEPACE_CONFIG_DIR_DOCKER` - Config/data directory in Docker (default: `"/config"`). Not set in entrypoint; override if you mount config elsewhere.
- `DRY_RUN` - When `DOWNLOAD=true`: test BitTorrent client without adding torrents. When `RENAME=true`: show rename plan without renaming (default: `false`)
  - With download: validates magnet links and checks existing torrents but does not add any downloads
  - With rename: prints which files would be renamed without modifying the filesystem
- `TORRENT_CLIENT` - BitTorrent client type: `transmission` or `qbittorrent` (default: `transmission`)
- `TORRENT_HOST` - BitTorrent client host address (default: `localhost`)
- `TORRENT_PORT` - BitTorrent client port (default: `9091` for Transmission, `8080` for qBittorrent)
- `TORRENT_USER` - BitTorrent client username (optional)
- `TORRENT_PASSWORD` - BitTorrent client password (optional)
- `DEBUG` - Enable debug output for troubleshooting (default: `false`)
  - Set to `true`, `1`, `yes`, or `on` to enable detailed debug information
  - When enabled, shows troubleshooting info, sample CRC32s, comparison details, and processing statistics
  - Useful for diagnosing issues with missing episode detection or data processing
- `TZ` - Timezone (default: `Europe/London`)

### Docker Volume Mounts

The following volumes should be mounted for persistent data:

- **Media folder** (default `/media`) - Mount your One-Pace library here (read-write). Override with `ACEPACE_MEDIA_DIR_DOCKER`.
- **Config folder** (default `/config`) - Mount a directory for persistent configuration and data files (read-write). Override with `ACEPACE_CONFIG_DIR_DOCKER`.
  - Contains: `crc32_files.db`, `episodes_index.db`, `Ace-Pace_Missing.csv`, `Ace-Pace_DB.csv`
  - `episodes_index.db` now stores magnet links for all episodes, reducing the need to fetch them repeatedly

### Docker Execution Flow

When the container starts, it executes the following steps in order:

1. **Episodes Update** (if `EPISODES_UPDATE=true`): Updates the episodes metadata database from Nyaa, including magnet links for all episodes
2. **Database Export** (if `DB=true`): Exports the CRC32 database to CSV
3. **Missing Episodes Report**: Always runs to generate/update `Ace-Pace_Missing.csv` (unless only DB export was requested)
4. **Rename** (if `RENAME=true`): Ensures CRC32 cache is complete for the media folder, then renames local files to match One-Pace episode titles (no confirmation). Use `DRY_RUN=true` to simulate only.
5. **Download** (if `DOWNLOAD=true`): Automatically downloads missing episodes via the configured BitTorrent client
   - If `DRY_RUN=true`, tests connection and validates magnet links without adding torrents

### Docker Notes

- In Docker mode, the default media folder is `/media` (set `ACEPACE_MEDIA_DIR_DOCKER` to override); config/data default is `/config` (set `ACEPACE_CONFIG_DIR_DOCKER` to override)
- The container runs non-interactively, so all configuration must be provided via environment variables
- All data files (databases, CSV exports) are stored in the config directory
- Quality filtering (1080p only) is applied in code regardless of the URL used
- When `NYAA_URL` is not set, the default URL searches for all "one pace" episodes without quality filter, then filters for 1080p in code
- Make sure your BitTorrent client is accessible from within the Docker network (use host network mode or configure networking appropriately)

### VPN Considerations

If you're running Ace-Pace through a VPN container (such as Gluetun), you may encounter 429 (Too Many Requests) errors when querying Nyaa.si. This is because multiple requests from the same VPN exit node can trigger rate limiting.

**Recommendation:** It's perfectly fine to run Ace-Pace without a VPN. Instead, keep your BitTorrent client behind the VPN to protect your downloads while allowing Ace-Pace to query Nyaa.si directly without rate limiting issues.

## ⚙️ Config File (`acepace.toml`)

Instead of exporting environment variables every time, copy `acepace.toml.example` to `acepace.toml` (next to `acepace.py`, or in the config dir used by `--folder`/`ACEPACE_CONFIG_DIR_DOCKER`) and set defaults there. Precedence is: CLI flag > environment variable > `acepace.toml` > built-in default. Keys map 1:1 to the environment variables described above (`VERSION`, `RENAME`, `RENAME_FORCE`, `REFERENCE_UPDATE`, `TORRENT_*`, etc.). Requires Python 3.11+ (uses stdlib `tomllib`); if unavailable, the file is silently ignored.

## 🧪 Running Tests

With `uv` (matches CI):

```bash
make install   # uv sync --extra dev
make test      # uv run pytest
make coverage  # uv run pytest --cov=. --cov-report=xml:coverage.xml
```

Or with plain pip/pytest:

```bash
# Install test dependencies
pip install -r requirements.txt

# Run tests with coverage
pytest

# Or explicitly generate coverage report
pytest --cov=. --cov-report=xml --cov-report=html --cov-report=term-missing
```

This will generate:
- `coverage.xml` - Used by SonarQube for test coverage analysis
- `htmlcov/` - HTML coverage report (open `htmlcov/index.html` in a browser)
- Terminal output showing coverage summary

## 🐛 Debug Mode

Ace-Pace includes a debug mode that provides detailed troubleshooting information. This is useful when diagnosing issues with missing episode detection or data processing.

### Enabling Debug Mode

**In Python (local execution):**
```bash
DEBUG=true python acepace.py --folder /path/to/videos
```

**In Docker:**
```bash
docker run --rm \
  -v /path/to/OnePaceLibrary:/media:rw \
  -v /path/to/config:/config:rw \
  timothe/ace-pace:latest
```

**In Docker Compose:**
Add to your `docker-compose.yml`:
```yaml
environment:
  - DEBUG=true
```

### Debug Output

When debug mode is enabled, you'll see additional information including:
- Episode fetching progress and page counts
- CRC32 normalization and comparison details
- Sample CRC32s from both Nyaa and local sources
- File processing statistics (cached vs calculated)
- Mapping issues and comparison mismatches
- Intersection and difference analysis
- Processing statistics for each operation

All debug output is prefixed with "DEBUG:" for easy filtering.

**Note:** Debug mode defaults to `false` (disabled). Set `DEBUG` to `true`, `1`, `yes`, or `on` to enable. The value is case-insensitive.

## 🛠️ How to Use

Run the script using Python with the following command:
```
python acepace.py [-h] [--url URL] [--folder FOLDER] [--db] [--client {transmission,qbittorrent}] [--download] [--host HOST] [--port PORT] [--username USERNAME] [--password PASSWORD] [--download-folder DOWNLOAD_FOLDER] [--tag TAG]... [--category CATEGORY]
```

### 🔭 Main commands

- `--folder <path>` (required for most cases)
  Specify the path to your local One-Pace video library. Ace-Pace will scan this directory recursively to identify and analyze your existing episodes.

- `--url <website_url>`
  Define the Nyaa URL used for the query to get episodes metadata and download links. Defaults to `https://nyaa.si/?f=0&c=0_0&q=one+pace&o=asc`.
  Note: Quality filtering (1080p only) is always applied in code.

- `--db` (standalone flag)
  Create a CSV file with the existing local file paths and CRC32 checksums. Useful to check what's detected and debugging.

- `--rename` (standalone flag)
  Rename local files to the canonical Plex naming (`One Pace - S{season}E{episode} - {Title}.ext`, sourced from the [one-pace-for-plex](https://github.com/SpykerNZ/one-pace-for-plex) reference index), copying the matching `.nfo`/poster alongside. Requires `--folder`. Optionally use `--url` for a custom Nyaa.si search URL, and `--version {normal,extended}` to pick which cut is canonical. Prompts for confirmation before touching the filesystem (unless `--dry-run`).

- `--undo` (standalone flag)
  Undo the most recent real (non-dry-run) `--rename` run: reverses the file moves/renames and reverts the recorded CRC32-cache paths. Only the last run is journaled.

- `--doctor` (standalone flag)
  Run diagnostics and exit: media folder readable, reference data present/fresh, `episodes_index.db` has rows, torrent client connectivity (if configured), and SQLite file integrity. Exits non-zero if any hard check fails. Doesn't scrape or touch files.

- `--episodes_update` (standalone flag)
  Update the episodes metadata database from Nyaa.si. Optionally use `--url` to specify a custom Nyaa.si search URL. This command forces an update even if episodes were recently updated (within the last 10 minutes).

### 🔧 Rename & output options

- `--version {normal,extended}`
  Which episode cut is canonical for `--rename` and missing/download detection (default: `normal`, env: `VERSION`). `extended` prefers the extended/alternate cut when both exist.

- `--quiet` (standalone flag)
  Suppress non-essential output; errors and final summaries still print.

- `--verbose` (standalone flag)
  Equivalent to `DEBUG=true`.

### 📥 Download commands

- `--client <client_name>`
  Specify the BitTorrent client to use for downloading missing episodes.
  Supported clients: `transmission`, `qbittorrent`.

- `--download` (standalone flag)
  Enable downloading of missing episodes using the specified BitTorrent client.

- `--host <host>`
  The BitTorrent client host (default: `localhost`).

- `--port <port>`
  The BitTorrent client port.

- `--username <username>`
  The BitTorrent client username.

- `--password <password>`
  The BitTorrent client password.

- `--download-folder <path>`
  The folder to download the torrents to.

- `--tag <tag>...`
  Tag to add to the torrent in qBittorrent (can be used multiple times).

- `--category <category>`
  Category to add to the torrent in qBittorrent.

- `--dry-run` (standalone flag)
  With `--download`: test BitTorrent client without adding torrents. With `--rename`: show rename plan without renaming files.

### 📚 Some examples

```
python acepace.py --folder "/volume42/media/One Piece/" --url https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc
python acepace.py --folder "/volume42/media/One Piece/"
python acepace.py --client transmission --download
python acepace.py --client qbittorrent --download --host 192.168.1.100 --port 8080 --username myuser --password mypassword --download-folder /downloads/onepace --tag onepace --tag 'one pace' --category 'anime'
python acepace.py --client transmission --download --dry-run
python acepace.py --client qbittorrent --download --dry-run --host 192.168.1.100 --port 8080
python acepace.py --db
python acepace.py --folder "/volume42/media/One Piece/" --rename
python acepace.py --folder "/volume42/media/One Piece/" --rename --version extended
python acepace.py --folder "/volume42/media/One Piece/" --rename --dry-run
python acepace.py --undo
python acepace.py --doctor
python acepace.py --episodes_update --url https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc
```

## 📜 Workflow Overview

1. **Scanning:** Ace-Pace begins by scanning your specified folder, computing CRC32 checksums for each video file to build an accurate inventory of your current collection and store it locally.

2. **Missing Detection:** It then queries the One-Pace website to retrieve the latest episode list and compares it against your local inventory using the stored checksums and metadata. Episodes are grouped by canonical (season, episode, version) so re-encodes/re-uploads of the same episode don't count as missing, and the newest release is preferred for download.

3. **Reporting:** A detailed report is generated, highlighting which episodes you already have, which are missing, and any discrepancies.

4. **Optional Downloading:** After that, Ace-Pace will propose to download any missing episodes directly on your BitTorrent client.

5. **Optional Renaming:** `--rename` renames local files to the canonical Plex naming and copies the matching `.nfo`/poster alongside, using [one-pace-for-plex](https://github.com/SpykerNZ/one-pace-for-plex) as the reference. Every real rename is journaled so it can be undone with `--undo`.

## 🙏 Credits

Ace-Pace is proudly inspired by and built to support the incredible work of the [One-Pace](http://onepace.net/) team. Their dedication to crafting a seamless and engaging One Piece viewing experience has allowed me to discover and share this legendary series. I salute their passion, creativity, and commitment.

Since the start of this project, not unlinke Luffy, a few people joined me to build or support it, namely [@Staubgeborener](https://github.com/Staubgeborener) & [@thekoma](https://github.com/thekoma) who implemented the multi-clients functionality. Check them out!
