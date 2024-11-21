FROM python:3.14.0a2-slim

WORKDIR /app

ADD https://github.com/UnpixeltGuard/newBaldy/blob/04bb4a50c8ccc53a224a2ecc91b391f4df7b7c34/newBaldy.py ./newBaldy.py

COPY docker-entrypoint.sh ./

RUN chmod +x ./docker-entrypoint.sh

VOLUME [ "/app" ]

RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT [ "./docker-entrypoint.sh" ]
