# Ace-Pace

Welcome to **Ace-Pace**, your ultimate companion for organizing and managing your One-Pace library with precision and ease! Whether you're a casual viewer who wants a neat collection or a hardcore fan aiming for the perfect sync between episodes and the official One-Pace releases, Ace-Pace is designed to make your life simpler, your library cleaner, and your watching experience smoother.

One-Pace is a fantastic fan project that trims the One Piece anime down to its essential story arcs, removing filler and pacing issues to deliver a tighter, more engaging narrative.
However, managing your One-Pace episodes, ensuring you have all the latest releases can be a daunting task. That's where Ace-Pace comes in — it automates the heavy lifting, letting you focus on enjoying the adventure.

## How to Install

To get started with Ace-Pace, you'll need to have Python installed on your system. We recommend using Python 3.6 or higher. You can download Python from the [official website](https://www.python.org/downloads/).

Once Python is installed, you need to install the required Python libraries.
Run this command in the Ace-Pace directory:

```
pip install -r requirements.txt
```

This will install all necessary packages to ensure Ace-Pace runs smoothly.

## How to Use

Run the script using Python with the following command:
```
python acepace.py [-h] [--url URL] [--folder FOLDER] [--db] [--download CLIENT]
```

- `--folder <path>` (required for most cases)
  Specify the path to your local One-Pace video library. Ace-Pace will scan this directory recursively to identify and analyze your existing episodes.

- `--url <website_url>`  
  Define the Nyaa URL used for the query to get episodes metadata and download links. Defaults to `https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc`.

- `--db` (standalone flag)
  Create a CSV file with the existing local file paths and CRC32 checksums. Useful to check what's detected and debugging.

- `--download <client_name>` (standalone flag)
  Enable downloading of missing episodes using a BitTorrent client (only Transmission is supported currently). 

### Some examples

```
python acepace.py --folder "/volume42/media/One Piece/" --url https://nyaa.si/?f=0&c=0_0&q=one+pace+720p&o=asc
python acepace.py --folder "/volume42/media/One Piece/"
python acepace.py --download transmission
python acepace.py --db
```

## Workflow Overview

1. **Scanning:** Ace-Pace begins by scanning your specified folder, computing CRC32 checksums for each video file to build an accurate inventory of your current collection and store it locally.

2. **Missing Detection:** It then queries the One-Pace website to retrieve the latest episode list and compares it against your local inventory using the stored checksums and metadata.

3. **Reporting:** A detailed report is generated, highlighting which episodes you already have, which are missing, and any discrepancies.

4. **Optional Downloading:** After that, Ace-Pace will propose to download any missing episodes directly on your BitTorrent client (Transmission only for now).

## Credits

Ace-Pace is proudly inspired by and built to support the incredible work of the [One-Pace](http://onepace.net/) team. Their dedication to crafting a seamless and engaging One Piece viewing experience has allowed me to discover and share this legendary series. I salute their passion, creativity, and commitment.

## Docker Usage

The easiest way to run Ace Pace is using Docker.

1.  **Configure `docker-compose.yml`**:
    *   Set `TORRENT_HOST`, `TORRENT_PORT`, `TORRENT_USER`, `TORRENT_PASSWORD` for your Transmission instance.
    *   Set `EXT_PREF=true` (default) to prefer extended episodes, or `false` for normal versions.
    *   Map your downloads folder to `/media`.

2.  **Run the container**:
    ```bash
    docker-compose up -d
    ```

    On the first run, it will automatically fetch episode metadata. Subsequent runs will check for new episodes and missing files.

    The missing episodes list is automatically exported to `data/Ace-Pace_Missing.csv`.

## Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `TORRENT_HOST` | `localhost` | Transmission host IP/Hostname |
| `TORRENT_PORT` | `9091` | Transmission port |
| `TORRENT_USER` | | Transmission username |
| `TORRENT_PASSWORD` | | Transmission password |
| `TORRENT_CLIENT` | `transmission` | Torrent client to use |
| `EXT_PREF` | `true` | Prefer "Extended" episodes if available |
| `EPISODES_UPDATE` | `false` | Force update of episode metadata on start |
| `NYAA_URL` | `https://nyaa.si...` | Nyaa URL for fetching episodes |
| `DB` | `false` | If `true`, export database to CSV and exit |
| `RENAME` | `false` | If `true`, rename local files based on CRC32 matches |
| `TZ` | `Europe/London` | Timezone for the container |

## Docker Run (One-time)

If you prefer to run Ace-Pace as a one-off command without Docker Compose, you can use `docker run`.

**Example: Standard Run**
```bash
docker run --rm \
  -v "/path/to/your/media:/media" \
  -v "$(pwd)/data:/data" \
  -e TZ="Europe/London" \
  ace-pace
```

**Example: Force Metadata Update**
```bash
docker run --rm \
  -v "/path/to/your/media:/media" \
  -v "$(pwd)/data:/data" \
  -e EPISODES_UPDATE="true" \
  ace-pace
```

**Example: Rename Local Files**
```bash
docker run --rm \
  -v "/path/to/your/media:/media" \
  -v "$(pwd)/data:/data" \
  -e RENAME="true" \
  ace-pace
```
