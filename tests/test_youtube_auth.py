import json
import logging
import os
import tempfile
import unittest

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import mp3_utils
import youtube_utils

from settings import Settings


class YouTubeAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.config_path = self.directory / "config.json"
        self.config: dict[str, Any] = {
            "token": "test-token",
            "log_file": str(self.directory / "test.log"),
            "allowed_users": [1],
            "allowed_groups": [],
            "cache_dir": str(self.directory / "media"),
            "cache_timeout_minutes": 60,
        }
        environment = patch.dict(
            os.environ,
            {"YOUTUBE_COOKIE_FILE": "", "YOUTUBE_COOKIES_FROM_BROWSER": ""},
        )
        environment.start()
        self.addCleanup(environment.stop)

    def load_settings(self) -> Settings:
        self.config_path.write_text(json.dumps(self.config))
        return Settings(str(self.config_path))

    def test_auth_is_optional(self) -> None:
        settings = self.load_settings()
        with patch.object(youtube_utils, "get_settings", return_value=settings):
            self.assertEqual(youtube_utils._yt_dlp_auth_args(), [])

    def test_config_overrides_environment_and_file_overrides_browser(self) -> None:
        cookie_file = self.directory / "cookies.txt"
        cookie_file.touch()
        os.environ["YOUTUBE_COOKIE_FILE"] = "unused-cookies.txt"
        os.environ["YOUTUBE_COOKIES_FROM_BROWSER"] = "firefox"
        self.config.update(
            youtube_cookie_file=str(cookie_file), youtube_cookies_from_browser="chrome"
        )
        settings = self.load_settings()
        self.assertEqual(settings.youtube_cookie_file, cookie_file)
        self.assertEqual(settings.youtube_cookies_from_browser, "chrome")
        with patch.object(youtube_utils, "get_settings", return_value=settings):
            self.assertEqual(
                youtube_utils._yt_dlp_auth_args(), ["--cookies", str(cookie_file)]
            )

    def test_environment_cookie_sources_reach_downloads_and_playlists(self) -> None:
        cookie_file = self.directory / "cookies.txt"
        cookie_file.touch()
        cases = [
            (
                {"YOUTUBE_COOKIE_FILE": str(cookie_file)},
                ["--cookies", str(cookie_file)],
            ),
            (
                {"YOUTUBE_COOKIES_FROM_BROWSER": "firefox"},
                ["--cookies-from-browser", "firefox"],
            ),
        ]
        for environment, expected in cases:
            with (
                self.subTest(environment=environment),
                patch.dict(os.environ, environment),
            ):
                settings = self.load_settings()
                with (
                    patch.object(youtube_utils, "get_settings", return_value=settings),
                    patch.object(
                        youtube_utils,
                        "cache_path_for_mp3_url",
                        return_value=self.directory / "audio.mp3",
                    ),
                    patch.object(
                        youtube_utils,
                        "get_default_logger",
                        return_value=logging.getLogger("test"),
                    ),
                ):
                    downloads: tuple[Callable[[], object], ...] = (
                        lambda: youtube_utils.ytdl_download_song(
                            "https://example.com/audio", False
                        ),
                        lambda: youtube_utils.playlist_url_to_video_urls(
                            "https://example.com/playlist"
                        ),
                    )
                    for download in downloads:
                        with patch.object(
                            youtube_utils,
                            "run_command",
                            side_effect=RuntimeError("intercepted"),
                        ) as command:
                            with self.assertRaisesRegex(RuntimeError, "intercepted"):
                                download()
                            args = command.call_args.args[0]
                            position = args.index(expected[0])
                            self.assertEqual(args[position : position + 2], expected)

    def test_missing_cookie_file_fails_before_running_yt_dlp(self) -> None:
        self.config.update(
            youtube_cookie_file=str(self.directory / "missing.txt"),
            youtube_cookies_from_browser="chrome",
        )
        settings = self.load_settings()
        with (
            patch.object(youtube_utils, "get_settings", return_value=settings),
            patch.object(youtube_utils, "run_command") as command,
        ):
            with self.assertRaisesRegex(FileNotFoundError, "YouTube cookie file"):
                youtube_utils.playlist_url_to_video_urls("https://example.com/playlist")
            command.assert_not_called()

    def test_unreadable_audio_reports_a_clear_error(self) -> None:
        with patch.object(mp3_utils.eyed3, "load", return_value=None):
            with self.assertRaisesRegex(ValueError, "Could not read metadata"):
                mp3_utils.read_metadata(self.directory / "invalid.mp3")


if __name__ == "__main__":
    unittest.main()
