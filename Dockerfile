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
    ACEPACE_URL="https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc" \
    ACEPACE_DB="true" \
    ACEPACE_DOWNLOAD="transmission" \
    TRANSMISSION_HOST="localhost" \
    TRANSMISSION_PORT="9091" \
    TRANSMISSION_USER="" \
    TRANSMISSION_PASS=""

CMD python /app/acepace.py \
    ${ACEPACE_URL:+--url "$ACEPACE_URL"} \
    ${ACEPACE_DB:+--db} \
    ${ACEPACE_DOWNLOAD:+--download "$ACEPACE_DOWNLOAD"}
