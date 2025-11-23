FROM python:3.13-slim

LABEL description="Ace-Pace - One Pace Library Manager"

COPY . /app
WORKDIR /app

ENV RUN_DOCKER="true" \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Berlin \
    NYAA_URL="https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc" \
    TORRENT_HOST="127.0.0.1" \
    TORRENT_CLIENT="transmission" \
    TORRENT_PORT="9091" \
    TORRENT_USER="" \
    TORRENT_PASSWORD="" \
    DB="true" \
    EPISODES_UPDATE="true"

RUN apt-get update \
    && apt-get install -y tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && chmod +x /app/entrypoint.sh \
    && touch /app/Ace-Pace_Missing.csv

CMD ["/app/entrypoint.sh"]
