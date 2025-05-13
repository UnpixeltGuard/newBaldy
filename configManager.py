import os
import json
import functools

class ConfigManager:
    def __init__(self, config_file_path):
        self.config_file_path = config_file_path
        self.config_cache = {}
        
        self._load_config_items(['DOWNLOAD_FOLDER', 'MAX_SONG_TIME'])
    
    def _load_config_items(self, keys):
        if not os.path.exists(self.config_file_path):
            raise FileNotFoundError(f"Configuration file not found at {self.config_file_path}")
            
        with open(self.config_file_path, 'r') as f:
            for line in f.readlines():
                if '=' in line:
                    key, value = line.strip().split('=')
                    key = key.strip()
                    if key in keys and key not in self.config_cache:
                        self.config_cache[key] = value.strip()
    
    def get(self, key):
        if key not in self.config_cache:
            self._load_config_items([key])
        return self.config_cache.get(key)
    
    def get_int(self, key):
        return int(self.get(key))
    
    def clear_sensitive(self, key):
        if key in self.config_cache:
            del self.config_cache[key]


def with_config(config_keys):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            from newBaldyYTv3 import config_manager
            
            for key in config_keys:
                config_manager.get(key)
            
            result = await func(*args, **kwargs)
            
            for key in config_keys:
                if key in ['BOT_TOKEN', 'YOUTUBE_API_KEY']:
                    config_manager.clear_sensitive(key)
            
            return result
        return wrapper
    return decorator