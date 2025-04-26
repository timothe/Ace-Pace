import requests
from bs4 import BeautifulSoup
import os
import zlib
import argparse
import re
import sqlite3
from datetime import datetime

# Define regex to extract CRC32 from filename text (commonly in [xxxxx])
CRC32_REGEX = re.compile(r"\[([A-Fa-f0-9]{8})\]")

# Video file extensions we care about
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi"}

DB_NAME = "crc32_files.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
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
    return conn


def get_metadata(conn, key):
    c = conn.cursor()
    c.execute("SELECT value FROM metadata WHERE key = ?", (key,))
    row = c.fetchone()
    return row[0] if row else None


def set_metadata(conn, key, value):
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", (key, value)
    )
    conn.commit()


def fetch_crc32_links(base_url):
    crc32_to_link = {}
    crc32_to_text = {}
    crc32_to_magnet = {}
    page = 1
    last_checked_page = 0
    while True:
        print(f"Fetching page {page}...")
        resp = requests.get(f"{base_url}&p={page}")
        if resp.status_code != 200:
            print(f"Failed to fetch page {page}, status code: {resp.status_code}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", class_="torrent-list")
        if not table:
            print("No table found, stopping.")
            break

        rows = table.find_all("tr")
        if not rows:
            print("No rows found, stopping.")
            break

        found_in_page = False
        for row in rows:
            links = row.find_all("a", href=True)
            if len(links) >= 2:
                filename_text = links[1].text
                link = "https://nyaa.si" + links[1]["href"]
                # Find magnet link in the row
                magnet_link = None
                for a in links:
                    href = a.get("href", "")
                    if href.startswith("magnet:"):
                        magnet_link = href
                        break
                match = CRC32_REGEX.search(filename_text)
                if match:
                    crc32 = match.group(1).upper()
                    crc32_to_link[crc32] = link
                    crc32_to_text[crc32] = filename_text
                    if magnet_link:
                        crc32_to_magnet[crc32] = magnet_link
                    else:
                        crc32_to_magnet[crc32] = ""
                    found_in_page = True

        if not found_in_page:
            break  # No more entries found

        last_checked_page = page
        page += 1

    return crc32_to_link, crc32_to_text, crc32_to_magnet, last_checked_page


def calculate_local_crc32(folder, conn):
    local_crc32s = set()
    c = conn.cursor()
    for root, dirs, files in os.walk(folder):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                file_path = os.path.join(root, file)
                # Check if file_path already in DB
                c.execute(
                    "SELECT crc32 FROM crc32_cache WHERE file_path = ?", (file_path,)
                )
                row = c.fetchone()
                if row:
                    crc32 = row[0]
                    local_crc32s.add(crc32)
                    continue

                parent_folder = os.path.basename(root)
                print(f"Calculating CRC32 for {parent_folder}/{file}...")
                with open(file_path, "rb") as f:
                    crc = 0
                    while chunk := f.read(8192):
                        crc = zlib.crc32(chunk, crc)
                    crc32 = f"{crc & 0xFFFFFFFF:08X}"
                local_crc32s.add(crc32)
                c.execute(
                    "INSERT OR REPLACE INTO crc32_cache (file_path, crc32) VALUES (?, ?)",
                    (file_path, crc32),
                )
                conn.commit()
    return local_crc32s


def main():

    parser = argparse.ArgumentParser(
        description="Find missing episodes from your personal One Pace library."
    )
    parser.add_argument(
        "--url",
        default="https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc",
        help="Base URL without the page param. Example: 'https://nyaa.si/?f=0&c=0_0&q=one+pace&o=asc' ",
    )
    parser.add_argument(
        "--folder", required=True, help="Folder containing local video files."
    )
    args = parser.parse_args()

    conn = init_db()

    # Count total video files and files already recorded in DB
    total_files = 0
    recorded_files = 0
    c = conn.cursor()
    for root, dirs, files in os.walk(args.folder):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                total_files += 1
                file_path = os.path.join(root, file)
                c.execute("SELECT 1 FROM crc32_cache WHERE file_path = ?", (file_path,))
                if c.fetchone():
                    recorded_files += 1

    last_run = get_metadata(conn, "last_run")

    if last_run:
        print(f"Last run was on: {last_run}")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_metadata(conn, "last_run", now_str)

    print(f"Using URL: {args.url}")

    print(f"Total video files detected: {total_files}")
    print(f"Video files already recorded in DB: {recorded_files}")

    crc32_to_link, crc32_to_text, crc32_to_magnet, last_checked_page = (
        fetch_crc32_links(args.url)
    )

    print(f"Found {len(crc32_to_link)} CRC32 entries from site.")

    if last_run:
        print("Calculating (new) local CRC32 hashes...")
    else:
        print(
            "Calculating local CRC32 hashes - this will take a while on first run!..."
        )

    local_crc32s = calculate_local_crc32(args.folder, conn)
    print(f"Found {len(local_crc32s)} local CRC32 hashes.")

    missing = [crc32 for crc32 in crc32_to_link if crc32 not in local_crc32s]

    print(
        f"\nSummary: {len(missing)} missing files out of {len(crc32_to_link)} total CRC32 entries found on the website.\n"
    )

    print("Missing files:")
    with open("missing.txt", "w", encoding="utf-8") as f:
        for crc32 in missing:
            entry = f"{crc32_to_text[crc32]} - {crc32_to_magnet.get(crc32, '')} - {crc32_to_link[crc32]}"
            print(entry)
            f.write(entry + "\n")

    set_metadata(conn, "last_checked_page", str(last_checked_page))


if __name__ == "__main__":
    main()
