FROM python:3.13-slim

LABEL description="Ace-Pace - One Pace Library Manager"

COPY . /app
WORKDIR /app

ENV RUN_DOCKER="true" \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Berlin \
    TORRENT_HOST="127.0.0.1" \
    TORRENT_CLIENT="transmission" \
    TORRENT_PORT="9091" \
    TORRENT_USER="" \
    TORRENT_PASSWORD=""
# Note: NYAA_URL, DB, and EPISODES_UPDATE should be set in docker-compose.yml, not here
# This allows users to override them without rebuilding the image

RUN apt-get update \
    && apt-get install -y tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
