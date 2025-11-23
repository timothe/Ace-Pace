FROM python:3.13-slim

LABEL description="Ace-Pace - One Pace Library Manager"

COPY . /app
WORKDIR /app

RUN apt-get update \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && touch /app/Ace-Pace_Missing.csv

ENV RUN_DOCKER="true" \
    PYTHONUNBUFFERED=1 \
    NYAA_URL="https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc" \
    TORRENT_CLIENT="transmission" \
    TORRENT_HOST="localhost" \
    TORRENT_PORT="9091" \
    TORRENT_USER="" \
    TORRENT_PASSWORD="" \
    DB="true" \
    EPISODES_UPDATE="true"

CMD ["/app/entrypoint.sh"]
