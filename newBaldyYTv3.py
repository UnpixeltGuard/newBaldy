import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
import discord
from discord.ext import commands
from discord.ext.commands import check
import yt_dlp
import random
import asyncio
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from configManager import ConfigManager

# Setup and configuration
logger = logging.getLogger("newBaldy")
logging.basicConfig(level=logging.INFO)

script_dir = Path(__file__).resolve().parent
config_file_path = script_dir / ".env"
INDEX_FOLDER = script_dir / "index"
INDEX_FOLDER.mkdir(parents=True, exist_ok=True)
library_path = INDEX_FOLDER / "song_library.json"

config_manager = ConfigManager(str(config_file_path))

MAX_SONG_TIME = config_manager.max_song_time
DOWNLOAD_FOLDER = config_manager.download_folder
download_folder_path = script_dir / DOWNLOAD_FOLDER
download_folder_path.mkdir(parents=True, exist_ok=True)

# Intents and bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
bot.config_manager = config_manager

# Guild-scoped state helpers
guild_queues: Dict[int, List[Dict[str, Any]]] = {}
guild_voice_clients: Dict[int, discord.VoiceClient] = {}
guild_locks: Dict[int, asyncio.Lock] = {}

def get_guild_lock(guild_id: int) -> asyncio.Lock:
    lock = guild_locks.get(guild_id)
    if lock is None:
        lock = asyncio.Lock()
        guild_locks[guild_id] = lock
    return lock

def get_queue(guild_id: int) -> List[Dict[str, Any]]:
    return guild_queues.setdefault(guild_id, [])

def set_voice_client_for_guild(guild_id: int, vc: Optional[discord.VoiceClient]):
    if vc is None:
        guild_voice_clients.pop(guild_id, None)
    else:
        guild_voice_clients[guild_id] = vc

def get_voice_client_for_guild(guild_id: int) -> Optional[discord.VoiceClient]:
    return guild_voice_clients.get(guild_id)

# Owner check using BOT_OWNER from config
def is_bot_owner():
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author.id != config_manager.bot_owner:
            raise commands.NotOwner("You are not the bot owner.")
        return True
    return check(predicate)

# Safe library access helpers
def load_library() -> Dict[str, Any]:
    if not library_path.exists():
        return {}
    try:
        with library_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.exception("Failed to read library file: %s", e)
        return {}

def save_library(library: Dict[str, Any]) -> None:
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, dir=str(INDEX_FOLDER), encoding="utf-8") as tf:
            json.dump(library, tf, indent=4, ensure_ascii=False)
            tempname = tf.name
        os.replace(tempname, str(library_path))
    except Exception:
        logger.exception("Failed to write library file")

def update_song_library(song_info: Dict[str, Any]) -> None:
    library = load_library()
    song_id = song_info.get("id")
    if not song_id:
        logger.warning("update_song_library called without id")
        return

    song_data = {
        "title": song_info.get("title", "Unknown Title"),
        "duration": song_info.get("duration", 0),
        "uploader": song_info.get("uploader", "Unknown Uploader"),
        "filename": str(Path(DOWNLOAD_FOLDER) / f"{song_id}.webm"),
        "url": f"https://www.youtube.com/watch?v={song_id}",
        "download_date": song_info.get("download_date", "")
    }
    library[song_id] = song_data
    save_library(library)

# Utilities
def get_song_file_path(song_id: str) -> Optional[str]:
    for ext in (".webm", ".m4a", ".mp3", ".opus", ".mp4"):
        file_path = download_folder_path / f"{song_id}{ext}"
        if file_path.exists():
            return str(file_path)
    return None

# Blocking operations
# Scan for Downloads and Index
def _scan_and_update_library_sync() -> None:
    try:
        library = load_library()
        downloaded_files = [f for f in os.listdir(download_folder_path) if f.endswith(".webm")]
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
                    "extract_flat": True
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    video_info = ydl.extract_info(video_url, download=False)

                song_data = {
                    "title": video_info.get("title", "Unknown Title"),
                    "duration": video_info.get("duration", 0),
                    "uploader": video_info.get("uploader", "Unknown Uploader"),
                    "filename": str(Path(DOWNLOAD_FOLDER) / filename),
                    "url": video_url,
                    "download_date": ""
                }

                library[song_id] = song_data
                new_songs_count += 1

            except Exception as e:
                logger.exception("Error processing song %s: %s", song_id, e)

        save_library(library)
        logger.info("Library scan complete. Added %d new songs.", new_songs_count)
    except Exception:
        logger.exception("Error during library scan")

# Downloads song via yt_dlp, checks duration limit and updates library
async def download_song(url: str, ctx: commands.Context) -> Optional[str]:
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
            "verbose": False
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(download_url, download=False)
                duration = info_dict.get("duration", 0)
                if duration and duration > MAX_SONG_TIME:
                    return {"error": "duration", "duration": duration, "max": MAX_SONG_TIME}

                info_dict = ydl.extract_info(download_url, download=True)
                return {"info": info_dict}
        except Exception as e:
            logger.exception("Download sync error for %s: %s", download_url, e)
            return {"error": "exception", "exception": str(e)}

    result = await asyncio.to_thread(_download_sync, url)

    if not result:
        await ctx.send("Download error: unknown error")
        return None
    if "error" in result:
        if result["error"] == "duration":
            await ctx.send(f"Song duration ({result['duration']} seconds) exceeds max allowed duration of {result['max']} seconds!")
            return None
        await ctx.send(f"Download error: {result.get('exception', 'unknown')}")
        return None

    info_dict = result.get("info")
    if not info_dict:
        await ctx.send("Download error: could not retrieve info after download")
        return None

    video_id = info_dict.get("id")
    if not video_id:
        await ctx.send("Download error: missing video id")
        return None

    actual_file = get_song_file_path(video_id)
    if actual_file is None:
        await ctx.send("Error: Downloaded file not found!")
        return None

    await asyncio.to_thread(update_song_library, info_dict)
    return actual_file

# Use YouTube Data API for looking up videos
async def search_song(query: str) -> List[Dict[str, Any]]:
    def _search_sync(q: str) -> List[Dict[str, Any]]:
        try:
            youtube = build("youtube", "v3", developerKey=config_manager.youtube_api_key)
            search_response = youtube.search().list(
                q=q,
                part="snippet",
                maxResults=1,
                type="video"
            ).execute()

            items = search_response.get("items", [])
            results = []
            for item in items:
                results.append({
                    "title": item["snippet"]["title"],
                    "videoId": item["id"]["videoId"],
                    "author": item["snippet"]["channelTitle"]
                })
            return results
        except HttpError as e:
            logger.exception("YouTube API error for query %s: %s", q, e)
            return []
        except Exception:
            logger.exception("Unexpected YouTube API error for query %s", q)
            return []

    return await asyncio.to_thread(_search_sync, query)


# Playback logic
# Play next song, disconnect if queue empty
async def play_next_for_guild(guild_id: int, text_channel_id: int) -> None:
    try:
        queue = get_queue(guild_id)
        if not queue:
            vc = get_voice_client_for_guild(guild_id)
            if vc and vc.is_connected():
                try:
                    await vc.disconnect()
                except Exception:
                    logger.exception("Error disconnecting voice client for guild %s", guild_id)
                set_voice_client_for_guild(guild_id, None)
            channel = bot.get_channel(text_channel_id)
            if channel:
                await channel.send("No songs in the queue!")
            return

        song = queue.pop(0)
        song_file = get_song_file_path(song["id"])
        channel = bot.get_channel(text_channel_id)

        if not song_file:
            if channel:
                await channel.send(f"Error: Could not find audio file for {song['title']}")
            await play_next_for_guild(guild_id, text_channel_id)
            return

        vc = get_voice_client_for_guild(guild_id)
        if not vc or not vc.is_connected():
            if channel:
                await channel.send("Bot is not connected to a voice channel. Use !play while in a voice channel to start playback.")
            return

        def _after_playback(error, g_id=guild_id, ch_id=text_channel_id):
            if error:
                logger.exception("Playback error for guild %s: %s", g_id, error)
            bot.loop.call_soon_threadsafe(asyncio.create_task, play_next_for_guild(g_id, ch_id))

        try:
            audio_source = discord.FFmpegPCMAudio(song_file)
            vc.play(audio_source, after=_after_playback)
            if channel:
                await channel.send(f"Now playing: {song['title']}")
        except Exception as e:
            logger.exception("Error playing audio for guild %s: %s", guild_id, e)
            if channel:
                await channel.send(f"Error playing audio: {str(e)}")
            await play_next_for_guild(guild_id, text_channel_id)

    except Exception:
        logger.exception("Unexpected error in play_next_for_guild for guild %s", guild_id)

# Search library first, download if missing, add to queue
async def add_to_queue_and_play(ctx: commands.Context, song_name: str) -> None:
    guild_id = ctx.guild.id
    channel = ctx.channel
    lock = get_guild_lock(guild_id)

    song_info = await search_song(song_name)

    if not song_info:
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": False,
                "extract_flat": True,
                "default_search": "ytsearch",
                "verbose": True
            }
            def _ytsearch_sync(query: str):
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(query, download=False)
            info = await asyncio.to_thread(_ytsearch_sync, song_name)

            if not info or "entries" not in info or not info["entries"]:
                await ctx.send("No YouTube results found for the song.")
                return

            video = info["entries"][0]
            song_title = video.get("title", song_name)
            video_url = video.get("webpage_url", "")
            video_id = video.get("id", "")

            if not video_url:
                await ctx.send("No results found! Please try a different query.")
                return

            await ctx.send(f"No results in index. Downloading first result: {song_title}")
            downloaded_file = await download_song(video_url, ctx)
            if downloaded_file is None:
                return

        except Exception as e:
            logger.exception("Unexpected error while searching with yt_dlp: %s", e)
            await ctx.send(f"Error searching for song: {e}")
            return
    else:
        video = song_info[0]
        if "title" not in video or "videoId" not in video:
            await ctx.send("Invalid song data received from the search. Please try again.")
            return
        song_title = video["title"]
        video_url = f"https://www.youtube.com/watch?v={video['videoId']}"
        video_id = video["videoId"]

    file_path = str(download_folder_path / f"{video_id}.webm")
    if not os.path.exists(file_path):
        await ctx.send(f"Downloading {song_title}...")
        downloaded_file = await download_song(video_url, ctx)
        if downloaded_file is None:
            return
        await ctx.send(f"Downloaded {song_title}.")

    async with lock:
        q = get_queue(guild_id)
        q.append({"title": song_title, "url": video_url, "id": video_id})
        await ctx.send(f"Added {song_title} to the queue.")

    vc = get_voice_client_for_guild(guild_id)
    if not vc or not vc.is_playing():
        if ctx.author.voice and ctx.author.voice.channel:
            try:
                vc = await ctx.author.voice.channel.connect()
                set_voice_client_for_guild(guild_id, vc)
            except Exception:
                logger.exception("Failed to connect to voice channel for guild %s", guild_id)
                await ctx.send("Failed to connect to your voice channel.")
                return
            await play_next_for_guild(guild_id, ctx.channel.id)
        else:
            await ctx.send("You must be in a voice channel for me to join and play music.")

# Bot Commands
def check_bot_ready():
    async def predicate(ctx):
        return True
    return commands.check(predicate)

@bot.command(name="search")
@check_bot_ready()
async def search(ctx, *, query: str):
    """Searches the Youtube API for a song!"""
    await ctx.send(f"Searching for: {query}")
    results = await search_song(query)
    if not results:
        await ctx.send("No results found! Please try a different search.")
        return

    embed = discord.Embed(title="Search Results", color=discord.Color.blue())
    for i, result in enumerate(results, 1):
        embed.add_field(
            name=f"{i}. {result['title']}",
            value=f"By: {result['author']}\nID: {result['videoId']}",
            inline=False
        )
    embed.set_footer(text="To play a song, use !play <song title> or !play https://youtube.com/watch?v=<video_id>")
    await ctx.send(embed=embed)

@bot.command(name="queue")
@check_bot_ready()
async def show_queue(ctx):
    """Shows the current queue!"""
    queue = get_queue(ctx.guild.id)
    if not queue:
        await ctx.send("The queue is empty!")
    else:
        queue_list = "\n".join([f"{idx + 1}. {song['title']}" for idx, song in enumerate(queue)])
        await ctx.send(f"Current Queue:\n{queue_list}")

@bot.command(name="skip")
@check_bot_ready()
async def skip(ctx):
    """Skips the current song!"""
    vc = get_voice_client_for_guild(ctx.guild.id)
    if vc and vc.is_playing():
        vc.stop()
        await ctx.send("Skipped the current song!")
    else:
        await ctx.send("No song is currently playing to skip.")

@bot.command(name="play")
@check_bot_ready()
async def play(ctx, *, song_name: str):
    """Searches the Youtube API and adds the first matching song to the playlist!"""
    await add_to_queue_and_play(ctx, song_name)

@bot.command(name="stop")
@check_bot_ready()
async def stop(ctx):
    """Stops the Bot and clears the current playlist!"""
    guild_id = ctx.guild.id
    vc = get_voice_client_for_guild(guild_id)
    if vc:
        try:
            vc.stop()
            if vc.is_connected():
                await vc.disconnect()
        except Exception:
            logger.exception("Error stopping/ disconnecting voice client for guild %s", guild_id)
        set_voice_client_for_guild(guild_id, None)
    guild_queues[guild_id] = []
    await ctx.send("Stopped the music and cleared the queue!")

@bot.command(name="library")
@check_bot_ready()
async def library(ctx, *, query: str = None):
    """Lists/Searches library of the Bot!"""
    library = load_library()
    if not library:
        await ctx.send("The song library is empty!")
        return

    if query is None:
        songs_list = list(library.values())[:20]
        response = "First 20 songs in the library:\n" + "\n".join([
            f"• {song['title']} (by {song['uploader']})" for song in songs_list
        ])
        await ctx.send(response)
        return

    matching_songs = [
        song for song in library.values()
        if query.lower() in song["title"].lower()
    ]
    if not matching_songs:
        await ctx.send(f"No songs found matching '{query}'.")
        return

    response = f"Songs matching '{query}':\n" + "\n".join([
        f"• {song['title']} (by {song['uploader']}) [ID: {song['url'].split('=')[1]}]" for song in matching_songs
    ])
    await ctx.send(response)

@bot.command(name="shuffle")
@check_bot_ready()
async def shuffle(ctx):
    """Shuffles 10 random songs from library into the playlist!"""
    library = load_library()
    if not library:
        await ctx.send("The song library is empty!")
        return

    selected_songs = random.sample(list(library.values()), min(10, len(library)))
    guild_id = ctx.guild.id
    async with get_guild_lock(guild_id):
        q = get_queue(guild_id)
        for song in selected_songs:
            q.append({
                "title": song["title"],
                "url": song["url"],
                "id": song["url"].split("=")[1]
            })
        random.shuffle(q)

    await ctx.send(f"Shuffled {len(selected_songs)} random songs and added them to the queue!")
    vc = get_voice_client_for_guild(guild_id)
    if not vc or not vc.is_playing():
        if ctx.author.voice and ctx.author.voice.channel:
            try:
                vc = await ctx.author.voice.channel.connect()
                set_voice_client_for_guild(guild_id, vc)
                await play_next_for_guild(guild_id, ctx.channel.id)
            except Exception:
                logger.exception("Failed to connect to voice channel for guild %s", guild_id)
                await ctx.send("Failed to connect to your voice channel.")
        else:
            await ctx.send("You must be in a voice channel for me to join and play music.")

@bot.command(name="shutdown")
@check_bot_ready()
@is_bot_owner()
async def shutdown(ctx):
    """Shuts down bot/container! (owner only)"""
    await ctx.send("Shutting down the bot...")
    for gid, vc in list(guild_voice_clients.items()):
        try:
            if vc and vc.is_connected():
                await vc.disconnect()
        except Exception:
            logger.exception("Error disconnecting VC during shutdown for guild %s", gid)
    await bot.close()

@bot.command(name="remove")
@check_bot_ready()
@is_bot_owner()
async def remove_song(ctx, video_id: str):
    """Removes song from library! (owner only)"""
    try:
        library = load_library()
        if video_id not in library:
            await ctx.send(f"No song found with ID: {video_id}")
            return

        song_title = library[video_id]["title"]
        del library[video_id]
        save_library(library)

        file_path = download_folder_path / f"{video_id}.webm"
        if file_path.exists():
            file_path.unlink()
            await ctx.send(f"Successfully removed '{song_title}' from the library and deleted the file.")
        else:
            await ctx.send(f"Removed '{song_title}' from the library, but file was not found in downloads folder.")

        for gid, q in guild_queues.items():
            guild_queues[gid] = [song for song in q if song.get("id") != video_id]

    except FileNotFoundError:
        await ctx.send("Error: Library file not found!")
    except json.JSONDecodeError:
        await ctx.send("Error: Could not read library file!")
    except Exception as e:
        logger.exception("Error removing song %s: %s", video_id, e)
        await ctx.send(f"An error occurred: {str(e)}")

# Help command
class SupremeHelpCommand(commands.HelpCommand):
    def get_command_signature(self, command):
        return "%s%s %s" % (self.context.clean_prefix, command.qualified_name, command.signature)

    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="Help", color=discord.Color.blurple())
        for cog, commands_ in mapping.items():
            filtered = await self.filter_commands(commands_, sort=True)
            if command_signatures := [self.get_command_signature(c) for c in filtered]:
                cog_name = getattr(cog, "qualified_name", " ")
                embed.add_field(name=cog_name, value="\n".join(command_signatures), inline=False)
        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(title=self.get_command_signature(command), color=discord.Color.blurple())
        if command.help:
            embed.description = command.help
        if alias := command.aliases:
            embed.add_field(name="Aliases", value=", ".join(alias), inline=False)
        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_help_embed(self, title, description, commands_):
        embed = discord.Embed(title=title, description=description or "No help found...")
        if filtered_commands := await self.filter_commands(commands_):
            for command in filtered_commands:
                embed.add_field(name=self.get_command_signature(command), value=command.help or "No help found...")
        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group):
        title = self.get_command_signature(group)
        await self.send_help_embed(title, group.help, group.commands)

    async def send_cog_help(self, cog):
        title = cog.qualified_name or "No"
        await self.send_help_embed(f"{title} Category", cog.description, cog.get_commands())

    async def send_error_message(self, error):
        embed = discord.Embed(title="Error", description=error, color=discord.Color.red())
        channel = self.get_destination()
        await channel.send(embed=embed)

bot.help_command = SupremeHelpCommand()

# Events and startup
@bot.event
async def on_ready():
    logger.info("Bot is logged in as %s. Scanning library...", bot.user.name)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _scan_and_update_library_sync)
    logger.info("Library scan task scheduled/completed.")

if __name__ == "__main__":
    bot.run(config_manager.bot_token)