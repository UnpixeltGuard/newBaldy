#!/bin/sh

echo "Starting PixMusicBot"
echo ""

FILE=/app/.env
if [ ! -f "$FILE" ]; then
    echo "No .env file found, downloading example config from
    https://github.com/UnpixeltGuard/newBaldy"
    
    curl -L https://raw.githubusercontent.com/UnpixeltGuard/newBaldy/refs/heads/main/.env -o /app/.env
    echo ""
fi

cd /app

exec python newBaldyYTv3.py
