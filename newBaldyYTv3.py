import os
import json
import discord
from discord.ext import commands, tasks
from discord.ext.commands import is_owner
import yt_dlp
import requests
import random
import asyncio
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Global variable to track bot readiness
bot_ready = False
# Get directory of Python script
script_dir = os.path.dirname(os.path.realpath(__file__))
# Full path to the config file relative to the script directory
config_file_path = os.path.join(script_dir, 'config.txt')
INDEX_FOLDER = os.path.join(script_dir, 'index')
os.makedirs(INDEX_FOLDER, exist_ok=True)
library_path = os.path.join(INDEX_FOLDER, 'song_library.json')
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
YOUTUBE_API_KEY = config['YOUTUBE_API_KEY']

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

def update_song_library(song_info):
    """Update the song library index with information about a downloaded song."""
    
    # Load existing library or create new one
    if os.path.exists(library_path):
        with open(library_path, 'r', encoding='utf-8') as f:
            library = json.load(f)
    else:
        library = {}
    
    # Extract relevant information
    song_id = song_info['id']
    song_data = {
        'title': song_info.get('title', 'Unknown Title'),
        'duration': song_info.get('duration', 0),
        'uploader': song_info.get('uploader', 'Unknown Uploader'),
        'filename': os.path.join(DOWNLOAD_FOLDER, f"{song_id}.webm"),
        'url': f"https://www.youtube.com/watch?v={song_id}",
        'download_date': song_info.get('download_date', '')
    }
    
    # Update library
    library[song_id] = song_data
    
    # Save updated library
    with open(library_path, 'w', encoding='utf-8') as f:
        json.dump(library, f, indent=4, ensure_ascii=False)


# Scan the downloads directory and update song_library.json with any songs not already in the index.
def scan_and_update_library():
    global bot_ready
    try:
        # Load existing library or create new one
        if os.path.exists(library_path):
            with open(library_path, 'r', encoding='utf-8') as f:
                library = json.load(f)
        else:
            library = {}
        
        # Scan downloads directory
        downloaded_files = [f for f in os.listdir(download_folder_path) if f.endswith('.webm')]
        
        # Track new songs added
        new_songs_count = 0
        
        for filename in downloaded_files:
            # Extract song ID from filename
            song_id = filename.split('.')[0]
            
            # Skip if song is already in library
            if song_id in library:
                continue
            
            # Construct YouTube URL
            video_url = f"https://www.youtube.com/watch?v={song_id}"
            
            try:
                # Try to get song info using yt-dlp for more reliable metadata
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'no_color': True,
                    'extract_flat': True
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    video_info = ydl.extract_info(video_url, download=False)
                
                # Prepare song data
                song_data = {
                    'title': video_info.get('title', 'Unknown Title'),
                    'duration': video_info.get('duration', 0),
                    'uploader': video_info.get('uploader', 'Unknown Uploader'),
                    'filename': os.path.join(DOWNLOAD_FOLDER, filename),
                    'url': video_url,
                    'download_date': ''  # We don't know the exact download date
                }
                
                # Add to library
                library[song_id] = song_data
                new_songs_count += 1
            
            except Exception as e:
                print(f"Error processing song {song_id}: {e}")
        
        # Save updated library
        with open(library_path, 'w', encoding='utf-8') as f:
            json.dump(library, f, indent=4, ensure_ascii=False)
        
        bot_ready = True
        print(f"Library scan complete. Added {new_songs_count} new songs. Bot is now ready to accept commands.")
    except Exception as e:
        print(f"Error during library scan: {e}")
        bot_ready = True  # Ensure bot becomes ready even if scan fails

def check_bot_ready():
    async def predicate(ctx):
        if not bot_ready:
            await ctx.send("⏳ Bot is still initializing. Please wait a moment.")
            return False
        return True
    return commands.check(predicate)

# Download song with yt-dlp
async def download_song(url, ctx):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(download_folder_path, '%(id)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # First, extract info without downloading
        info_dict = ydl.extract_info(url, download=False)
        
        # Check song duration
        duration = info_dict.get('duration', 0)
        if duration > MAX_SONG_TIME:
            await ctx.send(f"❌ Song duration ({duration} seconds) exceeds max allowed duration of {MAX_SONG_TIME} seconds!")
            return None

        # If duration is acceptable, proceed with download
        info_dict = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info_dict)
        update_song_library(info_dict)
        return filename

# Search Youtube API
def search_song(query):
    """Search for a song using YouTube Data API v3."""
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        
        # Perform the search
        search_response = youtube.search().list(
            q=query,
            part='snippet',
            maxResults=1,
            type='video'
        ).execute()

        # Check if we got any results
        if not search_response.get('items'):
            print(f"[YouTube API] No results found for query: {query}")
            return []

        # Format the response to match the expected structure
        results = []
        for item in search_response['items']:
            video_data = {
                'title': item['snippet']['title'],
                'videoId': item['id']['videoId'],
                'author': item['snippet']['channelTitle']
            }
            results.append(video_data)
            
            # Log the result for debugging
            print("[YouTube API] Search Result:")
            print(f"  Title: {video_data['title']}")
            print(f"  Video ID: {video_data['videoId']}")
            print(f"  Channel: {video_data['author']}")

        return results
        
    except HttpError as e:
        print(f"[YouTube API] Error making API request: {e}")
        return []
    except Exception as e:
        print(f"[YouTube API] Unexpected error: {e}")
        return []

# Add song to queue and play it
async def add_to_queue_and_play(ctx, song_name: str):
    song_info = search_song(song_name)
    if not song_info:
        # If Invidious search fails, try direct YouTube search and download
        try:
            # More verbose logging
            print(f"[YouTube Search] Attempting to search for: {song_name}")
            
            ydl_opts = {
                'quiet': True,  # Change to False to see more output
                'no_warnings': False,  # Change to False to see warnings
                'extract_flat': True,  # Change to False to get full video info
                'default_search': 'ytsearch',  # Explicitly set default search
                'verbose': True  # Add verbose logging
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Prepend 'ytsearch:' to ensure YouTube search
                search_query = song_name
                print(f"[YouTube Search] Search query: {search_query}")
                
                try:
                    info = ydl.extract_info(search_query, download=False)
                    print(f"[YouTube Search] Raw info: {info}")
                except Exception as search_err:
                    print(f"[YouTube Search] Search extraction error: {search_err}")
                    await ctx.send(f"Error searching YouTube: {search_err}")
                    return
                
                # Handle both playlist and single video results
                if 'entries' in info and info['entries']:
                    video = info['entries'][0]
                    print(f"[YouTube Search] First video: {video}")
                else:
                    print("[YouTube Search] No entries found")
                    await ctx.send("No YouTube results found for the song.")
                    return

            song_title = video.get('title', song_name)
            video_url = video.get('webpage_url', '')
            video_id = video.get('id', '')

            print(f"[YouTube Search] Song details - Title: {song_title}, URL: {video_url}, ID: {video_id}")

            if not video_url:
                await ctx.send("No results found! Please try a different query.")
                return

            # Send message about downloading
            await ctx.send(f"No results in index. Downloading first result: {song_title}")

            # Attempt to download the song
            downloaded_file = await download_song(video_url, ctx)
            if downloaded_file is None:
                return  # Song was too long or download failed

        except Exception as e:
            print(f"[YouTube Search] Unexpected error: {e}")
            await ctx.send(f"Error searching for song: {e}")
            return
    else:
        video = song_info[0]  
        if 'title' not in video or 'videoId' not in video:
            await ctx.send("Invalid song data received from the search. Please try again.")
            return

        song_title = video['title']
        video_url = f"https://www.youtube.com/watch?v={video['videoId']}"
        video_id = video['videoId']

    # Check if song is already loaded
    file_path = os.path.join(download_folder_path, f"{video_id}.webm")
    
    if not os.path.exists(file_path):
        await ctx.send(f"Downloading {song_title}...")
        downloaded_file = await download_song(video_url, ctx)
        if downloaded_file is None:
            return  # Song was too long, so we stop here
        await ctx.send(f"Downloaded {song_title}.")

    song_queue.append({'title': song_title, 'url': video_url, 'id': video_id})
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
@check_bot_ready()
async def show_queue(ctx):
    if not song_queue:
        await ctx.send("The queue is empty!")
    else:
        # Display current queue
        queue_list = "\n".join([f"{idx + 1}. {song['title']}" for idx, song in enumerate(song_queue)])
        await ctx.send(f"Current Queue:\n{queue_list}")

# Skip song
@bot.command(name="skip")
@check_bot_ready()
async def skip(ctx):
    global voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send("Skipped the current song!")
    else:
        await ctx.send("No song is currently playing to skip.")

# Stop music and disconnect bot
@bot.command(name="stop")
@check_bot_ready()
async def stop(ctx):
    global voice_client
    if voice_client:
        voice_client.stop()
        await voice_client.disconnect()
    song_queue.clear()
    await ctx.send("Stopped the music and cleared the queue!")

# Library command
@bot.command(name="library")
@check_bot_ready()
async def library(ctx, *, query: str = None):
    """
    Show library contents. 
    Without a query, shows first 20 songs.
    With a query, searches for songs matching the title.
    """
    
    # Check if library exists
    if not os.path.exists(library_path):
        await ctx.send("The song library is empty!")
        return
    
    # Load library
    with open(library_path, 'r', encoding='utf-8') as f:
        library = json.load(f)
    
    # If library is empty
    if not library:
        await ctx.send("The song library is empty!")
        return
    
    # If no query, show first 20 songs
    if query is None:
        songs_list = list(library.values())[:20]
        response = "📚 First 20 songs in the library:\n" + "\n".join([
            f"• {song['title']} (by {song['uploader']})" for song in songs_list
        ])
        await ctx.send(response)
        return
    
    # Search for songs matching the query
    matching_songs = [
        song for song in library.values() 
        if query.lower() in song['title'].lower()
    ]
    
    # If no matching songs
    if not matching_songs:
        await ctx.send(f"No songs found matching '{query}'.")
        return
    
    # Show matching songs
    response = f"🔍 Songs matching '{query}':\n" + "\n".join([
        f"• {song['title']} (by {song['uploader']})" for song in matching_songs
    ])
    await ctx.send(response)

# Owner-only commands
@bot.command(name="shutdown")
@check_bot_ready()
@is_owner()
async def shutdown(ctx):
    await ctx.send("Shutting down the bot...")
    await bot.close()

# Queue song and play it
@bot.command(name="shuffle")
@check_bot_ready()
async def shuffle(ctx):
    # Load the song library
    try:
        with open(library_path, 'r', encoding='utf-8') as f:
            library = json.load(f)
    except FileNotFoundError:
        await ctx.send("No songs in library!")
        return
    except json.JSONDecodeError:
        await ctx.send("Error reading song library!")
        return

    if not library:
        await ctx.send("The song library is empty!")
        return

    # Get 10 random songs from the library
    selected_songs = random.sample(list(library.values()), min(10, len(library)))
    
    # Add them to the queue
    for song in selected_songs:
        song_queue.append({
            'title': song['title'],
            'url': song['url'],
            'id': song['url'].split('=')[1]  # Extract video ID from URL
        })

    # Shuffle the queue
    random.shuffle(song_queue)
    await ctx.send(f"Shuffled {len(selected_songs)} random songs and added them to the queue!")

    # Start playing if not already playing
    if not voice_client or not voice_client.is_playing():
        await play_song(ctx)

# Start bot
@bot.event
async def on_ready():
    global bot_ready
    print(f"Bot is logged in. Logged in as {bot.user.name}. Scanning library...")
    
    # Run library scan in a separate thread to prevent blocking
    def run_scan():
        scan_and_update_library()
    
    # Use asyncio to run the blocking scan in a separate thread
    await bot.loop.run_in_executor(None, run_scan)

bot.run(BOT_TOKEN)
