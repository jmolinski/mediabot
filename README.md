# mediabot
telegram bot for fetching yt audio and editing telegram audio files

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

2. TODOs

- mass set tags -> 'apply to all next'?
