FROM python:3.13-slim

LABEL description="Ace-Pace - One Pace Library Manager"

COPY . /app
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && touch /app/Ace-Pace_Missing.csv

RUN pip install --no-cache-dir -r /app/requirements.txt

ENV PYTHONUNBUFFERED=1 \
    ACEPACE_URL="https://nyaa.si/?f=0&c=0_0&q=one+pace+1080p&o=asc" \
    ACEPACE_DB="true" \
    ACEPACE_DOWNLOAD="transmission" \
    TRANSMISSION_HOST="localhost" \
    TRANSMISSION_PORT="9091" \
    TRANSMISSION_USER="" \
    TRANSMISSION_PASS="" \

# outwit interactive questions in acepace.py - this is a dirty workaround and definitely needs to be changed, e.g., by adding an interactive_flag in acepace.py to only take default values and/or the environment variables from docker files
CMD /bin/sh -c 'printf "y\n${ACEPACE_DOWNLOAD:-transmission}\n${TRANSMISSION_HOST}\n${TRANSMISSION_PORT}\n${TRANSMISSION_USER}\n${TRANSMISSION_PASS}\n" | python /app/acepace.py \
    --folder "/media" \
    ${ACEPACE_URL:+--url "$ACEPACE_URL"} \
    ${ACEPACE_DB:+--db} \
    ${ACEPACE_DOWNLOAD:+--download "$ACEPACE_DOWNLOAD"}'
