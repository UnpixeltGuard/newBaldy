import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

import yt_dlp

logger = logging.getLogger("newBaldy.library")


def load_library(library_path: Path) -> Dict[str, Any]:
    if not library_path.exists():
        return {}
    try:
        with library_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.exception("Failed to read library file: %s", e)
        return {}


def save_library(library: Dict[str, Any], library_path: Path) -> None:
    try:
        with tempfile.NamedTemporaryFile(
            "w", delete=False, dir=str(library_path.parent), encoding="utf-8"
        ) as tf:
            json.dump(library, tf, indent=4, ensure_ascii=False)
            tempname = tf.name
        os.replace(tempname, str(library_path))
    except Exception:
        logger.exception("Failed to write library file")


def update_song_library(
    song_info: Dict[str, Any],
    library_path: Path,
    download_folder: str,
) -> None:
    library = load_library(library_path)
    song_id = song_info.get("id")
    if not song_id:
        logger.warning("update_song_library called without id")
        return

    library[song_id] = {
        "title": song_info.get("title", "Unknown Title"),
        "duration": song_info.get("duration", 0),
        "uploader": song_info.get("uploader", "Unknown Uploader"),
        "filename": str(Path(download_folder) / f"{song_id}.webm"),
        "url": f"https://www.youtube.com/watch?v={song_id}",
        "download_date": song_info.get("download_date", ""),
    }
    save_library(library, library_path)


def scan_and_update_library(
    download_folder_path: Path,
    library_path: Path,
    download_folder: str,
) -> None:
    """Scan download folder and index any songs missing from the library."""
    try:
        library = load_library(library_path)
        downloaded_files = [
            f for f in os.listdir(download_folder_path) if f.endswith(".mp4")
        ]
        new_songs_count = 0

        for filename in downloaded_files:
            song_id = Path(filename).stem
            if song_id in library:
                continue

            video_url = f"https://www.youtube.com/watch?v={song_id}"
            try:
                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "no_color": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    video_info = ydl.extract_info(video_url, download=False)

                library[song_id] = {
                    "title": video_info.get("title", "Unknown Title"),
                    "duration": video_info.get("duration", 0),
                    "uploader": video_info.get("uploader", "Unknown Uploader"),
                    "filename": str(Path(download_folder) / filename),
                    "url": video_url,
                    "download_date": "",
                }
                new_songs_count += 1

            except Exception as e:
                logger.exception("Error processing song %s: %s", song_id, e)

        save_library(library, library_path)
        logger.info("Library scan complete. Added %d new songs.", new_songs_count)
    except Exception:
        logger.exception("Error during library scan")
