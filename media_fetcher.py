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


async def fetch_targets(
    update: Update, context: CallbackContext, msg: MsgWrapper
) -> list[Path]:
    if msg.has_parent:
        if not msg.parent_msg.has_audio:
            return []

        audio = msg.parent_msg.audio
        await download_audio_file_from_telegram_if_not_in_cache(context.bot, audio)
        original_filepath = get_settings().cache_dir / f"{audio.file_unique_id}.mp3"
        copy_filepath = generate_random_filename_in_cache(".mp3")
        shutil.copyfile(original_filepath, copy_filepath)
        return [copy_filepath]

    youtube_links = youtube_utils.extract_youtube_links(msg.text)
    return await download_audio_from_url_if_not_in_cache(update, context, youtube_links)
