#!/bin/sh

# Signal handler for graceful shutdown
# Signal numbers: 15 = SIGTERM, 2 = SIGINT
# Python processes run in foreground and will receive signals directly
# This handler ensures clean exit if signal arrives between commands
cleanup() {
    echo "Received shutdown signal, exiting gracefully..."
    exit 0
}

# Set up signal handlers using signal numbers (POSIX compatible)
# Note: When Python runs in foreground, it receives signals directly
# This trap handles signals that arrive when no Python process is running
trap 'cleanup' 15 2

# Print Ace-Pace header (release date = mtime of acepace.py, no repo commits)
RELEASE_DATE=$(stat -c %y /app/acepace.py 2>/dev/null | cut -d' ' -f1 || true)
echo "============================================================"
echo "                    Ace-Pace"
echo "            One Pace Library Manager"
if [ -n "$RELEASE_DATE" ]; then echo "                  Release $RELEASE_DATE"; fi
echo "============================================================"
echo "Running in Docker mode (non-interactive)"
echo "------------------------------------------------------------"
echo ""

# Run episodes update if requested
if [ "$EPISODES_UPDATE" = "true" ]; then
    python /app/acepace.py --episodes_update ${NYAA_URL:+--url "$NYAA_URL"}
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo "Episodes update failed with exit code $EXIT_CODE"
        exit $EXIT_CODE
    fi
fi

# Export database if requested
if [ "$DB" = "true" ]; then
    python /app/acepace.py --db
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo "Database export failed with exit code $EXIT_CODE"
        exit $EXIT_CODE
    fi
fi

# Run missing episodes report (unless already done by --episodes_update above)
# When EPISODES_UPDATE=true, the report was already run in step 1 (--episodes_update does both)
# Skip when only exporting DB (DB=true and no other operations)
if [ "$EPISODES_UPDATE" != "true" ] && { [ "$DB" != "true" ] || [ "$DOWNLOAD" = "true" ]; }; then
    python /app/acepace.py \
        --folder /media \
        ${NYAA_URL:+--url "$NYAA_URL"}
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo "Missing episodes report failed with exit code $EXIT_CODE"
        exit $EXIT_CODE
    fi
fi

# Run rename if requested (non-interactive: dry-run simulates, otherwise renames without confirmation)
if [ "$RENAME" = "true" ]; then
    DRY_RUN_RENAME_ARG=""
    [ "$DRY_RUN" = "true" ] || [ "$DRY_RUN" = "1" ] || [ "$DRY_RUN" = "yes" ] || [ "$DRY_RUN" = "on" ] && DRY_RUN_RENAME_ARG="--dry-run"
    python /app/acepace.py \
        --folder /media \
        --rename \
        ${NYAA_URL:+--url "$NYAA_URL"} \
        ${DRY_RUN_RENAME_ARG:+$DRY_RUN_RENAME_ARG}
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo "Rename failed with exit code $EXIT_CODE"
        exit $EXIT_CODE
    fi
fi

# If DOWNLOAD is set to true, download missing episodes after generating report
if [ "$DOWNLOAD" = "true" ]; then
    # Only add --dry-run when DRY_RUN is explicitly true (not when set to "false" or empty)
    DRY_RUN_ARG=""
    [ "$DRY_RUN" = "true" ] || [ "$DRY_RUN" = "1" ] || [ "$DRY_RUN" = "yes" ] || [ "$DRY_RUN" = "on" ] && DRY_RUN_ARG="--dry-run"
    # Use exec to replace shell process so Python becomes PID 1 and receives signals directly
    exec python /app/acepace.py \
        --folder /media \
        ${NYAA_URL:+--url "$NYAA_URL"} \
        --download \
        ${DRY_RUN_ARG:+$DRY_RUN_ARG} \
        ${TORRENT_CLIENT:+--client "$TORRENT_CLIENT"} \
        ${TORRENT_HOST:+--host "$TORRENT_HOST"} \
        ${TORRENT_PORT:+--port "$TORRENT_PORT"} \
        ${TORRENT_USER:+--username "$TORRENT_USER"} \
        ${TORRENT_PASSWORD:+--password "$TORRENT_PASSWORD"}
fi

# Exit with success code if we reach here
exit 0