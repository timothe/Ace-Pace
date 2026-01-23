import abc
import getpass
import time
import requests  # type: ignore
import qbittorrentapi  # type: ignore
import re

class Client(abc.ABC):
    @abc.abstractmethod
    def add_torrents(self, magnets, download_folder=None, tags=None, category=None):
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
            raise ConnectionError(f"Failed to authenticate with qBittorrent at {host}:{port}: {e}") from e
        except qbittorrentapi.APIConnectionError as e:
            raise ConnectionError(f"Failed to connect to qBittorrent at {host}:{port}. Check if the client is running and accessible: {e}") from e
        except qbittorrentapi.APIError as e:
            raise ConnectionError(f"qBittorrent API error at {host}:{port}: {e}") from e
        except Exception as e:
            raise ConnectionError(f"Unexpected error connecting to qBittorrent at {host}:{port}: {e}") from e
        print("Connection to qBittorrent successful!")

    def _extract_info_hash(self, magnet):
        """Extract info hash from magnet link."""
        match = re.search(r"xt=urn:btih:([a-fA-F0-9]{40})", magnet)
        if not match:
            return None
        return match.group(1).lower()

    def _handle_existing_torrent(self, info_hash, tags_str, truncated):
        """Handle case when torrent already exists."""
        print(f"Torrent {truncated} already exists.")
        if tags_str:
            print(f"Adding tags to existing torrent: {tags_str}")
            self.client.torrents_add_tags(tags=tags_str, torrent_hashes=info_hash)

    def _add_new_torrent(self, magnet, download_folder, tags_str, category, truncated):
        """Add a new torrent to qBittorrent."""
        print(f"Adding new torrent: {truncated}")
        try:
            self.client.torrents_add(
                urls=magnet,
                save_path=download_folder if download_folder else None,
                tags=tags_str,
                category=category,
            )
            return True
        except Exception as e:
            print(f"Failed to add torrent: {truncated} Error: {e}")
            return False

    def add_torrents(self, magnets, download_folder=None, tags=None, category=None):
        if tags:
            self.client.torrents_create_tags(tags=",".join(tags))

        added_count = 0
        total = len(magnets)
        tags_str = ",".join(tags) if tags else None
        for idx, magnet in enumerate(magnets, 1):
            truncated = magnet[:50] + ("..." if len(magnet) > 50 else "")
            print(f"Processing {idx}/{total}: {truncated}")

            info_hash = self._extract_info_hash(magnet)
            if not info_hash:
                print(f"Could not find info hash in magnet link: {truncated}")
                continue

            existing_torrent = self.client.torrents_info(torrent_hashes=info_hash)
            if existing_torrent:
                self._handle_existing_torrent(info_hash, tags_str, truncated)
            else:
                if self._add_new_torrent(magnet, download_folder, tags_str, category, truncated):
                    added_count += 1
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
                new_session_id = resp.headers.get("X-Transmission-Session-Id")
                if new_session_id:
                    self.session_id = new_session_id
                    headers["X-Transmission-Session-Id"] = self.session_id
                    resp = self.session.post(
                        self.base_url, auth=self.auth, headers=headers, json={"method": "session-get"}
                    )
            resp.raise_for_status()
        except requests.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to Transmission at {host}:{port}. Check if the client is running and accessible: {e}") from e
        except requests.Timeout as e:
            raise ConnectionError(f"Connection to Transmission at {host}:{port} timed out: {e}") from e
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to connect to Transmission RPC at {host}:{port}: {e}") from e
        except ValueError as e:
            raise ConnectionError(f"Invalid response from Transmission at {host}:{port}: {e}") from e

        print("Connection to Transmission successful!")
        self.session_info = resp.json()


    def _make_rpc_request(self, payload):
        """Make an RPC request to Transmission, handling session ID updates."""
        headers = {"X-Transmission-Session-Id": self.session_id} if self.session_id else {}
        resp = self.session.post(self.base_url, auth=self.auth, headers=headers, json=payload)
        if resp.status_code == 409:
            new_session_id = resp.headers.get("X-Transmission-Session-Id")
            if new_session_id:
                self.session_id = new_session_id
                headers["X-Transmission-Session-Id"] = self.session_id
                resp = self.session.post(self.base_url, auth=self.auth, headers=headers, json=payload)
        return resp

    def _add_single_torrent(self, magnet, download_folder, truncated):
        """Add a single torrent to Transmission."""
        payload = {"method": "torrent-add", "arguments": {"filename": magnet}}
        if download_folder:
            payload["arguments"]["download-dir"] = download_folder
        try:
            resp = self._make_rpc_request(payload)
            resp.raise_for_status()
            result = resp.json()
            if result.get("result") == "success":
                return True
            print(f"Failed to add torrent: {truncated} Error: {result.get('result')}")
            return False
        except Exception as e:
            print(f"Failed to add torrent: {truncated} Error: {e}")
            return False

    def add_torrents(self, magnets, download_folder=None, tags=None, category=None):
        if tags or category:
            print("Warning: Transmission does not support tags or categories through this script.")
        added_count = 0
        total = len(magnets)
        for idx, magnet in enumerate(magnets, 1):
            truncated = magnet[:50] + ("..." if len(magnet) > 50 else "")
            print(f"Adding {idx}/{total}: {truncated}")
            if self._add_single_torrent(magnet, download_folder, truncated):
                added_count += 1
            time.sleep(0.1)
        print(f"Added {added_count} torrents to Transmission.")


def get_client(client_name, host, port, username, password):
    if client_name == 'qbittorrent':
        return QBittorrentClient(host, port, username, password)
    elif client_name == 'transmission':
        return TransmissionClient(host, port, username, password)
    else:
        raise ValueError(f'Unknown client: {client_name}')
