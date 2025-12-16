import abc
import getpass
import time
import requests
import qbittorrentapi
import re

class Client(abc.ABC):
    @abc.abstractmethod
    def add_torrents(self, torrents, download_folder=None, tags=None, category=None):
        pass

class QBittorrentClient(Client):
    def __init__(self, host, port, username, password):
        self.client = qbittorrentapi.Client(
            host=host,
            port=port,
            username=username,
            password=password
        )
        try:
            self.client.auth_log_in()
        except qbittorrentapi.LoginFailed as e:
            raise Exception(f"Failed to connect to qBittorrent: {e}") from e
        print("Connection to qBittorrent successful!")

    def add_torrents(self, magnets, download_folder=None, tags=None, category=None):
        if tags:
            self.client.torrents_create_tags(tags=",".join(tags))

        added_count = 0
        total = len(magnets)
        tags_str = ",".join(tags) if tags else None
        for idx, magnet in enumerate(magnets, 1):
            truncated = magnet[:50] + ("..." if len(magnet) > 50 else "")
            print(f"Processing {idx}/{total}: {truncated}")

            # Extract info hash from magnet link
            match = re.search(r"xt=urn:btih:([a-fA-F0-9]{40})", magnet)
            if not match:
                print(f"Could not find info hash in magnet link: {truncated}")
                continue

            info_hash = match.group(1).lower()

            # Check if torrent already exists
            existing_torrent = self.client.torrents_info(torrent_hashes=info_hash)

            if existing_torrent:
                print(f"Torrent {truncated} already exists.")
                if tags:
                    print(f"Adding tags to existing torrent: {tags_str}")
                    self.client.torrents_add_tags(tags=tags_str, torrent_hashes=info_hash)
            else:
                print(f"Adding new torrent: {truncated}")
                try:
                    self.client.torrents_add(
                        urls=magnet,
                        save_path=download_folder if download_folder else None,
                        tags=tags_str,
                        category=category,
                    )
                    added_count += 1
                except Exception as e:
                    print(f"Failed to add torrent: {truncated} Error: {e}")
            time.sleep(0.1)
        print(f"Added {added_count} new torrents to qBittorrent.")


class TransmissionClient(Client):
    def __init__(self, host, port, username, password):
        self.base_url = f"http://{host}:{port}/transmission/rpc"
        self.session_id = None
        self.session = requests.Session()
        self.auth = (username, password) if username else None

        # Test connection and get session ID
        try:
            headers = {}
            if self.session_id:
                headers["X-Transmission-Session-Id"] = self.session_id
            resp = self.session.post(
                self.base_url, auth=self.auth, headers=headers, json={"method": "session-get"}
            )
            if resp.status_code == 409:
                self.session_id = resp.headers.get("X-Transmission-Session-Id")
                headers["X-Transmission-Session-Id"] = self.session_id
                resp = self.session.post(
                    self.base_url, auth=self.auth, headers=headers, json={"method": "session-get"}
                )
            resp.raise_for_status()
        except Exception as e:
            raise Exception(f"Failed to connect to Transmission RPC: {e}") from e

        print("Connection to Transmission successful!")
        self.session_info = resp.json()


    def add_torrents(self, magnets, download_folder=None, tags=None, category=None):
        if tags or category:
            print("Warning: Transmission does not support tags or categories through this script.")
        added_count = 0
        total = len(magnets)
        for idx, magnet in enumerate(magnets, 1):
            truncated = magnet[:50] + ("..." if len(magnet) > 50 else "")
            print(f"Adding {idx}/{total}: {truncated}")
            payload = {"method": "torrent-add", "arguments": {"filename": magnet}}
            if download_folder:
                payload["arguments"]["download-dir"] = download_folder
            try:
                headers = {"X-Transmission-Session-Id": self.session_id} if self.session_id else {}
                resp = self.session.post(self.base_url, auth=self.auth, headers=headers, json=payload)
                if resp.status_code == 409:
                    self.session_id = resp.headers.get("X-Transmission-Session-Id")
                    headers["X-Transmission-Session-Id"] = self.session_id
                    resp = self.session.post(self.base_url, auth=self.auth, headers=headers, json=payload)
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


def get_client(client_name, host, port, username, password):
    if client_name == 'qbittorrent':
        return QBittorrentClient(host, port, username, password)
    elif client_name == 'transmission':
        return TransmissionClient(host, port, username, password)
    else:
        raise ValueError(f'Unknown client: {client_name}')
