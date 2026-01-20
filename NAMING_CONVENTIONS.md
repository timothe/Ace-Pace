# Function Naming Conventions

This document explains the naming logic for helper functions in `acepace.py`, particularly those added during the SonarQube refactoring.

## Naming Pattern Overview

Helper functions use a consistent naming pattern: `_<action>_<target>_<context>` or `_<action>_<target>`

The underscore prefix (`_`) indicates these are **private/internal functions** that are not part of the public API.

## Naming Categories

### 1. Extraction Functions: `_extract_*`

Functions that extract data from structures (HTML, files, etc.):

- `_extract_title_link_from_row(row)` - Extracts the title link element from an HTML table row
- `_extract_filenames_from_folder_structure(filelist_div)` - Extracts filenames from a folder-based torrent file list
- `_extract_filenames_from_torrent_page(torrent_soup)` - Extracts all filenames from a torrent page's file list
- `_extract_matching_titles_from_rows(rows, crc32)` - Extracts titles matching a specific CRC32 from table rows

**Pattern**: `_extract_<what>_from_<where>`

### 2. Processing Functions: `_process_*`

Functions that process data structures or perform transformations:

- `_process_fname_entry(fname_text, ...)` - Processes a filename entry to extract and store CRC32
- `_process_torrent_page(page_link, ...)` - Processes a torrent page to extract CRC32 information
- `_process_episode_row(row, ...)` - Processes a single table row to extract episode information
- `_process_crc32_row(row, ...)` - Processes a table row to extract CRC32 information for missing episodes

**Pattern**: `_process_<what>_<context>`

### 3. Validation Functions: `_is_*`, `_validate_*`

Functions that validate or check conditions:

- `_is_valid_quality(fname_text)` - Checks if a filename has valid quality (1080p or 720p)
- `_validate_url(url)` - Validates that a URL points to a valid Nyaa domain

**Pattern**: `_is_<condition>` or `_validate_<what>`

### 4. Command Handlers: `_handle_*`

Functions that handle specific command-line operations:

- `_handle_download_command(args)` - Handles the `--download` command
- `_handle_rename_command(conn)` - Handles the `--rename` command
- `_handle_main_commands(args, conn, folder)` - Routes and handles main command execution

**Pattern**: `_handle_<command>_<context>`

### 5. Getter Functions: `_get_*`

Functions that retrieve or compute values:

- `_get_total_pages(soup)` - Extracts total number of pages from pagination controls
- `_get_folder_from_args(args, conn, needs_folder)` - Gets folder path from arguments or prompts user
- `_get_rename_prompt(last_ep_update)` - Gets user prompt for rename confirmation

**Pattern**: `_get_<what>_<from_where>`

### 6. Load/Save Functions: `_load_*`, `_save_*`

Functions that load or save data:

- `_load_old_missing_crc32s()` - Loads CRC32s from previous missing CSV file
- `_save_missing_episodes_csv(...)` - Saves missing episodes to CSV file

**Pattern**: `_load_<what>` or `_save_<what>_<format>`

### 7. Print/Report Functions: `_print_*`, `_report_*`, `_show_*`

Functions that display information:

- `_print_report_header(conn, folder, args)` - Prints header information for the report
- `_report_new_missing_episodes(missing, crc32_to_text)` - Reports newly detected missing episodes
- `_show_episodes_metadata_status()` - Shows last episodes metadata update status

**Pattern**: `_print_<what>`, `_report_<what>`, or `_show_<what>`

### 8. Workflow Functions: `_generate_*`, `_calculate_*`

Functions that orchestrate multi-step workflows:

- `_generate_missing_episodes_report(conn, folder, args)` - Generates and saves missing episodes report
- `_calculate_and_find_missing(folder, conn, args, last_run)` - Calculates local CRC32s and finds missing episodes

**Pattern**: `_generate_<what>` or `_calculate_<what>_and_<action>`

### 9. Utility Functions: `_parse_*`, `_count_*`

General utility functions:

- `_parse_arguments()` - Parses command-line arguments
- `_count_video_files(folder, conn)` - Counts total video files and files already recorded in DB

**Pattern**: `_parse_<what>` or `_count_<what>`

## Design Principles

1. **Single Responsibility**: Each function has one clear purpose
2. **Descriptive Names**: Function names clearly describe what they do
3. **Consistent Patterns**: Similar functions follow similar naming patterns
4. **Private by Default**: All helpers are prefixed with `_` to indicate internal use
5. **Context Clarity**: Function names include enough context to understand their purpose

## Benefits of This Naming Convention

1. **Readability**: Easy to understand what a function does from its name
2. **Discoverability**: Functions can be found by their action prefix
3. **Maintainability**: Clear separation between public API and internal helpers
4. **Documentation**: Function names serve as inline documentation
5. **Refactoring**: Easy to identify and group related functions

## Example Usage Flow

When reading code, you can quickly understand the flow:

```python
# Main entry point
main()
  → _parse_arguments()           # Get user input
  → _validate_url()              # Check URL is valid
  → _show_episodes_metadata_status()  # Display status
  → _get_folder_from_args()      # Get or prompt for folder
  → _handle_main_commands()      # Route to appropriate handler
    → _generate_missing_episodes_report()  # Main workflow
      → _print_report_header()   # Show header info
      → _calculate_and_find_missing()  # Find missing episodes
        → fetch_crc32_links()    # Public API function
      → _report_new_missing_episodes()  # Show new episodes
      → _save_missing_episodes_csv()  # Save results
```

This naming convention makes the codebase more maintainable and easier to understand.
