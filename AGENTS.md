# Agent Instructions

## Project

Ace-Pace is a single-file Python CLI (`acepace.py` + `clients.py`) that manages a local
One Pace anime library: it scrapes Nyaa for new One Pace releases, matches files by
CRC32 against a local episode index, and renames/downloads episodes into the target
library layout. It supports qBittorrent/Transmission download clients and can run
standalone or inside Docker (see `Dockerfile`, `docker-compose.yml`, `entrypoint.sh`).

<!-- lean-ctx -->
## lean-ctx

Prefer lean-ctx MCP tools over native equivalents for token savings.
Full rules: @LEAN-CTX.md
<!-- /lean-ctx -->
