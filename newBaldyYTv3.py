import os
import json
import discord
from discord.ext import commands, tasks
from discord.ext.commands import is_owner
import yt_dlp
import random
import asyncio
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from configManager import ConfigManager, with_config

bot_ready = False
script_dir = os.path.dirname(os.path.realpath(__file__))
config_file_path = os.path.join(script_dir, 'config.txt')
INDEX_FOLDER = os.path.join(script_dir, 'index')
os.makedirs(INDEX_FOLDER, exist_ok=True)
library_path = os.path.join(INDEX_FOLDER, 'song_library.json')

config_manager = ConfigManager(config_file_path)

MAX_SONG_TIME = config_manager.get_int('MAX_SONG_TIME')
DOWNLOAD_FOLDER = config_manager.get('DOWNLOAD_FOLDER')

download_folder_path = os.path.join(script_dir, DOWNLOAD_FOLDER)
if not os.path.exists(download_folder_path):
    os.makedirs(download_folder_path)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
bot.config_manager = config_manager

song_queue = []
voice_client = None

def update_song_library(song_info):
    if os.path.exists(library_path):
        with open(library_path, 'r', encoding='utf-8') as f:
            library = json.load(f)
    else:
        library = {}
    
    song_id = song_info['id']
    song_data = {
        'title': song_info.get('title', 'Unknown Title'),
        'duration': song_info.get('duration', 0),
        'uploader': song_info.get('uploader', 'Unknown Uploader'),
        'filename': os.path.join(DOWNLOAD_FOLDER, f"{song_id}.webm"),
        'url': f"https://www.youtube.com/watch?v={song_id}",
        'download_date': song_info.get('download_date', '')
    }
    
    library[song_id] = song_data
    
    with open(library_path, 'w', encoding='utf-8') as f:
        json.dump(library, f, indent=4, ensure_ascii=False)

def scan_and_update_library():
    global bot_ready
    try:
        if os.path.exists(library_path):
            with open(library_path, 'r', encoding='utf-8') as f:
                library = json.load(f)
        else:
            library = {}
        
        downloaded_files = [f for f in os.listdir(download_folder_path) if f.endswith('.webm')]
        
        new_songs_count = 0
        
        for filename in downloaded_files:
            song_id = filename.split('.')[0]
            
            if song_id in library:
                continue
            
            video_url = f"https://www.youtube.com/watch?v={song_id}"
            
            try:
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'no_color': True,
                    'extract_flat': True
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    video_info = ydl.extract_info(video_url, download=False)
                
                song_data = {
                    'title': video_info.get('title', 'Unknown Title'),
                    'duration': video_info.get('duration', 0),
                    'uploader': video_info.get('uploader', 'Unknown Uploader'),
                    'filename': os.path.join(DOWNLOAD_FOLDER, filename),
                    'url': video_url,
                    'download_date': ''
                }
                
                library[song_id] = song_data
                new_songs_count += 1
            
            except Exception as e:
                print(f"Error processing song {song_id}: {e}")
        
        with open(library_path, 'w', encoding='utf-8') as f:
            json.dump(library, f, indent=4, ensure_ascii=False)
        
        bot_ready = True
        print(f"Library scan complete. Added {new_songs_count} new songs. Bot is now ready to accept commands.")
    except Exception as e:
        print(f"Error during library scan: {e}")
        bot_ready = True

def check_bot_ready():
    async def predicate(ctx):
        if not bot_ready:
            await ctx.send("⏳ Bot is still initializing. Please wait a moment.")
            return False
        return True
    return commands.check(predicate)

def get_song_file_path(song_id):
    for ext in ['.webm', '.m4a', '.mp3', '.opus']:
        file_path = os.path.join(download_folder_path, f"{song_id}{ext}")
        if os.path.exists(file_path):
            return file_path
    return None

async def download_song(url, ctx):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(download_folder_path, '%(id)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'force_generic_extractor': False,
        'youtube_include_dash_manifest': False,
        'ignoreerrors': True,
        'verbose': False
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            
            duration = info_dict.get('duration', 0)
            if duration > MAX_SONG_TIME:
                await ctx.send(f"❌ Song duration ({duration} seconds) exceeds max allowed duration of {MAX_SONG_TIME} seconds!")
                return None

            info_dict = ydl.extract_info(url, download=True)
            video_id = info_dict['id']
            actual_file = get_song_file_path(video_id)
            if actual_file is None:
                await ctx.send("❌ Error: Downloaded file not found!")
                return None
                
            update_song_library(info_dict)
            return actual_file
    except Exception as e:
        await ctx.send(f"❌ Download error: {str(e)}")
        return None

@with_config(['YOUTUBE_API_KEY'])
async def search_song(query):
    try:
        youtube = build('youtube', 'v3', developerKey=config_manager.get('YOUTUBE_API_KEY'))
        
        search_response = youtube.search().list(
            q=query,
            part='snippet',
            maxResults=1,
            type='video'
        ).execute()

        if not search_response.get('items'):
            print(f"[YouTube API] No results found for query: {query}")
            return []

        results = []
        for item in search_response['items']:
            video_data = {
                'title': item['snippet']['title'],
                'videoId': item['id']['videoId'],
                'author': item['snippet']['channelTitle']
            }
            results.append(video_data)
            
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

async def add_to_queue_and_play(ctx, song_name: str):
    song_info = await search_song(song_name)
    if not song_info:
        try:
            print(f"[YouTube Search] Attempting to search for: {song_name}")
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': False,
                'extract_flat': True,
                'default_search': 'ytsearch',
                'verbose': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                search_query = song_name
                print(f"[YouTube Search] Search query: {search_query}")
                
                try:
                    info = ydl.extract_info(search_query, download=False)
                    print(f"[YouTube Search] Raw info: {info}")
                except Exception as search_err:
                    print(f"[YouTube Search] Search extraction error: {search_err}")
                    await ctx.send(f"Error searching YouTube: {search_err}")
                    return
                
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

            await ctx.send(f"No results in index. Downloading first result: {song_title}")

            downloaded_file = await download_song(video_url, ctx)
            if downloaded_file is None:
                return

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

    file_path = os.path.join(download_folder_path, f"{video_id}.webm")
    
    if not os.path.exists(file_path):
        await ctx.send(f"Downloading {song_title}...")
        downloaded_file = await download_song(video_url, ctx)
        if downloaded_file is None:
            return
        await ctx.send(f"Downloaded {song_title}.")

    song_queue.append({'title': song_title, 'url': video_url, 'id': video_id})
    await ctx.send(f"Added {song_title} to the queue.")

    if not voice_client or not voice_client.is_playing():
        await play_song(ctx)

async def play_song(ctx):
    global voice_client
    if not song_queue:
        await ctx.send("No songs in the queue!")
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
        return

    song = song_queue.pop(0)
    song_file = get_song_file_path(song['id'])
    
    if not song_file:
        await ctx.send(f"❌ Error: Could not find audio file for {song['title']}")
        await play_song(ctx)
        return

    voice_channel = ctx.author.voice.channel

    if voice_channel:
        if not voice_client or not voice_client.is_connected():
            voice_client = await voice_channel.connect()

        def after_playback(error):
            if error:
                print(f"Playback error: {error}")
            if voice_client and voice_client.is_playing():
                voice_client.stop()
            
            asyncio.run_coroutine_threadsafe(play_song(ctx), bot.loop)

        try:
            audio_source = discord.FFmpegPCMAudio(song_file)
            voice_client.play(audio_source, after=after_playback)
            await ctx.send(f"Now playing: {song['title']}")
        except Exception as e:
            await ctx.send(f"❌ Error playing audio: {str(e)}")
            await play_song(ctx)

@bot.command(name="search")
@check_bot_ready()
async def search(ctx, *, query: str):
    """Searches the Youtube API for a song!"""
    await ctx.send(f"🔍 Searching for: {query}")
    
    results = await search_song(query)
    
    if not results:
        await ctx.send("❌ No results found! Please try a different search term.")
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
    if not song_queue:
        await ctx.send("The queue is empty!")
    else:
        queue_list = "\n".join([f"{idx + 1}. {song['title']}" for idx, song in enumerate(song_queue)])
        await ctx.send(f"Current Queue:\n{queue_list}")

@bot.command(name="skip")
@check_bot_ready()
async def skip(ctx):
    """Skips the current song!"""
    global voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
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
    global voice_client
    if voice_client:
        voice_client.stop()
        await voice_client.disconnect()
    song_queue.clear()
    await ctx.send("Stopped the music and cleared the queue!")

@bot.command(name="library")
@check_bot_ready()
async def library(ctx, *, query: str = None):
    """Lists/Searches library of the Bot!"""
    if not os.path.exists(library_path):
        await ctx.send("The song library is empty!")
        return
    
    with open(library_path, 'r', encoding='utf-8') as f:
        library = json.load(f)
    
    if not library:
        await ctx.send("The song library is empty!")
        return
    
    if query is None:
        songs_list = list(library.values())[:20]
        response = "📚 First 20 songs in the library:\n" + "\n".join([
            f"• {song['title']} (by {song['uploader']})" for song in songs_list
        ])
        await ctx.send(response)
        return
    
    matching_songs = [
        song for song in library.values() 
        if query.lower() in song['title'].lower()
    ]
    
    if not matching_songs:
        await ctx.send(f"No songs found matching '{query}'.")
        return
    
    response = f"🔍 Songs matching '{query}':\n" + "\n".join([
        f"• {song['title']} (by {song['uploader']}) [ID: {song['url'].split('=')[1]}]" for song in matching_songs
    ])
    await ctx.send(response)

@bot.command(name="shuffle")
@check_bot_ready()
async def shuffle(ctx):
    """Shuffles 10 random songs from library into the playlist!"""
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

    selected_songs = random.sample(list(library.values()), min(10, len(library)))
    
    for song in selected_songs:
        song_queue.append({
            'title': song['title'],
            'url': song['url'],
            'id': song['url'].split('=')[1]
        })

    random.shuffle(song_queue)
    await ctx.send(f"Shuffled {len(selected_songs)} random songs and added them to the queue!")

    if not voice_client or not voice_client.is_playing():
        await play_song(ctx)

@bot.command(name="shutdown")
@check_bot_ready()
@is_owner()
@with_config(['BOT_OWNER'])
async def shutdown(ctx):
    """Shuts down bot/container!"""
    if ctx.author.id != int(config_manager.get('BOT_OWNER')):
        await ctx.send("You don't have permission to use this command.")
        return
    await ctx.send("Shutting down the bot...")
    await bot.close()

@bot.command(name="remove")
@check_bot_ready()
@is_owner()
@with_config(['BOT_OWNER'])
async def remove_song(ctx, video_id: str):
    """Removes song from library!"""
    if ctx.author.id != int(config_manager.get('BOT_OWNER')):
        await ctx.send("You don't have permission to use this command.")
        return
    try:
        with open(library_path, 'r', encoding='utf-8') as f:
            library = json.load(f)
        
        if video_id not in library:
            await ctx.send(f"❌ No song found with ID: {video_id}")
            return
        
        song_title = library[video_id]['title']
        
        del library[video_id]
        
        with open(library_path, 'w', encoding='utf-8') as f:
            json.dump(library, f, indent=4, ensure_ascii=False)
        
        file_path = os.path.join(download_folder_path, f"{video_id}.webm")
        if os.path.exists(file_path):
            os.remove(file_path)
            await ctx.send(f"✅ Successfully removed '{song_title}' from the library and deleted the file.")
        else:
            await ctx.send(f"⚠️ Removed '{song_title}' from the library, but file was not found in downloads folder.")
            
        global song_queue
        song_queue = [song for song in song_queue if song['id'] != video_id]
        
    except FileNotFoundError:
        await ctx.send("❌ Error: Library file not found!")
    except json.JSONDecodeError:
        await ctx.send("❌ Error: Could not read library file!")
    except Exception as e:
        await ctx.send(f"❌ An error occurred: {str(e)}")    


class SupremeHelpCommand(commands.HelpCommand):
    def get_command_signature(self, command):
        return '%s%s %s' % (self.context.clean_prefix, command.qualified_name, command.signature)

    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="Help", color=discord.Color.blurple())
        for cog, commands in mapping.items():
            filtered = await self.filter_commands(commands, sort=True)
            if command_signatures := [
                self.get_command_signature(c) for c in filtered
            ]:
                cog_name = getattr(cog, "qualified_name", " ")
                embed.add_field(name=cog_name, value="\n".join(command_signatures), inline=False)

        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(title=self.get_command_signature(command) , color=discord.Color.blurple())
        if command.help:
            embed.description = command.help
        if alias := command.aliases:
            embed.add_field(name="Aliases", value=", ".join(alias), inline=False)

        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_help_embed(self, title, description, commands):
        embed = discord.Embed(title=title, description=description or "No help found...")

        if filtered_commands := await self.filter_commands(commands):
            for command in filtered_commands:
                embed.add_field(name=self.get_command_signature(command), value=command.help or "No help found...")

        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group):
        title = self.get_command_signature(group)
        await self.send_help_embed(title, group.help, group.commands)

    async def send_cog_help(self, cog):
        title = cog.qualified_name or "No"
        await self.send_help_embed(f'{title} Category', cog.description, cog.get_commands())
    
    async def send_error_message(self, error):
        embed = discord.Embed(title="Error", description=error, color=discord.Color.red())
        channel = self.get_destination()

        await channel.send(embed=embed)


bot.help_command = SupremeHelpCommand()


@bot.event
async def on_ready():
    global bot_ready
    print(f"Bot is logged in. Logged in as {bot.user.name}. Scanning library...") 
    def run_scan():
        scan_and_update_library()
    await bot.loop.run_in_executor(None, run_scan)

if __name__ == "__main__":
    try:
        bot_token = config_manager.get('BOT_TOKEN')
        bot.run(bot_token)
        config_manager.clear_sensitive('BOT_TOKEN')
    except Exception as e:
        print(f"Error starting bot: {e}")