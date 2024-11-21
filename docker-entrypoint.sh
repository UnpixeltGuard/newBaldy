#!/bin/sh

echo "Starting PixMusicBot"
echo ""

FILE=/app/config.txt
if [ ! -f "$FILE" ]; then
    echo "No config.txt found, downloading example config from
    PLACEHOLDER"
    
    curl -L https://raw.githubusercontent.com/PLACEHOLDER -o /app/config.txt
    echo ""
fi

cd /app

exec python newBaldy.py