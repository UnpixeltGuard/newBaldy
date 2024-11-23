import os
import discord
from discord.ext import commands, tasks
from discord.ext.commands import is_owner
import yt_dlp
import requests
import random
import asyncio

# Get directory of Python script
script_dir = os.path.dirname(os.path.realpath(__file__))
# Full path to the config file relative to the script directory
config_file_path = os.path.join(script_dir, 'config.txt')
# Load config.txt file
config = {}
try:
    with open(config_file_path, 'r') as f:
        for line in f.readlines():
            if '=' in line:
                key, value = line.strip().split('=')
                config[key.strip()] = value.strip()
except FileNotFoundError:
    print(f"Configuration file 'config.txt' not found at {config_file_path}. Please ensure it's in the same directory as the script.")
    exit(1)

# Map config.txt to app
BOT_TOKEN = config['BOT_TOKEN']
BOT_OWNER = int(config['BOT_OWNER'])
MAX_SONG_TIME = int(config['MAX_SONG_TIME'])
DOWNLOAD_FOLDER = config['DOWNLOAD_FOLDER']
INVIDIOUS_URL = config['INVIDIOUS_URL']

# Create download folder
download_folder_path = os.path.join(script_dir, DOWNLOAD_FOLDER)
if not os.path.exists(download_folder_path):
    os.makedirs(download_folder_path)

# Create bot instance
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Song queue and voice client
song_queue = []
voice_client = None

# Download song with yt-dlp
def download_song(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(download_folder_path, '%(id)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info_dict)
        return filename

# Search song with Invidious API
def search_song(query):
    search_url = f"{INVIDIOUS_URL}/api/v1/search?q={query}"
    try:
        response = requests.get(search_url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Ensure it's a list and contains video entries
        if isinstance(data, list) and len(data) > 0:
            return data
        else:
            print(f"Unexpected API response: {data}")
            return []
    except requests.RequestException as e:
        print(f"Error connecting to Invidious API: {e}")
        return []
    except ValueError as e:
        print(f"Error parsing JSON from Invidious API: {e}")
        return []

# Add song to queue and play it
async def add_to_queue_and_play(ctx, song_name: str):
    song_info = search_song(song_name)
    if not song_info:
        await ctx.send("No results found! Please try a different query.")
        return
    video = song_info[0]  
    if 'title' not in video or 'videoId' not in video:
        await ctx.send("Invalid song data received from the search. Please try again.")
        return

    song_title = video['title']
    video_url = f"https://www.youtube.com/watch?v={video['videoId']}"

    # Check if song is already loaded
    file_path = os.path.join(download_folder_path, f"{video['videoId']}.webm")
    
    if not os.path.exists(file_path):
        await ctx.send(f"Downloading {song_title}...")
        download_song(video_url)
        await ctx.send(f"Downloaded {song_title}.")

    song_queue.append({'title': song_title, 'url': video_url, 'id': video['videoId']})
    await ctx.send(f"Added {song_title} to the queue.")

    # Start playing if not playing
    if not voice_client or not voice_client.is_playing():
        await play_song(ctx)

# Play next song in queue
async def play_song(ctx):
    global voice_client
    if not song_queue:
        await ctx.send("No songs in the queue!")
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
        return

    song = song_queue.pop(0)
    song_file = os.path.join(download_folder_path, f"{song['id']}.webm")
    voice_channel = ctx.author.voice.channel

    if voice_channel:
        if not voice_client or not voice_client.is_connected():
            voice_client = await voice_channel.connect()

        def after_playback(error):
            if error:
                print(f"Playback error: {error}")
            # Stop playback if not stopped
            if voice_client and voice_client.is_playing():
                voice_client.stop()  

            asyncio.run_coroutine_threadsafe(play_song(ctx), bot.loop)

        try:
            audio_source = discord.FFmpegPCMAudio(song_file)
            voice_client.play(audio_source, after=after_playback)
            await ctx.send(f"Now playing: {song['title']}")
        except discord.ClientException as e:
            await ctx.send(f"Error playing audio: {e}")

# Show song queue
@bot.command(name="queue")
async def show_queue(ctx):
    if not song_queue:
        await ctx.send("The queue is empty!")
    else:
        # Display current queue
        queue_list = "\n".join([f"{idx + 1}. {song['title']}" for idx, song in enumerate(song_queue)])
        await ctx.send(f"Current Queue:\n{queue_list}")
# Skip song
@bot.command(name="skip")
async def skip(ctx):
    global voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send("Skipped the current song!")
    else:
        await ctx.send("No song is currently playing to skip.")
# Stop music and disconnect bot
@bot.command(name="stop")
async def stop(ctx):
    global voice_client
    if voice_client:
        voice_client.stop()
        await voice_client.disconnect()
    song_queue.clear()
    await ctx.send("Stopped the music and cleared the queue!")

# Owner-only commands
@bot.command(name="shutdown")
@is_owner()
async def shutdown(ctx):
    await ctx.send("Shutting down the bot...")
    await bot.close()
# Queue song and play it
@bot.command(name="play")
async def play(ctx, *, song_name: str):
    await add_to_queue_and_play(ctx, song_name)
# Pick 10 random songs, queue, shuffle and play them
@bot.command(name="shuffle")
async def shuffle(ctx):
    all_files = [f for f in os.listdir(download_folder_path) if f.endswith('.webm')]
    random_files = random.sample(all_files, min(10, len(all_files)))
    for filename in random_files:
        song_id = filename.split('.')[0] 
        video_url = f"https://www.youtube.com/watch?v={song_id}"

        song_info = search_song(video_url)

        if isinstance(song_info, list) and len(song_info) > 0:
            video = song_info[0]
            song_title = video.get('title', 'Unknown Title')
            song_queue.append({'title': song_title, 'url': video_url, 'id': song_id})

    random.shuffle(song_queue)
    await ctx.send(f"Shuffled {len(random_files)} random songs and added them to the queue!")

    if not voice_client or not voice_client.is_playing():
        await play_song(ctx)

# Start bot
@bot.event
async def on_ready():
    print(f"Bot is ready. Logged in as {bot.user.name}")

bot.run(BOT_TOKEN)
