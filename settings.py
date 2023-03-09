import json
import logging


class Settings:
    token: str
    log_file: str
    authorized_users: list[int]
    authorized_chats: list[int]

    def __init__(self, filename: str) -> None:
        with open(filename) as f:
            filecontents = json.loads(f.read())

        self.token = filecontents["token"]
        self.log_file = filecontents["log_file"]
        self.authorized_users = filecontents["allowed_users"]
        self.authorized_chats = filecontents["allowed_groups"]


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
