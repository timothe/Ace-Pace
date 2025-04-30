import requests
from bs4 import BeautifulSoup
import os
import zlib
import argparse
import re
import sqlite3
from datetime import datetime
import csv
import time
import getpass

# Define regex to extract CRC32 from filename text (commonly in [xxxxx])
CRC32_REGEX = re.compile(r"\[([A-Fa-f0-9]{8})\]")

# Video file extensions we care about
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi"}

DB_NAME = "crc32_files.db"


def init_db():
    exists = os.path.exists(DB_NAME)
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
    if exists:
        print("Database already exists. You can export it using the --db option.")
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
            title_link = None
            magnet_link = ""
            for a in links:
                if a.has_attr("title"):
                    title_link = a
                href = a.get("href", "")
                if href.startswith("magnet:"):
                    magnet_link = href
            if not title_link:
                continue  # Skip rows without a valid title link
            filename_text = title_link.text
            link = "https://nyaa.si" + title_link["href"]
            matches = CRC32_REGEX.findall(filename_text)
            if matches:
                crc32 = matches[-1].upper()
                crc32_to_link[crc32] = link
                crc32_to_text[crc32] = filename_text
                crc32_to_magnet[crc32] = magnet_link
                found_in_page = True
            else:
                print(f"Warning: No CRC32 found in title '{filename_text}'")

        if not found_in_page:
            break  # No more entries found

        last_checked_page = page
        page += 1

    return crc32_to_link, crc32_to_text, crc32_to_magnet, last_checked_page


def fetch_title_by_crc32(crc32):
    # Search on Nyaa for the given CRC32
    search_url = f"https://nyaa.si/?f=0&c=0_0&q={crc32}&o=asc"
    resp = requests.get(search_url)
    if resp.status_code != 200:
        print(f"Failed to fetch search results for CRC32 {crc32}")
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="torrent-list")
    if not table:
        return None
    rows = table.find_all("tr")
    matched_titles = []
    for row in rows:
        links = row.find_all("a", href=True)
        for a in links:
            if a.has_attr("title"):
                filename_text = a.text
                matches = CRC32_REGEX.findall(filename_text)
                if matches and matches[-1].upper() == crc32:
                    matched_titles.append(filename_text)
    if len(matched_titles) == 1:
        print(f"Found {crc32} on Nyaa!")
        return matched_titles[0]
    elif len(matched_titles) == 0:
        print(f"Warning: No title found for {crc32}")
        return None
    else:
        print(f"Warning: Multiple titles found for CRC32 {crc32}: {matched_titles}")
        return None


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


def rename_local_files(conn, folder):
    c = conn.cursor()
    c.execute("SELECT file_path, crc32 FROM crc32_cache")
    entries = c.fetchall()
    if not entries:
        print("No entries found in local CRC32 database.")
        return

    rename_plan = []
    for file_path, crc32 in entries:
        title = fetch_title_by_crc32(crc32)
        if not title:
            continue  # No match found on Nyaa, skip

        dir_name = os.path.dirname(file_path)
        ext = os.path.splitext(file_path)[1]
        # Sanitize title for filename (remove problematic characters)
        sanitized_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
        new_filename = f"{sanitized_title}"
        new_path = os.path.join(dir_name, new_filename)

        if os.path.abspath(file_path) != os.path.abspath(new_path):
            rename_plan.append((file_path, new_path))

    if not rename_plan:
        print("No files to rename.")
        return

    print("Rename plan:")
    for old, new in rename_plan:
        print(f"{os.path.basename(old)} -> {os.path.basename(new)}")
    print(f"{len(rename_plan)} file(s) will be renamed.")

    confirm = input("Proceed with renaming? (y/n): ").strip().lower()
    if confirm != "y":
        print("Renaming aborted.")
        return

    for old, new in rename_plan:
        try:
            if os.path.exists(new):
                print(f"Cannot rename {old} to {new}: target file already exists.")
                continue
            os.rename(old, new)
            print(f"Renamed {old} to {new}")
            # Update DB with new file path
            c.execute(
                "UPDATE crc32_cache SET file_path = ? WHERE file_path = ?", (new, old)
            )
            conn.commit()
        except Exception as e:
            print(f"Failed to rename {old} to {new}: {e}")


def export_db_to_csv(conn):
    c = conn.cursor()
    c.execute("SELECT file_path, crc32 FROM crc32_cache")
    rows = c.fetchall()
    with open("Ace-Pace_DB.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["File Path", "CRC32"])
        for row in rows:
            writer.writerow(row)
    print("Database exported to Ace-Pace_DB.csv")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_metadata(conn, "last_db_export", now_str)


def download_with_transmission():
    if not os.path.exists("Ace-Pace_Missing.csv"):
        print("Missing file 'Ace-Pace_Missing.csv' not found. Run the script first!")
        return

    magnets = []
    with open("Ace-Pace_Missing.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            magnet_link = row.get("Magnet Link", "").strip()
            if magnet_link.startswith("magnet:"):
                magnets.append(magnet_link)

    if not magnets:
        print("No magnet links found in 'Ace-Pace_Missing.csv'.")
        return

    print("The details below are not stored.")
    host = input("Enter Transmission host (default: localhost): ").strip()
    if not host:
        host = "localhost"
    port_input = input("Enter Transmission port (default: 9091): ").strip()
    if port_input:
        try:
            port = int(port_input)
        except ValueError:
            print("Invalid port number. Using default 9091.")
            port = 9091
    else:
        port = 9091
    rpc_username = input("Enter Transmission username (leave blank if none): ").strip()
    rpc_password = getpass.getpass(
        "Enter Transmission password (leave blank if none): "
    ).strip()

    base_url = f"http://{host}:{port}/transmission/rpc"
    session_id = None
    session = requests.Session()
    auth = (rpc_username, rpc_password) if rpc_username else None

    # Test connection and get session ID
    try:
        headers = {}
        if session_id:
            headers["X-Transmission-Session-Id"] = session_id
        resp = session.post(
            base_url, auth=auth, headers=headers, json={"method": "session-get"}
        )
        if resp.status_code == 409:
            session_id = resp.headers.get("X-Transmission-Session-Id")
            headers["X-Transmission-Session-Id"] = session_id
            resp = session.post(
                base_url, auth=auth, headers=headers, json={"method": "session-get"}
            )
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed to connect to Transmission RPC: {e}")
        return

    print("Connection to Transmission successful!")

    # Suggest default download directory to user
    try:
        session_info = resp.json()
        default_download_dir = ""
        if "arguments" in session_info and "download-dir" in session_info["arguments"]:
            default_download_dir = session_info["arguments"]["download-dir"]
    except Exception:
        default_download_dir = ""

    if default_download_dir:
        prompt_text = f"Enter target folder for downloads (current default: {default_download_dir}): "
    else:
        prompt_text = "Enter target folder for downloads (leave blank for default): "
    target_folder = input(prompt_text).strip()

    confirm = (
        input(f"Do you want to add {len(magnets)} torrents to Transmission? (y/n): ")
        .strip()
        .lower()
    )
    if confirm != "y":
        print("Abort! Abort!")
        return

    added_count = 0
    total = len(magnets)
    for idx, magnet in enumerate(magnets, 1):
        truncated = magnet[:50] + ("..." if len(magnet) > 50 else "")
        print(f"Adding {idx}/{total}: {truncated}")
        payload = {"method": "torrent-add", "arguments": {"filename": magnet}}
        if target_folder:
            payload["arguments"]["download-dir"] = target_folder
        try:
            headers = {"X-Transmission-Session-Id": session_id} if session_id else {}
            resp = session.post(base_url, auth=auth, headers=headers, json=payload)
            if resp.status_code == 409:
                session_id = resp.headers.get("X-Transmission-Session-Id")
                headers["X-Transmission-Session-Id"] = session_id
                resp = session.post(base_url, auth=auth, headers=headers, json=payload)
            resp.raise_for_status()
            result = resp.json()
            if result.get("result") == "success":
                added_count += 1
            else:
                print(
                    f"Failed to add torrent: {truncated} Error: {result.get('result')}"
                )
            time.sleep(0.1)
        except Exception as e:
            print(f"Failed to add torrent: {truncated} Error: {e}")

    print(f"Added {added_count} torrents to Transmission.")


def download_missing_to_client(client_type):
    client_type = client_type.lower()
    if client_type == "transmission":
        download_with_transmission()
    else:
        print(f"Download client '{client_type}' not supported.")


def main():

    parser = argparse.ArgumentParser(
        description="Find missing episodes from your personal One Pace library."
    )
    parser.add_argument(
        "--url",
        default="https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc",
        help="Base URL without the page param. Example: 'https://nyaa.si/?f=0&c=0_0&q=one+pace&o=asc' ",
    )
    parser.add_argument("--folder", help="Folder containing local video files.")
    parser.add_argument(
        "--db", action="store_true", help="Export database to CSV and exit."
    )
    parser.add_argument(
        "--download",
        metavar="CLIENT",
        help="Import magnet links from missing CSV and add to specified BitTorrent client (e.g. transmission).",
    )
    parser.add_argument(
        "--rename",
        action="store_true",
        help="Rename local files based on CRC32 matching titles from Nyaa.",
    )
    args = parser.parse_args()

    # Check if the URL points to Nyaa
    if not args.url.startswith("https://nyaa.si"):
        print(
            "Error: The --url argument must point to the Nyaa website (https://nyaa.si)."
        )
        return

    conn = init_db()

    # Folder selection logic: Always prompt if folder is required but not given
    folder = args.folder
    needs_folder = not args.download  # All commands except --download need folder
    if needs_folder and not folder:
        # Try to load last_folder from metadata
        last_folder = get_metadata(conn, "last_folder")
        if last_folder:
            print(f"Previously used folder: {last_folder}")
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
            return
        set_metadata(conn, "last_folder", folder)
    elif folder:
        set_metadata(conn, "last_folder", folder)

    if args.download:
        download_missing_to_client(args.download)
        return

    if args.rename:
        print("Renaming local files based on matching titles from Nyaa...")
        rename_local_files(conn, folder)
        return

    if not folder:
        print("Error: --folder argument is required.")
        return

    last_missing_export = get_metadata(conn, "last_missing_export")
    if last_missing_export:
        print(f"Last missing files list generated on: {last_missing_export}")

    if args.db:
        export_db_to_csv(conn)
        return

    # Count total video files and files already recorded in DB
    total_files = 0
    recorded_files = 0
    c = conn.cursor()
    for root, dirs, files in os.walk(folder):
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
    print(f"Episodes already recorded in DB: {recorded_files}")

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

    # Check for new CRC32 in missing compared to old file if exists
    old_missing_crc32s = set()
    if os.path.exists("Ace-Pace_Missing.csv"):
        with open("Ace-Pace_Missing.csv", "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if len(row) >= 1:
                    title = row[0]
                    # Extract CRC32 from title if possible
                    matches = CRC32_REGEX.findall(title)
                    if matches:
                        old_missing_crc32s.add(matches[-1].upper())
        new_crc32s = set(missing) - old_missing_crc32s
        if new_crc32s:
            print(f"New missing episodes detected since last export: {len(new_crc32s)}")
            for crc32 in new_crc32s:
                title = crc32_to_text.get(crc32, "(Unknown Title)")
                print(f"Missing: {title}")

    with open("Ace-Pace_Missing.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["Title", "Page Link", "Magnet Link"])
        for crc32 in missing:
            title = crc32_to_text[crc32]
            page_link = crc32_to_link[crc32]
            magnet = crc32_to_magnet.get(crc32, "")
            writer.writerow([title, page_link, magnet])

    print("Missing files list saved to Ace-Pace_Missing.csv")

    set_metadata(conn, "last_checked_page", str(last_checked_page))
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_metadata(conn, "last_missing_export", now_str)

    if missing:
        prompt = (
            input(
                "Do you want to add missing episodes to a BitTorrent client now? (y/n): "
            )
            .strip()
            .lower()
        )
        if prompt == "y":
            client = (
                input("Enter client name (currently supported: transmission): ")
                .strip()
                .lower()
            )
            if client:
                download_missing_to_client(client)
            else:
                print("No client specified. Skipping download.")


if __name__ == "__main__":
    main()
