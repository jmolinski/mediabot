from __future__ import annotations

import os

from collections import namedtuple

from telegram import Audio, Bot, Update
from telegram.ext import CallbackContext

import mp3_utils
import youtube_utils

from common import send_reply_audio
from image_utils import (
    DESIRED_THUMBNAIL_FORMAT,
    convert_image_to_format,
    crop_image_to_square,
)
from message import MsgWrapper
from settings import get_default_logger
from utils import extract_youtube_id, generate_random_filename

AudioFile = namedtuple("AudioFile", "path is_temporary")


async def download_audio_file(bot: Bot, audio: Audio) -> None:
    file_data = await bot.get_file(audio.file_id)

    b = bytearray()
    await file_data.download_as_bytearray(b)

    with open(f"media/{audio.file_unique_id}.mp3", "wb") as f:
        f.write(b)


async def download_audio_file_if_not_in_cache(bot: Bot, audio: Audio) -> None:
    if not os.path.exists(f"media/{audio.file_unique_id}.mp3"):
        await download_audio_file(bot, audio)


async def post_audio_to_telegram(
    update: Update,
    context: CallbackContext,
    filepath: str,
) -> None:
    ret = await send_reply_audio(update, filepath)
    await download_audio_file_if_not_in_cache(context.bot, ret.audio)


async def download_files_from_youtube(links: list[str]) -> list[str]:
    return [youtube_utils.download_song(extract_youtube_id(link)) for link in links]


async def fetch_targets(context: CallbackContext, msg: MsgWrapper) -> list[AudioFile]:
    if msg.has_parent:
        if msg.parent_msg.has_audio:
            audio = msg.parent_msg.audio
            await download_audio_file_if_not_in_cache(context.bot, audio)
            return [AudioFile(f"media/{audio.file_unique_id}.mp3", is_temporary=False)]
        return []

    return [
        AudioFile(filepath, is_temporary=True)
        for filepath in await download_files_from_youtube(msg.extract_youtube_links())
    ]


async def handler_message(update: Update, context: CallbackContext) -> None:
    get_default_logger().info("Message received")

    msg = MsgWrapper(update.message)

    files_to_edit = await fetch_targets(context, msg)

    for target in files_to_edit:
        # TODO run metadata updaters before posting (if present in original msg)
        await post_audio_to_telegram(update, context, target.path)
        if target.is_temporary:
            os.remove(target.path)

    if msg.text.startswith("title"):
        pass


async def handler_picture(update: Update, context: CallbackContext) -> None:
    get_default_logger().info("Picture received")

    msg = MsgWrapper(update.message)
    if not msg.has_parent:
        return

    files_to_edit = await fetch_targets(context, msg)
    if not files_to_edit:
        return
    assert len(files_to_edit) == 1
    target = files_to_edit[0]

    picture_filename = generate_random_filename()
    await (await msg.picture).download_to_drive(picture_filename)

    thumbnail = convert_image_to_format(picture_filename, DESIRED_THUMBNAIL_FORMAT)
    os.remove(picture_filename)

    crop_image_to_square(thumbnail)
    mp3_utils.set_cover(target.path, thumbnail)

    await post_audio_to_telegram(update, context, target.path)

    os.remove(thumbnail)
