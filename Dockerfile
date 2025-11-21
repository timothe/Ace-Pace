FROM python:3.13-slim

LABEL description="Ace-Pace - One Pace Library Manager"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && git clone https://github.com/timothe/Ace-Pace.git . \
    && touch /app/Ace-Pace_Missing.csv
    
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1
ENV ACEPACE_URL=""
ENV ACEPACE_DB=""
ENV ACEPACE_DOWNLOAD=""
ENV TRANSMISSION_HOST="localhost"
ENV TRANSMISSION_PORT="9091"
ENV TRANSMISSION_USER=""
ENV TRANSMISSION_PASS=""

# outwit interactive questions in acepace.py - this is a dirty workaround and definitely needs to be changed, e.g., by adding an interactive_flag in acepace.py to only take default values and/or the environment variables from docker files
CMD /bin/sh -c 'printf "y\n${ACEPACE_DOWNLOAD:-transmission}\n${TRANSMISSION_HOST}\n${TRANSMISSION_PORT}\n${TRANSMISSION_USER}\n${TRANSMISSION_PASS}\n" | python /app/acepace.py \
    --folder /media \
    ${ACEPACE_URL:+--url "$ACEPACE_URL"} \
    ${ACEPACE_DB:+--db} \
    ${ACEPACE_DOWNLOAD:+--download "$ACEPACE_DOWNLOAD"}'
