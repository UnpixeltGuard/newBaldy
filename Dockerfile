FROM python:3.13-alpine AS builder
WORKDIR /app

RUN apk add --no-cache \
    gcc \
    opus-dev \
    libffi-dev \
    libressl-dev \
    python3-dev \
    build-base \
    portaudio-dev \
    alsa-lib-dev \
    libsndfile

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.13-alpine
WORKDIR /app

RUN apk add --no-cache \
    opus \
    libffi \
    ffmpeg \
    libmagic \
    libsndfile

COPY --from=builder /install /usr/local
COPY newBaldyYTv3.py configManager.py ./
COPY cogs ./cogs
COPY utils ./utils
COPY docker-entrypoint.sh ./

RUN chmod +x ./docker-entrypoint.sh && \
    echo "nobody:x:99:100:nobody:/:/bin/false" > /etc/passwd && \
    echo "users:x:100:" > /etc/group && \
    chown 99:100 /app

VOLUME ["/app"]
USER nobody
ENTRYPOINT ["./docker-entrypoint.sh"]
