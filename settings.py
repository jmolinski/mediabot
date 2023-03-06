import json


class Settings:
    token: str

    def __init__(self, filename: str) -> None:
        with open(filename) as f:
            filecontents = json.loads(f.read())

        self.token = filecontents["token"]


def get_settings() -> Settings:
    return Settings("config.json")
