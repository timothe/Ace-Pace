# Ace-Pace TODO / Roadmap

Project-level ideas and future work. Do not treat these as committed implementation plans.

- [x] **Let the user choose between the extended or normal versions** — `--version {normal,extended}` / `VERSION` env var, used by both rename and missing/download detection.
- [x] **Rename using episode reference with [one-pace-for-plex](https://github.com/SpykerNZ/one-pace-for-plex/)** — `--rename` now targets `One Pace - S01E01 - Romance Dawn, the Dawn of an Adventure.mkv` (plus `.nfo`/poster), sourced from a live-fetch-with-vendored-fallback reference index (`REFERENCE_UPDATE`).
- [ ] **Clean feature** — Newest-version detection is embedded in the download/missing flow (an episode's newest release is preferred for download). Still missing: a standalone "clean" command that scans the library and removes older local duplicate files once a newer version of the same episode is confirmed present, respecting the version choice above.
- [ ] **Long-term goal: Complete web UI** — Provide a full web interface for Ace-Pace (configuration, missing report, rename, clean, etc.) instead of/in addition to CLI and Docker env vars.
