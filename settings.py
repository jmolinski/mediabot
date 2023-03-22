import json
import logging

from pathlib import Path


class Settings:
    token: str
    log_file: Path
    authorized_users: list[int]
    authorized_chats: list[int]
    authorize_all: bool
    cache_dir: Path
    cache_timeout_seconds: int

    def __init__(self, filename: str) -> None:
        with open(filename) as f:
            filecontents = json.loads(f.read())

        self.token = filecontents["token"]

        self.log_file = Path(filecontents["log_file"])
        self.log_file.touch(exist_ok=True)

        self.authorized_users = filecontents["allowed_users"]
        self.authorized_chats = filecontents["allowed_groups"]
        self.authorize_all = (
            len(self.authorized_users) == len(self.authorized_chats) == 0
        )

        self.cache_timeout_seconds = int(filecontents["cache_timeout_minutes"]) * 60
        self.cache_dir = Path(filecontents["cache_dir"])
        if not self.cache_dir.is_dir():
            self.cache_dir.mkdir(parents=True)


def get_settings() -> Settings:
    return Settings("config.json")


LOGGER = None


def get_logger(settings: Settings) -> logging.Logger:
    global LOGGER

    if LOGGER:
        return LOGGER

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(settings.log_file), logging.StreamHandler()],
    )

    LOGGER = logging.getLogger("mediabot_logger")
    return LOGGER


def get_default_logger() -> logging.Logger:
    return get_logger(get_settings())


def disable_logger(name: str) -> None:
    logger = logging.getLogger(name)
    logger.setLevel(logging.WARNING)
