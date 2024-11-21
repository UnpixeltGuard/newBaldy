FROM python:3.12.4-alpine

WORKDIR /app

ADD newBaldy.py ./newBaldy.py
ADD requirements.txt ./requirements.txt

COPY docker-entrypoint.sh ./

RUN chmod +x ./docker-entrypoint.sh

VOLUME [ "/app" ]


RUN apk update && apk add --no-cache \
    gcc \
    libffi-dev \
    libressl-dev \  
    python3-dev \
    build-base \    
    ffmpeg \
    libmagic \
    libsndfile \
    alsa-lib-dev \  
    portaudio-dev \
    && apk clean


RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT [ "./docker-entrypoint.sh" ]

RUN apt-get install libasound-dev libportaudio2 libportaudiocpp0 portaudio19-dev -y
