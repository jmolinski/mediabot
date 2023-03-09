# mediabot
telegram bot for fetching yt audio and editing telegram audio files


1. local cache cleared every 24h

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
  ]
}
```
