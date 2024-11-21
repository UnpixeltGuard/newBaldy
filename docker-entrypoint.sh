#!/bin/sh

echo "Starting PixMusicBot"
echo ""

FILE=/app/config.txt
if [ ! -f "$FILE" ]; then
    echo "No config.txt found, downloading example config from
    https://github.com/UnpixeltGuard/newBaldy"
    
    curl -L https://raw.githubusercontent.com/UnpixeltGuard/newBaldy/refs/heads/main/config.txt?token=GHSAT0AAAAAACYEW3M6QHLYDASRVK2NVFKKZZ7TLAQ -o /app/config.txt
    echo ""
fi

cd /app

exec python newBaldy.py