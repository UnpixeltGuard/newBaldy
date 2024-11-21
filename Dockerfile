FROM python:3.12.7-alpine

WORKDIR /app

ADD newBaldy.py ./newBaldy.py
ADD requirements.txt ./requirements.txt

COPY docker-entrypoint.sh ./

RUN chmod +x ./docker-entrypoint.sh

VOLUME [ "/app" ]


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

ENTRYPOINT [ "./docker-entrypoint.sh" ]
