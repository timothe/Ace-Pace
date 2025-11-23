#!/bin/sh
set -e

if [ "$EPISODES_UPDATE" = "true" ]; then
    python /app/acepace.py --episodes_update
fi

exec python /app/acepace.py \
    ${NYAA_URL:+--url "$NYAA_URL"} \
    ${TORRENT_CLIENT:+--download "$TORRENT_CLIENT"} \
    ${DB:+--db}
