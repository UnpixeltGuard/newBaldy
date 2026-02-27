import os
from dataclasses import dataclass
from dotenv import load_dotenv

_SENSITIVE_KEYS = {"BOT_TOKEN", "YOUTUBE_API_KEY"}

@dataclass
class BotConfig:
    bot_token: str
    bot_owner: int
    youtube_api_key: str
    max_song_time: int
    download_folder: str

class ConfigManager:
    def __init__(self, config_file_path: str = ".env"):
        self.config_file_path = config_file_path
        self._config: BotConfig | None = None
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.config_file_path):
            raise FileNotFoundError(
                f"Config file not found: '{self.config_file_path}'\n"
                f"Copy config.env to {self.config_file_path} and fill in your values."
            )

        load_dotenv(self.config_file_path, override=True)

        missing = []
        required = ["BOT_TOKEN", "BOT_OWNER", "YOUTUBE_API_KEY", "MAX_SONG_TIME", "DOWNLOAD_FOLDER"]
        for key in required:
            if not os.getenv(key):
                missing.append(key)

        if missing:
            raise ValueError(
                f"Missing required config keys: {', '.join(missing)}\n"
                f"Check your {self.config_file_path} file."
            )

        try:
            bot_owner = int(os.environ["BOT_OWNER"])
        except ValueError:
            raise ValueError(
                f"BOT_OWNER must be a numeric Discord user ID, "
                f"got: '{os.environ['BOT_OWNER']}'"
            )

        try:
            max_song_time = int(os.environ["MAX_SONG_TIME"])
        except ValueError:
            raise ValueError(
                f"MAX_SONG_TIME must be an integer (seconds), "
                f"got: '{os.environ['MAX_SONG_TIME']}'"
            )

        if max_song_time <= 0:
            raise ValueError(f"MAX_SONG_TIME must be greater than 0, got: {max_song_time}")

        self._config = BotConfig(
            bot_token=os.environ["BOT_TOKEN"],
            bot_owner=bot_owner,
            youtube_api_key=os.environ["YOUTUBE_API_KEY"],
            max_song_time=max_song_time,
            download_folder=os.environ["DOWNLOAD_FOLDER"],
        )

        for key in _SENSITIVE_KEYS:
            os.environ.pop(key, None)

    @property
    def bot_token(self) -> str:
        return self._config.bot_token

    @property
    def bot_owner(self) -> int:
        return self._config.bot_owner

    @property
    def youtube_api_key(self) -> str:
        return self._config.youtube_api_key

    @property
    def max_song_time(self) -> int:
        return self._config.max_song_time

    @property
    def download_folder(self) -> str:
        return self._config.download_folder

    def __repr__(self) -> str:
        return (
            f"ConfigManager("
            f"bot_token='***', "
            f"bot_owner={self._config.bot_owner}, "
            f"youtube_api_key='***', "
            f"max_song_time={self._config.max_song_time}, "
            f"download_folder='{self._config.download_folder}'"
            f")"
        )