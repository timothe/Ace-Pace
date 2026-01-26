#!/bin/sh
set -e

# Run episodes update if requested
if [ "$EPISODES_UPDATE" = "true" ]; then
    python /app/acepace.py --episodes_update ${NYAA_URL:+--url "$NYAA_URL"}
fi

# Export database if requested
if [ "$DB" = "true" ]; then
    python /app/acepace.py --db
fi

# Always run missing episodes report first (updates Ace-Pace_Missing.csv)
python /app/acepace.py \
    --folder /media \
    ${NYAA_URL:+--url "$NYAA_URL"}

# If DOWNLOAD is set to true, download missing episodes after generating report
if [ "$DOWNLOAD" = "true" ]; then
    exec python /app/acepace.py \
        --folder /media \
        ${NYAA_URL:+--url "$NYAA_URL"} \
        --download \
        ${TORRENT_CLIENT:+--client "$TORRENT_CLIENT"} \
        ${TORRENT_HOST:+--host "$TORRENT_HOST"} \
        ${TORRENT_PORT:+--port "$TORRENT_PORT"} \
        ${TORRENT_USER:+--username "$TORRENT_USER"} \
        ${TORRENT_PASSWORD:+--password "$TORRENT_PASSWORD"}
fi