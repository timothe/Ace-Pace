FROM python:3.13-slim

LABEL description="Ace-Pace - One Pace Library Manager"

COPY . /app
WORKDIR /app

ENV RUN_DOCKER="true" \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/London \
    NYAA_URL="https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc" \
    TORRENT_HOST="127.0.0.1" \
    TORRENT_CLIENT="transmission" \
    TORRENT_PORT="9091" \
    TORRENT_USER="" \
    TORRENT_PASSWORD="" \
    TORRENT_PASSWORD="" \
    RENAME="false" \
    EPISODES_UPDATE="true"

# Install dependencies
RUN apt-get update && apt-get install -y \
    tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
