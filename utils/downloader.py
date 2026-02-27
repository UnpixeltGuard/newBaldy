import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import yt_dlp
import asyncio
from discord.ext import commands
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from utils.library import update_song_library

logger = logging.getLogger("newBaldy.downloader")


def get_song_file_path(song_id: str, download_folder_path: Path) -> Optional[str]:
    for ext in (".webm", ".m4a", ".mp3", ".opus", ".mp4"):
        file_path = download_folder_path / f"{song_id}{ext}"
        if file_path.exists():
            return str(file_path)
    return None


async def search_song(query: str, youtube_api_key: str) -> List[Dict[str, Any]]:
    """Search YouTube Data API v3 for a video matching the query."""
    def _search_sync(q: str) -> List[Dict[str, Any]]:
        try:
            youtube = build("youtube", "v3", developerKey=youtube_api_key)
            search_response = (
                youtube.search()
                .list(q=q, part="snippet", maxResults=1, type="video")
                .execute()
            )
            return [
                {
                    "title": item["snippet"]["title"],
                    "videoId": item["id"]["videoId"],
                    "author": item["snippet"]["channelTitle"],
                }
                for item in search_response.get("items", [])
            ]
        except HttpError as e:
            logger.exception("YouTube API error for query '%s': %s", q, e)
            return []
        except Exception:
            logger.exception("Unexpected YouTube API error for query '%s'", q)
            return []

    return await asyncio.to_thread(_search_sync, query)


async def download_song(
    url: str,
    ctx: commands.Context,
    download_folder_path: Path,
    max_song_time: int,
    library_path: Path,
    download_folder: str,
) -> Optional[str]:
    """Download a song via yt_dlp, enforcing the duration limit and updating the library."""

    def _download_sync(download_url: str) -> Optional[Dict[str, Any]]:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(download_folder_path / "%(id)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "force_generic_extractor": False,
            "youtube_include_dash_manifest": False,
            "ignoreerrors": True,
            "verbose": False,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(download_url, download=False)
                duration = info_dict.get("duration", 0)
                if duration and duration > max_song_time:
                    return {"error": "duration", "duration": duration, "max": max_song_time}
                info_dict = ydl.extract_info(download_url, download=True)
                return {"info": info_dict}
        except Exception as e:
            logger.exception("Download error for %s: %s", download_url, e)
            return {"error": "exception", "exception": str(e)}

    result = await asyncio.to_thread(_download_sync, url)

    if not result:
        await ctx.send("Download error: unknown error.")
        return None

    if "error" in result:
        if result["error"] == "duration":
            await ctx.send(
                f"Song duration ({result['duration']}s) exceeds the "
                f"maximum allowed duration of {result['max']}s."
            )
        else:
            await ctx.send(f"Download error: {result.get('exception', 'unknown')}")
        return None

    info_dict = result.get("info")
    if not info_dict:
        await ctx.send("Download error: could not retrieve info after download.")
        return None

    video_id = info_dict.get("id")
    if not video_id:
        await ctx.send("Download error: missing video ID.")
        return None

    actual_file = get_song_file_path(video_id, download_folder_path)
    if actual_file is None:
        await ctx.send("Error: downloaded file not found on disk.")
        return None

    await asyncio.to_thread(update_song_library, info_dict, library_path, download_folder)
    return actual_file
