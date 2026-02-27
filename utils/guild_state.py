import asyncio
import discord
from typing import Dict, List, Optional, Any

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


def set_voice_client(guild_id: int, vc: Optional[discord.VoiceClient]) -> None:
    if vc is None:
        guild_voice_clients.pop(guild_id, None)
    else:
        guild_voice_clients[guild_id] = vc


def get_voice_client(guild_id: int) -> Optional[discord.VoiceClient]:
    return guild_voice_clients.get(guild_id)
