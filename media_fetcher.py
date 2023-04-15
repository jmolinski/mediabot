from __future__ import annotations

import re
import shutil

from pathlib import Path

from telegram import Update
from telegram.ext import CallbackContext

import utils
import youtube_utils

from message import MsgWrapper
from settings import get_settings
from telegram_helpers import (
    download_audio_file_from_telegram_if_not_in_cache,
    log_exception_and_notify_chat,
)
from utils import generate_random_filename_in_cache

BANDCAMP_PLAYLIST_PATTERN = re.compile(
    r"^https://[\w\-]+\.bandcamp\.com/album/[\w\-]+$"
)
BANDCAMP_SONG_PATTERN = re.compile(r"^https://[\w\-]+\.bandcamp\.com/track/[\w\-]+$")

YOUTUBE_PLAYLIST_PATTERN = re.compile(
    r"^https?://(?:www\.)?(?:music\.)?youtube\.com/playlist\?(list=[\w-]+)$"
)
YOUTUBE_SONG_PATTERNS = [
    re.compile(r"^https://(?:www\.)?youtu\.be/([\w-]+)$"),
    re.compile(
        r"^https?://(?:www\.)?(?:music\.)?youtube\.com/watch\?(?=.*v=)(?:\S+)?v=([\w-]+)(?:\S+)?$"
    ),
]

SOUNDCLOUD_PLAYLIST_PATTERNS = re.compile(
    r"^https://soundcloud\.com/[\w\-]+/sets/[\w\-]+$"
)
SOUNDCLOUD_SONG_PATTERNS = re.compile(r"^https://soundcloud\.com/[\w\-]+/[\w\-]+$")


async def download_audio_from_url_if_not_in_cache(
    update: Update, context: CallbackContext, links: list[str]
) -> list[Path]:
    targets = []

    for link in links:
        try:
            original_filepath = utils.cache_path_for_mp3_url(link)
            if not original_filepath.exists():
                downloaded_song = youtube_utils.ytdl_download_song(link)
                assert downloaded_song.as_posix() == original_filepath.as_posix()
            assert original_filepath.exists()

            copy_filepath = generate_random_filename_in_cache(".mp3")
            shutil.copyfile(original_filepath, copy_filepath)

            targets.append(copy_filepath)
        except Exception as e:
            await log_exception_and_notify_chat(update, context, e)

    return targets


async def fetch_parent_message_target(
    context: CallbackContext, msg: MsgWrapper
) -> list[Path]:
    if msg.has_parent and msg.parent_msg.has_audio:
        audio = msg.parent_msg.audio
        await download_audio_file_from_telegram_if_not_in_cache(context.bot, audio)
        original_filepath = get_settings().cache_dir / f"{audio.file_unique_id}.mp3"
        copy_filepath = generate_random_filename_in_cache(".mp3")
        shutil.copyfile(original_filepath, copy_filepath)
        return [copy_filepath]
    return []


async def extract_video_links(
    text: str,
    song_patterns: list[re.Pattern],
    playlist_patterns: list[re.Pattern],
) -> list[str]:
    links_in_text = [t for t in text.split() if t.startswith("https")]

    song_links: list[str] = []
    for song_pattern in song_patterns:
        song_links.extend([p for p in links_in_text if re.match(song_pattern, p)])

    for playlist_pattern in playlist_patterns:
        playlist_links = [p for p in links_in_text if re.match(playlist_pattern, p)]
        for playlist_link in playlist_links:
            song_links.extend(youtube_utils.playlist_url_to_video_urls(playlist_link))

    return [utils.remove_query_parameter_from_url(url, "list") for url in song_links]


async def collect_link_targets(text: str) -> list[str]:
    patterns_for_services: list[tuple[list[re.Pattern], list[re.Pattern]]] = [
        (YOUTUBE_SONG_PATTERNS, [YOUTUBE_PLAYLIST_PATTERN]),
        ([BANDCAMP_SONG_PATTERN], [BANDCAMP_PLAYLIST_PATTERN]),
        ([SOUNDCLOUD_SONG_PATTERNS], [SOUNDCLOUD_PLAYLIST_PATTERNS]),
    ]

    links = []
    for patterns_for_service in patterns_for_services:
        links.extend(await extract_video_links(text, *patterns_for_service))
    return links


async def fetch_targets(
    update: Update, context: CallbackContext, msg: MsgWrapper
) -> list[Path]:
    parent_message_target = await fetch_parent_message_target(context, msg)
    if parent_message_target:
        return parent_message_target

    links = await collect_link_targets(msg.text)

    return await download_audio_from_url_if_not_in_cache(update, context, links)
