# Vendored snapshot: SpykerNZ/one-pace-for-plex

This directory is a lightweight, offline snapshot of canonical episode
metadata from https://github.com/SpykerNZ/one-pace-for-plex (`main` branch),
used by `reference_index.py` to build the deterministic
`(season, episode, extended) -> title` lookup needed for Plex-style renaming.

Contents:

- `seasons.json` — arc name -> season number (vendored verbatim from
  `dist/seasons.json`).
- `exceptions.json` — season name -> {filename substring -> episode number}
  (vendored verbatim from `dist/exceptions.json`).
- `episodes_index.json` — a flat list of `{season, number, title, extended,
  nfo_path}`, derived **from the `.nfo` file paths only** (via the GitHub git
  tree API), not from the `.nfo` file contents.
- `metadata.json` — bookkeeping: `last_refresh` timestamp, source commit SHA,
  episode count.
- `tvshow.nfo` — vendored for future poster/season-name use.

**Not vendored in this pass:** the full `.nfo` XML content for each episode,
`season.nfo` files, and poster images (`.png`). The reference project's path
naming convention (`One Pace/Season N/One Pace - S{NN}E{MM} - {Title}.nfo`)
already encodes everything the naming feature needs (season, episode number,
title, extended/alternate suffix), so path-derived data alone is sufficient
for this pass. A later pass that copies `.nfo`/poster files into the local
library alongside renamed media will need to vendor (or fetch on demand) the
actual file contents.

Refresh this snapshot with `reference_index.refresh_reference_index()`.
