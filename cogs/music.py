import logging
import random
from pathlib import Path
from typing import Optional
import asyncio
import discord
from discord.ext import commands
from configManager import ConfigManager
from utils import guild_state
from utils.library import load_library
from utils.downloader import download_song, search_song, get_song_file_path

logger = logging.getLogger("newBaldy.music")


class MusicCog(commands.Cog, name="Music"):
    def __init__(
        self,
        bot: commands.Bot,
        config_manager: ConfigManager,
        download_folder_path: Path,
        library_path: Path,
        download_folder: str,
    ):
        self.bot = bot
        self.config_manager = config_manager
        self.download_folder_path = download_folder_path
        self.library_path = library_path
        self.download_folder = download_folder

# Helpers

    async def play_next(self, guild_id: int, text_channel_id: int) -> None:
        try:
            queue = guild_state.get_queue(guild_id)
            if not queue:
                vc = guild_state.get_voice_client(guild_id)
                if vc and vc.is_connected():
                    try:
                        await vc.disconnect()
                    except Exception:
                        logger.exception("Error disconnecting voice client for guild %s", guild_id)
                    guild_state.set_voice_client(guild_id, None)
                channel = self.bot.get_channel(text_channel_id)
                if channel:
                    await channel.send("Queue finished — disconnecting.")
                return

            song = queue.pop(0)
            song_file = get_song_file_path(song["id"], self.download_folder_path)
            channel = self.bot.get_channel(text_channel_id)

            if not song_file:
                if channel:
                    await channel.send(f"Error: audio file not found for **{song['title']}**, skipping.")
                await self.play_next(guild_id, text_channel_id)
                return

            vc = guild_state.get_voice_client(guild_id)
            if not vc or not vc.is_connected():
                if channel:
                    await channel.send(
                        "Bot is no longer connected to a voice channel. "
                        "Use `!play` while in a voice channel to start again."
                    )
                return

            def _after(error, g_id=guild_id, ch_id=text_channel_id):
                if error:
                    logger.exception("Playback error for guild %s: %s", g_id, error)
                self.bot.loop.call_soon_threadsafe(
                    asyncio.create_task, self.play_next(g_id, ch_id)
                )

            try:
                vc.play(discord.FFmpegPCMAudio(song_file), after=_after)
                if channel:
                    await channel.send(f"Now playing: **{song['title']}**")
            except Exception as e:
                logger.exception("Error starting playback for guild %s: %s", guild_id, e)
                if channel:
                    await channel.send(f"Error playing audio: {e}")
                await self.play_next(guild_id, text_channel_id)

        except Exception:
            logger.exception("Unexpected error in play_next for guild %s", guild_id)

    async def _connect_and_play(self, ctx: commands.Context) -> None:
        guild_id = ctx.guild.id
        vc = guild_state.get_voice_client(guild_id)
        if not vc or not vc.is_playing():
            if ctx.author.voice and ctx.author.voice.channel:
                try:
                    vc = await ctx.author.voice.channel.connect()
                    guild_state.set_voice_client(guild_id, vc)
                except Exception:
                    logger.exception("Failed to connect to voice channel for guild %s", guild_id)
                    await ctx.send("Failed to connect to your voice channel.")
                    return
                await self.play_next(guild_id, ctx.channel.id)
            else:
                await ctx.send("You must be in a voice channel for me to join and play music.")

    async def _queue_song(
        self,
        ctx: commands.Context,
        song_title: str,
        video_url: str,
        video_id: str,
    ) -> None:
        if not get_song_file_path(video_id, self.download_folder_path):
            await ctx.send(f"Downloading **{song_title}**...")
            downloaded = await download_song(
                video_url, ctx,
                self.download_folder_path,
                self.config_manager.max_song_time,
                self.library_path,
                self.download_folder,
            )
            if downloaded is None:
                return
            await ctx.send(f"Downloaded **{song_title}**.")

        async with guild_state.get_guild_lock(ctx.guild.id):
            guild_state.get_queue(ctx.guild.id).append(
                {"title": song_title, "url": video_url, "id": video_id}
            )
        await ctx.send(f"Added **{song_title}** to the queue.")
        await self._connect_and_play(ctx)

    def _search_library(self, query: str):
        lib = load_library(self.library_path)
        query_lower = query.lower()
        for song in lib.values():
            if query_lower in song.get("title", "").lower():
                return song
        return None

# Commands

    @commands.command(name="search")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def search(self, ctx: commands.Context, *, query: str):
        """Searches YouTube for a song and shows the top result."""
        await ctx.send(f"Searching for: {query}")
        results = await search_song(query, self.config_manager.youtube_api_key)
        if not results:
            await ctx.send("No results found. Try a different search.")
            return

        embed = discord.Embed(title="Search Results", color=discord.Color.blue())
        for i, result in enumerate(results, 1):
            embed.add_field(
                name=f"{i}. {result['title']}",
                value=f"By: {result['author']}\nID: `{result['videoId']}`",
                inline=False,
            )
        embed.set_footer(text="Use !play <song title> to queue a song.")
        await ctx.send(embed=embed)

    @commands.command(name="play")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def play(self, ctx: commands.Context, *, song_name: str):
        """Plays a song — checks local library first, then YouTube."""

        # 1. Check local library before making any network calls
        local = self._search_library(song_name)
        if local:
            video_id = local["url"].split("=")[-1]
            if get_song_file_path(video_id, self.download_folder_path):
                await ctx.send(f"Found **{local['title']}** in local library.")
                await self._queue_song(ctx, local["title"], local["url"], video_id)
                return

        # 2. Call YouTube API (results cached for 5 min)
        results = await search_song(song_name, self.config_manager.youtube_api_key)

        if results:
            video = results[0]
            if "title" not in video or "videoId" not in video:
                await ctx.send("Invalid data from search. Please try again.")
                return
            await self._queue_song(
                ctx,
                video["title"],
                f"https://www.youtube.com/watch?v={video['videoId']}",
                video["videoId"],
            )
            return

        # 3. Fall back to yt_dlp if YouTube API returns nothing
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "default_search": "ytsearch",
            }

            def _ytsearch(query: str):
                import yt_dlp
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(query, download=False)

            info = await asyncio.to_thread(_ytsearch, song_name)
            if not info or "entries" not in info or not info["entries"]:
                await ctx.send("No results found. Try a different query.")
                return

            video = info["entries"][0]
            video_url = video.get("webpage_url", "")
            video_id = video.get("id", "")
            song_title = video.get("title", song_name)

            if not video_url:
                await ctx.send("No results found. Try a different query.")
                return

            await ctx.send(f"No API result found — using yt_dlp fallback: **{song_title}**")
            await self._queue_song(ctx, song_title, video_url, video_id)

        except Exception as e:
            logger.exception("yt_dlp fallback search failed: %s", e)
            await ctx.send(f"Error searching for song: {e}")

    @commands.command(name="queue")
    async def show_queue(self, ctx: commands.Context):
        """Shows the current queue."""
        queue = guild_state.get_queue(ctx.guild.id)
        if not queue:
            await ctx.send("The queue is empty!")
            return
        lines = "\n".join(f"{i + 1}. {s['title']}" for i, s in enumerate(queue))
        await ctx.send(f"**Current Queue:**\n{lines}")

    @commands.command(name="skip")
    async def skip(self, ctx: commands.Context):
        """Skips the current song."""
        vc = guild_state.get_voice_client(ctx.guild.id)
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send("Skipped!")
        else:
            await ctx.send("Nothing is playing right now.")

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        """Stops playback and clears the queue."""
        guild_id = ctx.guild.id
        vc = guild_state.get_voice_client(guild_id)
        if vc:
            try:
                vc.stop()
                if vc.is_connected():
                    await vc.disconnect()
            except Exception:
                logger.exception("Error stopping voice client for guild %s", guild_id)
            guild_state.set_voice_client(guild_id, None)
        guild_state.guild_queues[guild_id] = []
        await ctx.send("Stopped and cleared the queue.")

    @commands.command(name="library")
    async def library(self, ctx: commands.Context, *, query: Optional[str] = None):
        """Lists or searches the downloaded song library."""
        lib = load_library(self.library_path)
        if not lib:
            await ctx.send("The song library is empty!")
            return

        if query is None:
            songs = list(lib.values())[:20]
            lines = "\n".join(f"• {s['title']} (by {s['uploader']})" for s in songs)
            await ctx.send(f"**First 20 songs in the library:**\n{lines}")
            return

        matches = [s for s in lib.values() if query.lower() in s["title"].lower()]
        if not matches:
            await ctx.send(f"No songs found matching `{query}`.")
            return

        lines = "\n".join(
            f"• {s['title']} (by {s['uploader']}) [ID: `{s['url'].split('=')[1]}`]"
            for s in matches
        )
        await ctx.send(f"**Songs matching '{query}':**\n{lines}")

    @commands.command(name="shuffle")
    async def shuffle(self, ctx: commands.Context):
        """Adds 10 random songs from the library to the queue and shuffles it."""
        lib = load_library(self.library_path)
        if not lib:
            await ctx.send("The song library is empty!")
            return

        selected = random.sample(list(lib.values()), min(10, len(lib)))
        guild_id = ctx.guild.id

        async with guild_state.get_guild_lock(guild_id):
            q = guild_state.get_queue(guild_id)
            for song in selected:
                q.append({
                    "title": song["title"],
                    "url": song["url"],
                    "id": song["url"].split("=")[1],
                })
            random.shuffle(q)

        await ctx.send(f"Shuffled {len(selected)} random songs into the queue!")
        await self._connect_and_play(ctx)


async def setup(
    bot: commands.Bot,
    config_manager: ConfigManager,
    download_folder_path: Path,
    library_path: Path,
    download_folder: str,
):
    await bot.add_cog(
        MusicCog(bot, config_manager, download_folder_path, library_path, download_folder)
    )
