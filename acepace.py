import requests
from bs4 import BeautifulSoup
import os
import zlib
import argparse
import re

# Define regex to extract CRC32 from title (commonly in [xxxxx])
CRC32_REGEX = re.compile(r"\[([A-Fa-f0-9]{8})\]")

# Video file extensions we care about
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".flv"}


def fetch_crc32_links(base_url):
    crc32_to_link = {}
    page = 1
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
            title_cell = row.find("a", href=True, title=True)
            if title_cell:
                title = title_cell["title"]
                link = "https://nyaa.si" + title_cell["href"]
                match = CRC32_REGEX.search(title)
                if match:
                    crc32 = match.group(1).upper()
                    crc32_to_link[crc32] = link
                    found_in_page = True

        if not found_in_page:
            break  # No more entries found

        page += 1

    return crc32_to_link


def calculate_local_crc32(folder):
    local_crc32s = set()
    for root, dirs, files in os.walk(folder):
        for file in files:
            if os.path.splitext(file)[1].lower() in VIDEO_EXTENSIONS:
                file_path = os.path.join(root, file)
                print(f"Calculating CRC32 for {file_path}...")
                with open(file_path, "rb") as f:
                    crc = 0
                    while chunk := f.read(8192):
                        crc = zlib.crc32(chunk, crc)
                    local_crc32s.add(f"{crc & 0xFFFFFFFF:08X}")
    return local_crc32s


def main():
    parser = argparse.ArgumentParser(
        description="Find missing CRC32 links from Nyaa.si."
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Base URL without the page param. Example: 'https://nyaa.si/?f=0&c=0_0&q=one+pace&s=id&o=asc' ",
    )
    parser.add_argument(
        "--folder", required=True, help="Folder containing local video files."
    )
    args = parser.parse_args()

    crc32_to_link = fetch_crc32_links(args.url)
    print(f"Found {len(crc32_to_link)} CRC32 entries from site.")

    local_crc32s = calculate_local_crc32(args.folder)
    print(f"Found {len(local_crc32s)} local CRC32 hashes.")

    missing = [
        link for crc32, link in crc32_to_link.items() if crc32 not in local_crc32s
    ]

    print("\nMissing files:")
    for link in missing:
        print(link)


if __name__ == "__main__":
    main()
