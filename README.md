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

At least one of `allowed_users` / `allowed_groups` must be non-empty, otherwise the bot
refuses to start. To intentionally run an open bot, set `"allow_all_users": true`.
Keep `config.json` out of version control — it holds the bot token.

### Optional YouTube authentication

For videos that require a logged-in YouTube session, configure either:

- `youtube_cookie_file` in `config.json` or `YOUTUBE_COOKIE_FILE` in the environment, pointing to a Netscape-format cookies export.
- `youtube_cookies_from_browser` in `config.json` or `YOUTUBE_COOKIES_FROM_BROWSER` in the environment, for example `chrome` or `firefox`.

Config values take precedence over the corresponding environment variables. If both cookie sources are set, the cookie file takes precedence. Both downloads and playlist expansion use these settings. Leave them unset to download without authentication. Cookies grant access to your account, so keep exports private and out of version control.

2. TODOs

- mass set tags -> 'apply to all next'?
