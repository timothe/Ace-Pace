#!/bin/sh
set -e

if [ "$EPISODES_UPDATE" = "true" ]; then
    python /app/acepace.py --episodes_update
fi

if [ "$DB" = "true" ]; then
    python /app/acepace.py --db
fi

if [ "$RENAME" = "true" ]; then
    python /app/acepace.py --rename
fi

if [ "$DOWNLOAD_ONLY" = "true" ]; then
    python /app/acepace.py --download "$TORRENT_CLIENT"
fi

exec python /app/acepace.py \
    ${NYAA_URL:+--url "$NYAA_URL"}