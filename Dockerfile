FROM python:3.13-alpine
WORKDIR /app

ADD newBaldyYTv3.py ./newBaldyYTv3.py
ADD configManager.py ./configManager.py
ADD cogs ./cogs
ADD utils ./utils
ADD requirements.txt ./requirements.txt
COPY docker-entrypoint.sh ./

RUN chmod +x ./docker-entrypoint.sh

RUN apk update && apk add --no-cache \
    gcc \
    opus \
    opus-dev \
    libffi-dev \
    libressl-dev \
    python3-dev \
    build-base \
    ffmpeg \
    libmagic \
    libsndfile \
    alsa-lib-dev \
    portaudio-dev
    
RUN apk add --no-cache python3 py3-pip
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

RUN echo "nobody:x:99:100:nobody:/:/bin/false" > /etc/passwd && \
    echo "users:x:100:" > /etc/group

RUN chown 99:100 /app

VOLUME [ "/app" ]
USER nobody

ENTRYPOINT [ "./docker-entrypoint.sh" ]
