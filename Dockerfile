FROM python:3.14.0a2-slim

WORKDIR /app

ADD PLACEHOLDER

COPY docker-entrypoint.sh ./

RUN chmod +x ./docker-entrypoint.sh

VOLUME [ "/app" ]

RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT [ "./docker-entrypoint.sh" ]