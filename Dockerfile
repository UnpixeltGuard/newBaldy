FROM python:3.14.0a2-slim

WORKDIR /app

ADD newBaldy.py ./newBaldy.py
ADD requirements.txt ./requirements.txt

COPY docker-entrypoint.sh ./

RUN chmod +x ./docker-entrypoint.sh

VOLUME [ "/app" ]


RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    libssl-dev \
    python3-dev \
    build-essential \
    ffmpeg \
    libmagic1 \
    libsndfile1 \
    ibasound-dev \
    libportaudio2 \
    libportaudiocpp0 \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT [ "./docker-entrypoint.sh" ]

RUN apt-get install libasound-dev libportaudio2 libportaudiocpp0 portaudio19-dev -y
