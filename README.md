# 🏴‍☠️ Ace-Pace

Welcome to **Ace-Pace**, your ultimate companion for organizing and managing your One-Pace library with precision and ease! Whether you're a casual viewer who wants a neat collection or a hardcore fan aiming for the perfect sync between episodes and the official One-Pace releases, Ace-Pace is designed to make your life simpler, your library cleaner, and your watching experience smoother.

One-Pace is a fantastic fan project that trims the One Piece anime down to its essential story arcs, removing filler and pacing issues to deliver a tighter, more engaging narrative.
However, managing your One-Pace episodes, ensuring you have all the latest releases can be a daunting task. That's where Ace-Pace comes in — it automates the heavy lifting, letting you focus on enjoying the adventure.

## 🚀 How to Install

To get started with Ace-Pace, you'll need to have Python installed on your system. We recommend using Python 3.6 or higher. You can download Python from the [official website](https://www.python.org/downloads/).

Once Python is installed, you need to install the required Python libraries.
Run this command in the Ace-Pace directory:

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
  -v $(pwd)/crc32_files.db:/app/crc32_files.db:rw \
  -v $(pwd)/episodes_index.db:/app/episodes_index.db:rw \
  -v $(pwd)/Ace-Pace_Missing.csv:/app/Ace-Pace_Missing.csv:rw \
  -e TZ=Europe/London \
  -e TORRENT_HOST=127.0.0.1 \
  -e TORRENT_PORT=9091 \
  -e TORRENT_CLIENT=transmission \
  -e NYAA_URL=https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc \
  -e DB=true \
  -e EPISODES_UPDATE=true \
  timothe/ace-pace:latest
```

### Using Docker Compose

For easier management, you can use the provided `docker-compose.yml` file. First, edit the compose file to match your setup:

1. Update the volume path for your One-Pace library:
   ```yaml
   volumes:
     - /path/to/OnePaceLibrary:/media:rw
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

- `NYAA_URL` - Nyaa.si search URL (default: `https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc`)
- `TORRENT_CLIENT` - BitTorrent client type: `transmission` or `qbittorrent` (default: `transmission`)
- `TORRENT_HOST` - BitTorrent client host address (default: `127.0.0.1`)
- `TORRENT_PORT` - BitTorrent client port (default: `9091` for Transmission, `8080` for qBittorrent)
- `TORRENT_USER` - BitTorrent client username (optional)
- `TORRENT_PASSWORD` - BitTorrent client password (optional)
- `DB` - Set to `true` to generate CSV database export (default: `true`)
- `EPISODES_UPDATE` - Set to `true` to update episodes metadata from Nyaa (default: `true`)
- `TZ` - Timezone (default: `Europe/Berlin`)

### Docker Volume Mounts

The following volumes should be mounted for persistent data:

- `/media` - Mount your One-Pace library directory here (read-write)
- `/app/crc32_files.db` - Database file for CRC32 checksums (read-write)
- `/app/episodes_index.db` - Database file for episodes index (read-write)
- `/app/Ace-Pace_Missing.csv` - CSV export of missing episodes (read-write)

### Docker Notes

- In Docker mode, Ace-Pace automatically uses `/media` as the default folder path
- The container runs non-interactively, so all configuration must be provided via environment variables
- Make sure your BitTorrent client is accessible from within the Docker network (use host network mode or configure networking appropriately)

## 🧪 Running Tests

To run the test suite with coverage:

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

## 🛠️ How to Use

Run the script using Python with the following command:
```
python acepace.py [-h] [--url URL] [--folder FOLDER] [--db] [--client {transmission,qbittorrent}] [--download] [--host HOST] [--port PORT] [--username USERNAME] [--password PASSWORD] [--download-folder DOWNLOAD_FOLDER] [--tag TAG]... [--category CATEGORY]
```

### 🔭 Main commands

- `--folder <path>` (required for most cases)
  Specify the path to your local One-Pace video library. Ace-Pace will scan this directory recursively to identify and analyze your existing episodes.

- `--url <website_url>`
  Define the Nyaa URL used for the query to get episodes metadata and download links. Defaults to `https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc`.

- `--db` (standalone flag)
  Create a CSV file with the existing local file paths and CRC32 checksums. Useful to check what's detected and debugging.

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

### 📚 Some examples

```
python acepace.py --folder "/volume42/media/One Piece/" --url https://nyaa.si/?f=0&c=0_0&q=one+pace+720p&o=asc
python acepace.py --folder "/volume42/media/One Piece/"
python acepace.py --client transmission --download
python acepace.py --client qbittorrent --download --host 192.168.1.100 --port 8080 --username myuser --password mypassword --download-folder /downloads/onepace --tag onepace --tag 'one pace' --category 'anime'
python acepace.py --db
```

## 📜 Workflow Overview

1. **Scanning:** Ace-Pace begins by scanning your specified folder, computing CRC32 checksums for each video file to build an accurate inventory of your current collection and store it locally.

2. **Missing Detection:** It then queries the One-Pace website to retrieve the latest episode list and compares it against your local inventory using the stored checksums and metadata.

3. **Reporting:** A detailed report is generated, highlighting which episodes you already have, which are missing, and any discrepancies.

4. **Optional Downloading:** After that, Ace-Pace will propose to download any missing episodes directly on your BitTorrent client.

## 🙏 Credits

Ace-Pace is proudly inspired by and built to support the incredible work of the [One-Pace](http://onepace.net/) team. Their dedication to crafting a seamless and engaging One Piece viewing experience has allowed me to discover and share this legendary series. I salute their passion, creativity, and commitment.

Since the start of this project, not unlinke Luffy, a few people joined me to build or support it, namely [@Staubgeborener](https://github.com/Staubgeborener) & [@thekoma](https://github.com/thekoma) who implemented the multi-clients functionality. Check them out!
