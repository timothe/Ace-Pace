FROM python:3.13-slim

LABEL description="Ace-Pace - One Pace Library Manager"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && git clone https://github.com/timothe/Ace-Pace.git .

RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /media

ENV PYTHONUNBUFFERED=1
ENV ACEPACE_URL=""
ENV ACEPACE_DB=""
ENV ACEPACE_DOWNLOAD=""

CMD python acepace.py \
    --folder /media \
    ${ACEPACE_URL:+--url "$ACEPACE_URL"} \
    ${ACEPACE_DB:+--db} \
    ${ACEPACE_DOWNLOAD:+--download "$ACEPACE_DOWNLOAD"}
