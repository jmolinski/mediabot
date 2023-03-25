from __future__ import annotations

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

METADATA_TRANSFORMERS = ("title", "artist", "album")
LENGTH_TRANSFORMERS = ("cut", "cuthead")
TRANSFORMERS = METADATA_TRANSFORMERS + LENGTH_TRANSFORMERS


async def download_audio_from_url_if_not_in_cache(
    update: Update, context: CallbackContext, links: list[str]
) -> list[Path]:
    targets = []

    for link in links:
        try:
            original_filepath = utils.cache_path_for_url(link)
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


async def extract_bandcamp_links(text: str) -> list[str]:
    links_in_text = [t for t in text.split() if "https" in t]

    bandcamp_links = [p for p in links_in_text if ".bandcamp.com/" in p]
    playlist_links = [p for p in bandcamp_links if ".com/album/" in p]
    video_links = [p for p in bandcamp_links if p not in playlist_links]

    for playlist_link in playlist_links:
        video_links.extend(youtube_utils.playlist_url_to_video_urls(playlist_link))

    return video_links


async def extract_youtube_links(text: str) -> list[str]:
    links_in_text = [t for t in text.split() if "https" in t]
    # TODO fix to regexes
    youtube_links = [
        p for p in links_in_text if ("youtube.com" in p or "youtu.be" in p)
    ]
    playlist_links = [p for p in youtube_links if "/playlist?" in p]
    video_links = [p for p in youtube_links if p not in playlist_links]

    for playlist_link in playlist_links:
        video_links.extend(youtube_utils.playlist_url_to_video_urls(playlist_link))

    return video_links


async def collect_link_targets(msg: MsgWrapper) -> list[str]:
    link_extractors = [extract_youtube_links, extract_bandcamp_links]
    links = []
    for link_extractor in link_extractors:
        links.extend(await link_extractor(msg.text))
    return links


async def fetch_targets(
    update: Update, context: CallbackContext, msg: MsgWrapper
) -> list[Path]:
    parent_message_target = await fetch_parent_message_target(context, msg)
    if parent_message_target:
        return parent_message_target

    links = await collect_link_targets(msg)

    return await download_audio_from_url_if_not_in_cache(update, context, links)
