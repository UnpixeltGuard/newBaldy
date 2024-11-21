FROM python:3.14.0a2-slim

WORKDIR /app

ADD newBaldy.py ./newBaldy.py
ADD requirements.txt ./requirements.txt

COPY docker-entrypoint.sh ./

RUN chmod +x ./docker-entrypoint.sh

VOLUME [ "/app" ]

RUN apt-get update && apt-get install -y ffmpeg libmagic1

RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT [ "./docker-entrypoint.sh" ]
