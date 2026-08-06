# mediabot
telegram bot for fetching yt audio and editing telegram audio files

## Setup

Install dependencies with `uv sync --python 3.13`.

This project uses `uv` for dependency management and execution. `yt-dlp` is installed with its `default` extra so the `yt-dlp-ejs` companion package is included for YouTube extraction. You also need a JavaScript runtime such as Deno or Node on `PATH` for that extractor support.

Run the bot with `./run.sh`, which wraps `uv run --frozen --python 3.13 python main.py`.

Run linters with `./linters.sh`, which wraps `uv run --frozen --python 3.13 --group dev isort .`, `black .`, `ruff .`, and `mypy .`.

Requires a config.json file in the root directory with the following format:

```json
{
  "token": "your telegram bot token",
  "log_file": "log.log",
  "allowed_users": [
    123456789
  ],
  "allowed_groups": [
    -123456789
  ],
  "cache_dir": "media",
  "cache_timeout_minutes": 720
}
```

At least one of `allowed_users` / `allowed_groups` must be non-empty; the bot refuses
to start otherwise, so it is never open to arbitrary users. Keep `config.json` out of
version control — it holds the bot token.

2. TODOs

- mass set tags -> 'apply to all next'?
