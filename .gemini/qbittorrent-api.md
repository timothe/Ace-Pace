### Install qBittorrent API

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/README.md

Installs the qBittorrent API client library using pip.

```bash
python -m pip install qbittorrent-api
```

--------------------------------

### Install qbittorrent-api via pip

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/introduction.rst

Installs the qbittorrent-api package from PyPI using pip. This is the standard method for installing Python packages.

```console
python -m pip install qbittorrent-api
```

--------------------------------

### Install qbittorrent-api from main branch

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/introduction.rst

Installs the qbittorrent-api package directly from the main branch of the GitHub repository. This is useful for accessing the latest development features or bug fixes.

```console
pip install git+https://github.com/rmartin16/qbittorrent-api.git@main#egg=qbittorrent-api
```

--------------------------------

### Install a specific qbittorrent-api version

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/introduction.rst

Installs a specific version of the qbittorrent-api package from PyPI. Useful for ensuring compatibility with older projects or testing specific releases.

```console
python -m pip install qbittorrent-api==2024.3.60
```

--------------------------------

### Full Async Example with qbittorrent-api

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/async.rst

A complete example showing how to initialize the qbittorrentapi client and fetch application build information asynchronously using `asyncio.to_thread`. This code can be run in the Python REPL.

```python
import asyncio
import qbittorrentapi

qbt_client = qbittorrentapi.Client()

async def fetch_qbt_info():
    return await asyncio.to_thread(qbt_client.app_build_info)

print(asyncio.run(fetch_qbt_info()))
```

--------------------------------

### qBittorrent Web API Reference

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/README.md

Provides an overview of the qBittorrent Web API, detailing its version compatibility and features. It also links to comprehensive user guides and API references.

```APIDOC
qBittorrent Web API Client

Project: /rmartin16/qbittorrent-api

Description:
Python client implementation for qBittorrent Web API.
Supports qBittorrent versions up to v5.1.2 (Web API v2.11.4).
Features:
- Implements the entire qBittorrent Web API.
- Automatically handles qBittorrent version checking for endpoint support.
- Automatically requests a new authentication cookie if the current one expires.

Resources:
- User Guide and API Reference: https://qbittorrent-api.readthedocs.io/
- qBittorrent GitHub Wiki (Web API): https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)

API Endpoints Overview:
(Note: Specific endpoint details are extensive and found in the linked documentation. This section summarizes the scope.)
- Application Information: Retrieve details about the qBittorrent application, including version, build info, and Web API version.
- Authentication: Log in, log out, and manage authentication cookies.
- Torrents Management:
    - Add torrents (by URL or content).
    - Retrieve torrent information (all, by hash, by state).
    - Control torrent states (start, stop, pause, resume, delete).
    - Manage torrent content (select/deselect files).
    - Set torrent properties (download/upload limits, priority, category).
- Downloads Management:
    - Control download limits.
- Peers Management:
    - Retrieve peer information for torrents.
- Trackers Management:
    - Update trackers for torrents.
- Search Management:
    - Initiate and retrieve search results.
- Filters Management:
    - Manage torrent filters.
- Tags Management:
    - Manage tags for torrents.
- Options Management:
    - Retrieve and modify qBittorrent settings.
- Web Server Management:
    - Control the Web Server.
- RSS Feed Management:
    - Manage RSS feeds.
- Transfer List Management:
    - Control transfer list operations.

Error Handling:
- Handles `qbittorrentapi.LoginFailed` for authentication errors.
- Automatically retries authentication on expiration.
```

--------------------------------

### SearchPluginsList

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/search.rst

Represents a list of installed search plugins. This structure allows for managing and querying the available search plugins within qBittorrent.

```APIDOC
qbittorrentapi.search.SearchPluginsList:
    __init__(...)
        Initializes the SearchPluginsList.

    # Members are typically SearchPlugin objects, each representing an installed search plugin.
```

--------------------------------

### SearchPlugin

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/search.rst

Represents a single installed search plugin, providing details about its name, version, and status. This is used to manage and interact with individual search plugins.

```APIDOC
qbittorrentapi.search.SearchPlugin:
    __init__(...)
        Initializes the SearchPlugin.

    # Attributes typically include:
    # - name (str): The name of the search plugin.
    # - version (str): The version of the search plugin.
    # - enabled (bool): Whether the plugin is currently enabled.
```

--------------------------------

### Basic qbittorrent-api Client Usage

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/introduction.rst

Demonstrates the basic usage of the qbittorrentapi Client, including instantiation, login, logout, and retrieving application information.

```python
import qbittorrentapi

# instantiate a Client using the appropriate WebUI configuration
conn_info = dict(
    host="localhost",
    port=8080,
    username="admin",
    password="adminadmin",
)
qbt_client = qbittorrentapi.Client(**conn_info)

# the Client will automatically acquire/maintain a logged-in state
# in line with any request. therefore, this is not strictly necessary;
# however, you may want to test the provided login credentials.
try:
    qbt_client.auth_log_in()
except qbittorrentapi.LoginFailed as e:
    print(e)

# if the Client will not be long-lived or many Clients may be created
# in a relatively short amount of time, be sure to log out:
qbt_client.auth_log_out()

# or use a context manager:
with qbittorrentapi.Client(**conn_info) as qbt_client:
    if qbt_client.torrents_add(urls="...") != "Ok.":
        raise Exception("Failed to add torrent.")

# display qBittorrent info
print(f"qBittorrent: {qbt_client.app.version}")
print(f"qBittorrent Web API: {qbt_client.app.web_api_version}")
for k, v in qbt_client.app.build_info.items():
    print(f"{k}: {v}")

# retrieve and show all torrents
for torrent in qbt_client.torrents_info():
    print(f"{torrent.hash[-6:]}: {torrent.name} ({torrent.state})")

# stop all torrents
qbt_client.torrents.stop.all()
```

--------------------------------

### Client Instantiation with Credentials

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/behavior&configuration.rst

Demonstrates how to instantiate the qbittorrentapi.client.Client with host, username, and password.

```python
from qbittorrentapi import Client

qbt_client = Client(host="localhost:8080", username='...', password='...')
```

--------------------------------

### qBittorrent Client Initialization and Torrent Management

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/introduction.rst

Demonstrates how to initialize the qBittorrent client and iterate through active torrents to perform common operations like setting location, reannouncing, and adjusting upload limits.

```python
import qbittorrentapi

qbt_client = qbittorrentapi.Client(host='localhost:8080', username='admin', password='adminadmin')

for torrent in qbt_client.torrents.info.active():
    torrent.set_location(location='/home/user/torrents/')
    torrent.reannounce()
    torrent.upload_limit = -1
```

--------------------------------

### Configuring HTTPAdapter Arguments

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/behavior&configuration.rst

Illustrates setting arguments for the requests.Session.HTTPAdapter during client instantiation using the HTTPADAPTER_ARGS parameter.

```python
from qbittorrentapi import Client

qbt_client = Client(host="localhost:8080", username='...', password='...', HTTPADAPTER_ARGS={"pool_connections": 100, "pool_maxsize": 100})
```

--------------------------------

### qbittorrentapi.client.Client API

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/client.rst

Provides comprehensive documentation for the Client class, including its methods for authentication, torrent management, and client configuration. This serves as the main entry point for interacting with the qBittorrent Web API.

```APIDOC
Client:
  __init__(host: str, port: int = 8080, username: str = None, password: str = None, **kwargs)
    Initializes the qBittorrent API client.
    Parameters:
      host: The hostname or IP address of the qBittorrent instance.
      port: The port number for the Web UI (default is 8080).
      username: The username for authentication.
      password: The password for authentication.
      **kwargs: Additional keyword arguments for advanced configuration.

  auth_log_in()
    Logs into the qBittorrent Web API.
    Returns: True if login is successful, False otherwise.

  auth_log_out()
    Logs out of the qBittorrent Web API.
    Returns: True if logout is successful, False otherwise.

  get_torrent_list(status_filter: str = 'all', category: str = None, tag: str = None, sort: str = 'name', reverse: bool = False) -> list
    Retrieves a list of torrents.
    Parameters:
      status_filter: Filter torrents by status (e.g., 'downloading', 'completed', 'paused', 'all').
      category: Filter torrents by category.
      tag: Filter torrents by tag.
      sort: Field to sort torrents by (e.g., 'name', 'size', 'progress').
      reverse: If True, sort in descending order.
    Returns: A list of torrent dictionaries.

  add_torrent(torrent_files: list, urls: list = None, save_path: str = None, category: str = None, tags: str = None, is_paused: bool = False)
    Adds one or more torrents to qBittorrent.
    Parameters:
      torrent_files: A list of torrent file contents (bytes).
      urls: A list of magnet links or URLs to .torrent files.
      save_path: The directory to save the torrents.
      category: The category to assign to the torrents.
      tags: Comma-separated string of tags to assign.
      is_paused: If True, the torrents will be added in a paused state.

  pause_torrent(torrent_hash: str)
    Pauses a specific torrent.
    Parameters:
      torrent_hash: The hash of the torrent to pause.

  resume_torrent(torrent_hash: str)
    Resumes a paused torrent.
    Parameters:
      torrent_hash: The hash of the torrent to resume.

  delete_torrent(torrent_hash: str, delete_files: bool = False)
    Deletes a torrent.
    Parameters:
      torrent_hash: The hash of the torrent to delete.
      delete_files: If True, also deletes the torrent's data files.

  get_app_preferences() -> dict
    Retrieves the application preferences.
    Returns: A dictionary containing application settings.

  set_app_preferences(prefs: dict)
    Sets the application preferences.
    Parameters:
      prefs: A dictionary of preferences to update.

  get_connection_status() -> dict
    Retrieves the connection status of the client.
    Returns: A dictionary with connection status information.

  shutdown_client()
    Shuts down the qBittorrent client.

  reboot_client()
    Reboots the qBittorrent client.

  get_web_api_version() -> str
    Retrieves the version of the Web API.
    Returns: The Web API version string.
```

--------------------------------

### qbittorrentapi.app.Application Methods

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/app.rst

Represents the qBittorrent application and exposes methods for managing its settings, preferences, and retrieving information like build details and network interfaces.

```APIDOC
qbittorrentapi.app.Application:
    Manages qBittorrent application settings and retrieves information.
    Excludes methods like app, application, webapiVersion, buildInfo, setPreferences, defaultSavePath, setCookies, networkInterfaceAddressList, networkInterfaceList, sendTestEmail, getDirectoryContent.
```

--------------------------------

### qBittorrent API Client Usage

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/README.md

Demonstrates how to instantiate a qBittorrent API client, log in, log out, and interact with various API endpoints like adding torrents, retrieving application info, and managing torrent states.

```python
import qbittorrentapi

# instantiate a Client using the appropriate WebUI configuration
conn_info = dict(
    host="localhost",
    port=8080,
    username="admin",
    password="adminadmin",
)
qbt_client = qbittorrentapi.Client(**conn_info)

# the Client will automatically acquire/maintain a logged-in state
# in line with any request. therefore, this is not strictly necessary;
# however, you may want to test the provided login credentials.
try:
    qbt_client.auth_log_in()
except qbittorrentapi.LoginFailed as e:
    print(e)

# if the Client will not be long-lived or many Clients may be created
# in a relatively short amount of time, be sure to log out:
qbt_client.auth_log_out()

# or use a context manager:
with qbittorrentapi.Client(**conn_info) as qbt_client:
    if qbt_client.torrents_add(urls="...") != "Ok.":
        raise Exception("Failed to add torrent.")

# display qBittorrent info
print(f"qBittorrent: {qbt_client.app.version}")
print(f"qBittorrent Web API: {qbt_client.app.web_api_version}")
for k, v in qbt_client.app.build_info.items():
    print(f"{k}: {v}")

# retrieve and show all torrents
for torrent in qbt_client.torrents_info():
    print(f"{torrent.hash[-6:]}: {torrent.name} ({torrent.state})")

# stop all torrents
qbt_client.torrents.stop.all()
```

--------------------------------

### qbittorrentapi.app.BuildInfoDictionary

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/app.rst

Represents a dictionary containing build information for the qBittorrent application.

```APIDOC
qbittorrentapi.app.BuildInfoDictionary:
    Dictionary structure for qBittorrent build information.
```

--------------------------------

### Namespace-Based Interaction with Web API

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/introduction.rst

Demonstrates a more organized and intuitive way to interact with the qBittorrent Web API using namespaces, allowing for easier management of preferences and torrent operations.

```python
import qbittorrentapi
qbt_client = qbittorrentapi.Client(host='localhost:8080', username='admin', password='adminadmin')
# changing a preference
is_dht_enabled = qbt_client.app.preferences.dht
qbt_client.app.preferences = dict(dht=not is_dht_enabled)
# stopping all torrents
qbt_client.torrents.stop.all()
# retrieve different views of the log
qbt_client.log.main.warning()
```

--------------------------------

### Direct Method Calls for Web API Endpoints

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/introduction.rst

Illustrates how to interact with the qBittorrent Web API by directly calling methods on the client object, corresponding to individual API endpoints.

```python
import qbittorrentapi
qbt_client = qbittorrentapi.Client(host='localhost:8080', username='admin', password='adminadmin')
qbt_client.app_version()
qbt_client.rss_rules()
qbt_client.torrents_info()
qbt_client.torrents_resume(torrent_hashes='...')
# and so on
```

--------------------------------

### Client Authentication with auth_log_in

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/behavior&configuration.rst

Shows how to explicitly log in a client instance using username and password. Authentication happens automatically for API requests.

```python
qbt_client.auth_log_in(username='...', password='...')
```

--------------------------------

### Instantiate Client with Simple Responses

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/performance.rst

Demonstrates how to instantiate the qbittorrentapi client with the SIMPLE_RESPONSES flag set to True to always receive simple JSON responses, improving performance by avoiding complex object conversions.

```python
import qbittorrentapi

qbt_client = qbittorrentapi.Client(
    host='localhost:8080',
    username='admin',
    password='adminadmin',
    SIMPLE_RESPONSES=True,
)
```

--------------------------------

### qbittorrentapi.app.AppAPIMixIn Methods

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/app.rst

Provides methods for interacting with the qBittorrent application's API. This class serves as a mixin for application-related functionalities.

```APIDOC
qbittorrentapi.app.AppAPIMixIn:
    Methods related to application settings and information.
```

--------------------------------

### qbittorrentapi.sync.Sync Documentation

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/sync.rst

Documentation for the Sync class, which handles synchronization operations. It includes all members, undocumented members, and the special '__call__' member.

```APIDOC
qbittorrentapi.sync.Sync
    :members:
    :undoc-members:
    :special-members: __call__
```

--------------------------------

### qbittorrentapi.app.ApplicationPreferencesDictionary

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/app.rst

Represents a dictionary for application preferences in qBittorrent.

```APIDOC
qbittorrentapi.app.ApplicationPreferencesDictionary:
    Dictionary structure for qBittorrent application preferences.
```

--------------------------------

### qbittorrentapi.sync.SyncAPIMixIn Documentation

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/sync.rst

Documentation for the SyncAPIMixIn class, which provides synchronization-related methods. It excludes 'sync' and 'sync_torrentPeers' members and shows inheritance.

```APIDOC
qbittorrentapi.sync.SyncAPIMixIn
    :members:
    :undoc-members:
    :exclude-members: sync, sync_torrentPeers
    :show-inheritance:
```

--------------------------------

### SearchAPIMixIn Class

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/search.rst

Provides search-related functionalities for interacting with qBittorrent's search engine. It includes methods for initiating searches, managing plugins, and retrieving search results. Excludes specific methods that might be handled by a base class or are internal.

```APIDOC
qbittorrentapi.search.SearchAPIMixIn:
    __init__(...)
        Initializes the SearchAPIMixIn class.

    search(pattern: str, **kwargs) -> SearchResultsDictionary
        Searches for torrents matching the given pattern.
        Parameters:
            pattern (str): The search query string.
            **kwargs: Additional keyword arguments for search options (e.g., category, limit).
        Returns:
            SearchResultsDictionary: A dictionary containing the search results.

    search_installPlugin(url: str)
        Installs a search plugin from the given URL.
        Parameters:
            url (str): The URL of the search plugin to install.

    search_uninstallPlugin(name: str)
        Uninstalls a search plugin by its name.
        Parameters:
            name (str): The name of the search plugin to uninstall.

    search_enablePlugin(name: str)
        Enables a search plugin by its name.
        Parameters:
            name (str): The name of the search plugin to enable.

    search_updatePlugins()
        Updates all installed search plugins.

    search_downloadTorrent(file_url: str, save_path: str, **kwargs)
        Downloads a torrent file from the given URL.
        Parameters:
            file_url (str): The URL of the torrent file.
            save_path (str): The path where the torrent should be saved.
            **kwargs: Additional keyword arguments for download options.
```

--------------------------------

### Configuring Request Timeouts

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/behavior&configuration.rst

Demonstrates setting request timeouts for all HTTP requests made by the client using the REQUESTS_ARGS parameter during instantiation.

```python
from qbittorrentapi import Client

qbt_client = Client(host="localhost:8080", username='...', password='...', REQUESTS_ARGS={'timeout': (3.1, 30)})
```

--------------------------------

### Context Manager for Session Management

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/behavior&configuration.rst

Illustrates using a context manager with qbittorrentapi.Client for proper session handling, ensuring the client is logged in and managing session expiration.

```python
import qbittorrentapi

conn_info = {
    "host": "localhost:8080",
    "username": "...",
    "password": "..."
}

with qbittorrentapi.Client(**conn_info) as qbt_client:
    if qbt_client.torrents_add(urls="...") != "Ok.":
        raise Exception("Failed to add torrent.")
```

--------------------------------

### Handle Unsupported qBittorrent Versions

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/behavior&configuration.rst

Configure the client to raise an UnsupportedQbittorrentVersion exception for qBittorrent hosts with versions not fully supported by the client. This ensures compatibility with the client's features.

```python
from qbittorrentapi import Client

qbt_client = Client(..., RAISE_ERROR_FOR_UNSUPPORTED_QBITTORRENT_VERSIONS=True)
```

--------------------------------

### qbittorrentapi.auth.AuthAPIMixIn

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/auth.rst

Provides authentication methods for interacting with the qBittorrent API. It includes methods for logging in and out, and managing authentication state. Inherits from object.

```APIDOC
qbittorrentapi.auth.AuthAPIMixIn
  __init__(self, auth_client)
    Initializes the AuthAPIMixIn with an authentication client.
    Parameters:
      auth_client: The client responsible for authentication.

  login(self, username, password, **kwargs)
    Logs into the qBittorrent Web API.
    Parameters:
      username (str): The username for authentication.
      password (str): The password for authentication.
      **kwargs: Additional keyword arguments for login.
    Returns: True if login is successful, False otherwise.

  logout(self)
    Logs out of the qBittorrent Web API.
    Returns: True if logout is successful, False otherwise.

  is_logged_in(self)
    Checks if the client is currently logged in.
    Returns: True if logged in, False otherwise.

  is_logged_out(self)
    Checks if the client is currently logged out.
    Returns: True if logged out, False otherwise.
```

--------------------------------

### qbittorrent-api Documentation Structure

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/api.rst

This section outlines the structure of the API documentation, indicating that detailed API documentation can be found within the 'apidoc/' directory. It uses a Sphinx toctree directive to organize the documentation.

```APIDOC
.. toctree::
    :maxdepth: 2
    :glob:

    apidoc/*
```

--------------------------------

### Set Simple Responses for Individual Method Call

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/performance.rst

Shows how to override the default behavior and request a simple JSON response for a specific method call by passing SIMPLE_RESPONSES=True as an argument.

```python
qbt_client.torrents.files(torrent_hash='...', SIMPLE_RESPONSES=True)
```

--------------------------------

### qbittorrentapi.sync.SyncTorrentPeersDictionary Documentation

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/sync.rst

Documentation for the SyncTorrentPeersDictionary class, used for representing synchronized torrent peers data. It includes all members, undocumented members, and shows inheritance.

```APIDOC
qbittorrentapi.sync.SyncTorrentPeersDictionary
    :members:
    :undoc-members:
    :show-inheritance:
```

--------------------------------

### Instantiating qBittorrent API Client with Sub-Path (Python)

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/CHANGELOG.md

This snippet demonstrates how to instantiate the qBittorrent API client when the qBittorrent Web API is accessible via a sub-path (e.g., behind a reverse proxy). It shows passing the combined host and sub-path to the `host` parameter of the `Client` constructor. This ensures that all API requests are correctly prefixed with the specified path.

```Python
Client(host='localhost/qbt')
```

--------------------------------

### qbittorrentapi.app.NetworkInterfaceList

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/app.rst

Represents a list of network interfaces available on the qBittorrent client.

```APIDOC
qbittorrentapi.app.NetworkInterfaceList:
    List structure for network interfaces in qBittorrent.
```

--------------------------------

### qbittorrentapi.sync.SyncMainDataDictionary Documentation

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/sync.rst

Documentation for the SyncMainDataDictionary class, used for representing synchronized main data. It lists all members, including undocumented ones, and shows inheritance.

```APIDOC
qbittorrentapi.sync.SyncMainDataDictionary
    :members:
    :undoc-members:
    :show-inheritance:
```

--------------------------------

### Handling Untrusted Certificates

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/behavior&configuration.rst

Explains how to instantiate the Client with VERIFY_WEBUI_CERTIFICATE=False to handle untrusted or self-signed certificates, disabling certificate verification.

```python
from qbittorrentapi import Client

qbt_client = Client(host="localhost:8080", username='...', password='...', VERIFY_WEBUI_CERTIFICATE=False)
```

--------------------------------

### qbittorrentapi.app.DirectoryContentList

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/app.rst

Represents a list of directory content items returned by the qBittorrent API.

```APIDOC
qbittorrentapi.app.DirectoryContentList:
    List structure for directory content in qBittorrent.
```

--------------------------------

### Adding Custom HTTP Headers during Instantiation

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/behavior&configuration.rst

Demonstrates how to include custom HTTP headers in all requests made by an instantiated client by using the EXTRA_HEADERS parameter.

```python
from qbittorrentapi import Client

qbt_client = Client(host="localhost:8080", username='...', password='...', EXTRA_HEADERS={'X-My-Fav-Header': 'header value'})
```

--------------------------------

### qbittorrentapi.app.NetworkInterface

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/app.rst

Represents a single network interface on the qBittorrent client.

```APIDOC
qbittorrentapi.app.NetworkInterface:
    Represents a single network interface.
```

--------------------------------

### qbittorrentapi.request Module Documentation

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/request.rst

This section details the members, private members, undocumented members, and inheritance of the qbittorrentapi.request module. It serves as a comprehensive reference for interacting with the request functionalities within the library.

```python
.. automodule:: qbittorrentapi.request
    :members:
    :private-members:
    :undoc-members:
    :show-inheritance:
```

--------------------------------

### LogEntry Class

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/log.rst

Represents a single entry within the qBittorrent log. This class inherits from a base class, exposing all its members and undocumented members.

```APIDOC
qbittorrentapi.log.LogEntry
  :members:
  :undoc-members:
  :show-inheritance:
```

--------------------------------

### AttrDict Class Documentation

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/attrdict.rst

Provides documentation for the AttrDict class, detailing its members, undocumented members, and inheritance. AttrDict is an internal class for the qbittorrent-api library.

```python
.. autoclass:: qbittorrentapi._attrdict.AttrDict
    :members:
    :undoc-members:
    :show-inheritance:
```

--------------------------------

### Handle Unimplemented API Endpoints

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/behavior&configuration.rst

Configure the client to raise a NotImplementedError for API endpoints that are not supported by the host's qBittorrent version. This is useful for early detection of compatibility issues.

```python
from qbittorrentapi import Client

qbt_client = Client(..., RAISE_NOTIMPLEMENTEDERROR_FOR_UNIMPLEMENTED_API_ENDPOINTS=True)
```

--------------------------------

### qBittorrent API - Torrent Operations

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/introduction.rst

Provides an overview of the methods available for managing torrents through the qBittorrent API client. This includes setting download/upload limits, reannouncing, and changing the save location.

```APIDOC
qbt_client.torrents.info.active()
  - Retrieves a list of currently active torrents.
  - Returns: A list of TorrentInfo objects.

TorrentInfo.set_location(location: str)
  - Sets the save location for a specific torrent.
  - Parameters:
    - location: The new directory path to save the torrent content.
  - Returns: None.

TorrentInfo.reannounce()
  - Forces a reannounce for the torrent.
  - Returns: None.

TorrentInfo.upload_limit
  - Gets or sets the upload speed limit for the torrent.
  - Type: int
  - Description: Set to -1 for unlimited upload speed.
```

--------------------------------

### qbittorrentapi._version_support.Version Class

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/version.rst

Provides details on the Version class, its members, and undocumented members related to version support in the qbittorrent-api library. This class is crucial for ensuring compatibility between the client and the qBittorrent client.

```APIDOC
qbittorrentapi._version_support.Version:
    Represents and validates qBittorrent versions.

    Methods:
        __init__(self, version_string: str)
            Initializes the Version object with a version string.
            Parameters:
                version_string (str): The qBittorrent version string (e.g., "4.4.0").

        __str__(self) -> str
            Returns the string representation of the version.

        __repr__(self) -> str
            Returns the detailed representation of the Version object.

        __eq__(self, other)
            Checks if this version is equal to another Version object or string.
            Parameters:
                other (Version | str): The version to compare against.
            Returns:
                bool: True if versions are equal, False otherwise.

        __ne__(self, other)
            Checks if this version is not equal to another Version object or string.
            Parameters:
                other (Version | str): The version to compare against.
            Returns:
                bool: True if versions are not equal, False otherwise.

        __lt__(self, other)
            Checks if this version is less than another Version object or string.
            Parameters:
                other (Version | str): The version to compare against.
            Returns:
                bool: True if this version is less than the other, False otherwise.

        __le__(self, other)
            Checks if this version is less than or equal to another Version object or string.
            Parameters:
                other (Version | str): The version to compare against.
            Returns:
                bool: True if this version is less than or equal to the other, False otherwise.

        __gt__(self, other)
            Checks if this version is greater than another Version object or string.
            Parameters:
                other (Version | str): The version to compare against.
            Returns:
                bool: True if this version is greater than the other, False otherwise.

        __ge__(self, other)
            Checks if this version is greater than or equal to another Version object or string.
            Parameters:
                other (Version | str): The version to compare against.
            Returns:
                bool: True if this version is greater than or equal to the other, False otherwise.

        is_at_least(self, required_version: str) -> bool
            Checks if the current version is at least the required version.
            Parameters:
                required_version (str): The minimum required version string.
            Returns:
                bool: True if the version meets the requirement, False otherwise.

    Undocumented Members:
        _version_tuple (tuple): Internal representation of the version as a tuple of integers.
```

--------------------------------

### qbittorrentapi.transfer.TransferInfoDictionary

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/transfer.rst

Documentation for the TransferInfoDictionary class, which represents information related to transfers. This class inherits from other classes and includes various members that provide detailed transfer status and data.

```APIDOC
TransferInfoDictionary:
  Represents transfer information.
  Includes members for detailed transfer status.
```

--------------------------------

### qbittorrentapi.transfer.TransferAPIMixIn Methods

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/transfer.rst

This section documents the methods available in the TransferAPIMixIn class, which provides core transfer management functionalities. It excludes specific methods related to speed limits and peer banning, which are detailed elsewhere.

```APIDOC
TransferAPIMixIn:
  Methods related to general transfer management.
```

--------------------------------

### Attr Class Documentation

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/attrdict.rst

Provides documentation for the Attr class, detailing its members, undocumented members, and inheritance. Attr is an internal class for the qbittorrent-api library.

```python
.. autoclass:: qbittorrentapi._attrdict.Attr
    :members:
    :undoc-members:
    :show-inheritance:
```

--------------------------------

### LogMainList Class

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/log.rst

Represents the main list structure for log entries. This class inherits from a base class, exposing all its members and undocumented members.

```APIDOC
qbittorrentapi.log.LogMainList
  :members:
  :undoc-members:
  :show-inheritance:
```

--------------------------------

### Adding Custom HTTP Headers for Individual Requests

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/behavior&configuration.rst

Shows how to send custom HTTP headers for specific API calls using the headers parameter.

```python
qbt_client.torrents.add(headers={'X-My-Fav-Header': 'header value'})
```

--------------------------------

### Search Class

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/search.rst

Represents the core search functionality in qBittorrent. This class likely encapsulates the logic for executing searches and managing search-related operations. It excludes methods related to plugin management, which are handled by SearchAPIMixIn.

```APIDOC
qbittorrentapi.search.Search:
    __init__(...)
        Initializes the Search class.

    installPlugin(url: str)
        Installs a search plugin from the given URL.
        Parameters:
            url (str): The URL of the search plugin to install.

    uninstallPlugin(name: str)
        Uninstalls a search plugin by its name.
        Parameters:
            name (str): The name of the search plugin to uninstall.

    enablePlugin(name: str)
        Enables a search plugin by its name.
        Parameters:
            name (str): The name of the search plugin to enable.

    updatePlugins()
        Updates all installed search plugins.

    downloadTorrent(file_url: str, save_path: str, **kwargs)
        Downloads a torrent file from the given URL.
        Parameters:
            file_url (str): The URL of the torrent file.
            save_path (str): The path where the torrent should be saved.
            **kwargs: Additional keyword arguments for download options.
```

--------------------------------

### TorrentCreator Class Methods

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/torrentcreator.rst

This section outlines the methods of the TorrentCreator class, responsible for the core logic of creating torrents. It excludes methods like addTask, torrentFile, and deleteTask, which are likely internal or handled by the mixin.

```APIDOC
qbittorrentapi.torrentcreator.TorrentCreator
  __init__(...)
    Initializes the TorrentCreator.

  createTorrent(..., **kwargs)
    Creates a torrent file with specified parameters.
    Parameters:
      ...: Parameters for torrent creation (e.g., files, trackers, name).
    Returns:
      The created torrent file content or path.

  getTaskStatus(..., **kwargs)
    Retrieves the status of a torrent creation task.
    Parameters:
      task_id: The ID of the task.
    Returns:
      The status of the specified task.
```

--------------------------------

### TorrentCreatorAPIMixIn Methods

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/torrentcreator.rst

This section details the methods available in the TorrentCreatorAPIMixIn class, which serves as a mixin for torrent creation functionalities. It excludes specific internal methods like torrentcreator, torrentcreator_addTask, torrentcreator_torrentFile, and torrentcreator_deleteTask.

```APIDOC
qbittorrentapi.torrentcreator.TorrentCreatorAPIMixIn
  __init__(...)
    Initializes the TorrentCreatorAPIMixIn.

  addTorrent(..., **kwargs)
    Adds a torrent using the creator.
    Parameters:
      ...: Various parameters for torrent creation.
    Returns:
      The result of adding the torrent.

  createTorrent(..., **kwargs)
    Creates a torrent file.
    Parameters:
      ...: Various parameters for torrent creation.
    Returns:
      The result of creating the torrent file.

  deleteTorrent(..., **kwargs)
    Deletes a torrent task.
    Parameters:
      ...: Various parameters for deleting a torrent task.
    Returns:
      The result of deleting the torrent task.

  getTorrentCreatorTask(..., **kwargs)
    Retrieves a specific torrent creator task.
    Parameters:
      ...: Parameters to identify the task.
    Returns:
      The torrent creator task details.

  getTorrentCreatorTasks(..., **kwargs)
    Retrieves a list of all torrent creator tasks.
    Parameters:
      ...: Optional parameters for filtering or pagination.
    Returns:
      A list of torrent creator tasks.

  updateTorrent(..., **kwargs)
    Updates an existing torrent task.
    Parameters:
      ...: Parameters for updating the torrent task.
    Returns:
      The result of updating the torrent task.
```

--------------------------------

### RSSAPIMixIn Methods

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/rss.rst

Provides methods for interacting with the RSS feed functionalities. This class includes methods for managing RSS feeds, items, and rules. Specific methods like rss_addFolder, rss_addFeed, rss_removeItem, etc., are excluded from this documentation block.

```APIDOC
qbittorrentapi.rss.RSSAPIMixIn:
  Methods for RSS feed management.
  Excludes: rss, rss_addFolder, rss_addFeed, rss_removeItem, rss_moveItem, rss_refreshItem, rss_markAsRead, rss_setRule, rss_renameRule, rss_removeRule, rss_matchingArticles, rss_setFeedURL
```

--------------------------------

### Torrents API Reference

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/torrents.rst

This section provides a detailed reference for the Torrents API, outlining the available classes and their methods for managing torrents, files, categories, tags, and web seeds.

```APIDOC
qbittorrentapi.torrents.TorrentsAPIMixIn:
  Manages core torrent operations.
  Methods:
    (See excluded members for specific functionalities)

qbittorrentapi.torrents.Torrents:
  Provides access to torrent-related functionalities.
  Methods:
    (See excluded members for specific functionalities)

qbittorrentapi.torrents.TorrentDictionary:
  Represents a torrent with its properties.
  Methods:
    (See excluded members for specific functionalities)

qbittorrentapi.torrents.TorrentCategories:
  Manages torrent categories.
  Methods:
    removeCategories(categories: list[str]) -> None
      Removes specified categories.
    editCategory(old_name: str, new_name: str) -> None
      Renames a category.
    createCategory(name: str, save_path: str = None) -> None
      Creates a new category.

qbittorrentapi.torrents.TorrentTags:
  Manages torrent tags.
  Methods:
    addTags(torrent_hashes: str, tags: str) -> None
      Adds tags to torrents.
    removeTags(torrent_hashes: str, tags: str) -> None
      Removes tags from torrents.
    createTags(tags: str) -> None
      Creates new tags.
    deleteTags(tags: str) -> None
      Deletes specified tags.
    setTags(torrent_hashes: str, tags: str) -> None
      Sets tags for torrents, overwriting existing ones.

qbittorrentapi.torrents.TorrentPropertiesDictionary:
  Dictionary for torrent properties.

qbittorrentapi.torrents.TorrentLimitsDictionary:
  Dictionary for torrent speed limits.

qbittorrentapi.torrents.TorrentCategoriesDictionary:
  Dictionary for torrent categories.

qbittorrentapi.torrents.TorrentsAddPeersDictionary:
  Dictionary for adding peers to torrents.

qbittorrentapi.torrents.TorrentFilesList:
  List of files within a torrent.

qbittorrentapi.torrents.TorrentFile:
  Represents a single file in a torrent.

qbittorrentapi.torrents.WebSeedsList:
  List of web seeds for a torrent.

qbittorrentapi.torrents.WebSeed:
  Represents a single web seed.

qbittorrentapi.torrents.TrackersList:
  List of trackers for a torrent.

qbittorrentapi.torrents.Tracker:
  Represents a single tracker.

qbittorrentapi.torrents.TorrentInfoList:
  List of torrent information.

qbittorrentapi.torrents.TorrentPieceInfoList:
  List of piece information for a torrent.

qbittorrentapi.torrents.TorrentPieceData:
  Data for a specific piece of a torrent.

qbittorrentapi.torrents.TagList:
  List of tags.

qbittorrentapi.torrents.Tag:
  Represents a single tag.
```

--------------------------------

### LogAPIMixIn Class

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/log.rst

Provides methods for interacting with the qBittorrent log API. It serves as a mixin class, likely intended to be inherited by other classes that require log functionality. Specific methods are exposed through its members, excluding the 'log' attribute.

```APIDOC
qbittorrentapi.log.LogAPIMixIn
  :members:
  :undoc-members:
  :exclude-members: log
  :show-inheritance:
```

--------------------------------

### Setting Timeouts for Individual Requests

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/behavior&configuration.rst

Shows how to specify request timeouts for individual API calls using the requests_args parameter.

```python
qbt_client.torrents_info(requests_args={'timeout': (3.1, 30)})
```

--------------------------------

### qbittorrentapi.transfer.Transfer Methods

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/transfer.rst

This section documents the methods of the Transfer class, focusing on transfer operations. It excludes methods for toggling speed limits, setting limits, and banning peers, which are handled separately.

```APIDOC
Transfer:
  Methods for managing transfer operations.
```

--------------------------------

### SearchJobDictionary

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/search.rst

Represents a dictionary structure for search jobs, likely containing information about ongoing or completed search operations. It inherits from a base dictionary type and includes specific members relevant to search jobs.

```APIDOC
qbittorrentapi.search.SearchJobDictionary:
    __init__(...)
        Initializes the SearchJobDictionary.

    # Members typically include information about:
    # - Job ID
    # - Search query
    # - Status (e.g., running, completed, failed)
    # - Progress
    # - Number of results found
```

--------------------------------

### qbittorrentapi Exception Hierarchy

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/exceptions.rst

This section outlines the exception classes provided by the qbittorrentapi library, detailing their inheritance structure and available members. It helps developers understand and handle potential errors during interaction with the qBittorrent API.

```python
import qbittorrentapi

try:
    # Attempt to interact with qBittorrent API
    pass
except qbittorrentapi.LoginFailed as e:
    print(f"Login failed: {e}")
except qbittorrentapi.APIConnectionError as e:
    print(f"Connection error: {e}")
except qbittorrentapi.NotFoundHTTPError as e:
    print(f"Resource not found: {e}")
except qbittorrentapi.ForbiddenHTTPError as e:
    print(f"Forbidden access: {e}")
except qbittorrentapi.BadRequestHTTPError as e:
    print(f"Bad request: {e}")
except qbittorrentapi.ServerError as e:
    print(f"Server error: {e}")
except qbittorrentapi.QBittorrentError as e:
    print(f"An unexpected qBittorrent API error occurred: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
```

--------------------------------

### Log Class

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/log.rst

Represents the main log functionality within the qbittorrent-api. This class exposes various members for accessing and managing log data. It also supports being called directly, indicated by the special member '__call__'.

```APIDOC
qbittorrentapi.log.Log
  :members:
  :undoc-members:
  :special-members: __call__
```

--------------------------------

### LogPeer Class

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/log.rst

Represents a single log peer entry. This class inherits from a base class, exposing all its members and undocumented members.

```APIDOC
qbittorrentapi.log.LogPeer
  :members:
  :undoc-members:
  :show-inheritance:
```

--------------------------------

### MutableAttr Class Documentation

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/attrdict.rst

Provides documentation for the MutableAttr class, detailing its members, undocumented members, and inheritance. MutableAttr is an internal class for the qbittorrent-api library.

```python
.. autoclass:: qbittorrentapi._attrdict.MutableAttr
    :members:
    :undoc-members:
    :show-inheritance:
```

--------------------------------

### qbittorrentapi.app.CookieList

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/app.rst

Represents a list of cookies used with the qBittorrent API.

```APIDOC
qbittorrentapi.app.CookieList:
    List structure for cookies in qBittorrent.
```

--------------------------------

### TorrentCreatorTaskStatus Members

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/torrentcreator.rst

This section describes the members of the TorrentCreatorTaskStatus class, which likely enumerates the possible states for a torrent creation task.

```APIDOC
qbittorrentapi.torrentcreator.TorrentCreatorTaskStatus
  PENDING = 'pending'
    The task is waiting to be processed.

  PROCESSING = 'processing'
    The task is currently being processed.

  COMPLETED = 'completed'
    The task has finished successfully.

  FAILED = 'failed'
    The task failed to complete.
```

--------------------------------

### Manual qBittorrent Version Introspection

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/behavior&configuration.rst

Manually check if a qBittorrent application version is supported by the client using the Version.is_app_version_supported method. This allows for custom handling of version compatibility.

```python
from qbittorrentapi import Client, Version

qbt_client = Client(...)

if Version.is_app_version_supported(qbt_client.app.version):
    print("qBittorrent version is supported.")
else:
    print("qBittorrent version is not supported.")
```

--------------------------------

### RSS Class Methods

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/rss.rst

Represents the core RSS functionality. It includes methods for managing RSS feeds and items. The special member __call__ is documented. Methods like rss, addFolder, addFeed, removeItem, etc., are excluded.

```APIDOC
qbittorrentapi.rss.RSS:
  Core RSS functionality.
  Special Members: __call__
  Excludes: rss, addFolder, addFeed, removeItem, moveItem, refreshItem, markAsRead, setRule, renameRule, removeRule, matchingArticles, setFeedURL
```

--------------------------------

### qbittorrentapi.auth.Authorization

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/auth.rst

Represents authorization details for API requests. This class is typically used internally by the authentication mixin.

```APIDOC
qbittorrentapi.auth.Authorization
  __init__(self, username, password)
    Initializes the Authorization object with username and password.
    Parameters:
      username (str): The username for authorization.
      password (str): The password for authorization.

  username
    The username associated with this authorization.

  password
    The password associated with this authorization.
```

--------------------------------

### qbittorrentapi.definitions Module Members

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/definitions.rst

This section details the members of the qbittorrentapi.definitions module. It includes all documented members but excludes the TorrentStates enum and undocumented members. The show-inheritance flag indicates that inheritance relationships are displayed.

```python
import qbittorrentapi

# Accessing members of the definitions module
# Example: Accessing a specific definition class or function
# print(dir(qbittorrentapi.definitions))

# The following is a representation of what might be documented within the module.
# Specific members are not listed here as they are dynamically generated by the automodule directive.

# Example of a potential class within definitions:
# class SomeDefinition:
#     """A sample definition class."""
#     def __init__(self, value):
#         self.value = value

# Example of a potential function within definitions:
# def some_function(param1: str) -> int:
#     """A sample function."""
#     return len(param1)

# The automodule directive with :members:, :undoc-members:, and :show-inheritance:
# implies that the following would be generated and displayed in the documentation:
# - All public members (functions, classes, variables)
# - Undocumented members (if any)
# - Inheritance hierarchy for classes
# - Excludes 'TorrentStates' as specified.
```

--------------------------------

### TorrentCreatorTaskStatusList Members

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/torrentcreator.rst

This section describes the members of the TorrentCreatorTaskStatusList class, which is likely a container for multiple torrent creation task statuses.

```APIDOC
qbittorrentapi.torrentcreator.TorrentCreatorTaskStatusList
  __init__(...)
    Initializes a TorrentCreatorTaskStatusList.

  tasks: list[TorrentCreatorTaskDictionary]
    A list containing TorrentCreatorTaskDictionary objects.
```

--------------------------------

### LogPeersList Class

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/log.rst

Defines the structure for a list of log peers. This class inherits from a base class, indicated by 'show-inheritance', and includes all its members and undocumented members.

```APIDOC
qbittorrentapi.log.LogPeersList
  :members:
  :undoc-members:
  :show-inheritance:
```

--------------------------------

### Fetch Torrents Asynchronously

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/async.rst

Demonstrates how to fetch torrent information asynchronously by running the blocking `qbt_client.torrents_info` method in a separate thread using `asyncio.to_thread`. This prevents blocking the asyncio event loop.

```python
async def fetch_torrents() -> TorrentInfoList:
    return await asyncio.to_thread(qbt_client.torrents_info, category="uploaded")
```

--------------------------------

### SearchCategoriesList

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/search.rst

Represents a list of available search categories. This structure is used to manage and retrieve the categories that can be used when performing searches.

```APIDOC
qbittorrentapi.search.SearchCategoriesList:
    __init__(...)
        Initializes the SearchCategoriesList.

    # Members are typically SearchCategory objects, each representing a searchable category.
```

--------------------------------

### SearchStatusesList

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/search.rst

Represents a list of search statuses, likely used to track the state of multiple search operations. It inherits from a base list type and contains individual SearchStatus objects.

```APIDOC
qbittorrentapi.search.SearchStatusesList:
    __init__(...)
        Initializes the SearchStatusesList.

    # Members are typically SearchStatus objects, each representing the status of a single search job.
```

--------------------------------

### SearchCategory

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/search.rst

Represents a single search category, providing its name and potentially other relevant information. This is used to define the types of content that can be searched for.

```APIDOC
qbittorrentapi.search.SearchCategory:
    __init__(...)
        Initializes the SearchCategory.

    # Attributes typically include:
    # - name (str): The name of the search category (e.g., 'all', 'movies', 'music').
    # - supported_by (list): A list of plugins that support this category.
```

--------------------------------

### SearchStatus

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/search.rst

Represents the status of a single search job, providing details about its progress and completion. It inherits from a base object type and includes specific attributes for status information.

```APIDOC
qbittorrentapi.search.SearchStatus:
    __init__(...)
        Initializes the SearchStatus.

    # Attributes typically include:
    # - status (str): The current status of the search (e.g., 'Running', 'Completed', 'Error').
    # - progress (int): The progress of the search in percentage.
    # - total (int): The total number of items found.
```

--------------------------------

### TorrentCreatorTaskDictionary Members

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/torrentcreator.rst

Details the members of the TorrentCreatorTaskDictionary class, used for representing torrent creation tasks. It excludes torrentFile and deleteTask, suggesting these might be handled at a different level.

```APIDOC
qbittorrentapi.torrentcreator.TorrentCreatorTaskDictionary
  __init__(...)
    Initializes a TorrentCreatorTaskDictionary.

  task_id: int
    The unique identifier for the torrent creation task.

  status: TorrentCreatorTaskStatus
    The current status of the task.

  progress: float
    The progress of the torrent creation task (0.0 to 1.0).

  created_torrent_path: str
    The file path where the torrent was created.

  error_message: str
    An error message if the task failed.
```

--------------------------------

### SearchResultsDictionary

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/search.rst

Represents a dictionary structure for search results, containing a list of torrents that match a search query. It inherits from a base dictionary type and provides access to individual search results.

```APIDOC
qbittorrentapi.search.SearchResultsDictionary:
    __init__(...)
        Initializes the SearchResultsDictionary.

    # Members typically include:
    # - A list of SearchResults (or similar objects)
    # - Total number of results
    # - Pagination information (if applicable)
```

--------------------------------

### qbittorrentapi.app.NetworkInterfaceAddressList

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/app.rst

Represents a list of IP addresses associated with a network interface.

```APIDOC
qbittorrentapi.app.NetworkInterfaceAddressList:
    List structure for network interface addresses in qBittorrent.
```

--------------------------------

### qbittorrentapi.app.Cookie

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/app.rst

Represents a cookie used for authentication or other purposes with the qBittorrent API.

```APIDOC
qbittorrentapi.app.Cookie:
    Represents a single cookie.
```

--------------------------------

### TaskStatus Members

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/torrentcreator.rst

Details the members of the TaskStatus class, which appears to be an alias or a more general status indicator, possibly for tasks within the torrent creator system.

```APIDOC
qbittorrentapi.torrentcreator.TaskStatus
  PENDING = 'pending'
    Task is pending.

  PROCESSING = 'processing'
    Task is currently processing.

  COMPLETED = 'completed'
    Task has been completed.

  FAILED = 'failed'
    Task has failed.
```

--------------------------------

### RSSitemsDictionary Structure

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/rss.rst

Defines the structure for dictionaries containing RSS items. This class is used to represent collections of RSS feed items.

```APIDOC
qbittorrentapi.rss.RSSitemsDictionary:
  Dictionary structure for RSS items.
  Inheritance: show-inheritance
```

--------------------------------

### RSSRulesDictionary Structure

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/apidoc/rss.rst

Defines the structure for dictionaries containing RSS rules. This class is used to represent collections of RSS feed rules.

```APIDOC
qbittorrentapi.rss.RSSRulesDictionary:
  Dictionary structure for RSS rules.
  Inheritance: show-inheritance
```

--------------------------------

### Disable Logging Debug Output

Source: https://github.com/rmartin16/qbittorrent-api/blob/main/docs/source/behavior&configuration.rst

Disable debug logging for the qbittorrentapi and related packages by setting the logger level to INFO. This can be done during client instantiation or by directly configuring loggers.

```python
import logging
from qbittorrentapi import Client

# Option 1: During client instantiation
# qbt_client = Client(..., DISABLE_LOGGING_DEBUG_OUTPUT=True)

# Option 2: Manually configure loggers
logging.getLogger('qbittorrentapi').setLevel(logging.INFO)
logging.getLogger('requests').setLevel(logging.INFO)
logging.getLogger('urllib3').setLevel(logging.INFO)
```

=== COMPLETE CONTENT === This response contains all available snippets from this library. No additional content exists. Do not make further requests.