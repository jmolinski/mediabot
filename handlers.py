from __future__ import annotations

import os

from telegram import Audio, Bot, Update
from telegram.ext import CallbackContext

import youtube_utils

from common import send_reply_audio
from message import MsgWrapper
from settings import get_default_logger
from utils import extract_youtube_id


async def download_audio_file(bot: Bot, audio: Audio) -> None:
    file_data = await bot.get_file(audio.file_id)

    b = bytearray()
    await file_data.download_as_bytearray(b)

    with open(f"media/{audio.file_unique_id}.mp3", "wb") as f:
        f.write(b)


async def download_audio_file_if_not_in_cache(bot: Bot, audio: Audio) -> None:
    if not os.path.exists(f"media/{audio.file_unique_id}.mp3"):
        await download_audio_file(bot, audio)


async def handle_download_from_youtube(
    update: Update, context: CallbackContext, links: list[str]
) -> None:
    for link in links:
        yt_id = extract_youtube_id(link)
        filepath = youtube_utils.download_song(yt_id)

        assert update.message is not None
        ret = await send_reply_audio(update, filepath)
        # TODO run metadata updaters before posting (if present in original msg)
        await download_audio_file_if_not_in_cache(context.bot, ret.audio)

        os.remove(filepath)


async def handler_message(update: Update, context: CallbackContext) -> None:
    get_default_logger().info("Message received")

    msg = MsgWrapper(update.message)

    if not msg.has_parent:
        if yt_links := msg.extract_youtube_links():
            await handle_download_from_youtube(update, context, yt_links)
        return

    print("\n\n\n")
    print(msg.parent_msg.audio)
    print("\n\n\n")

    if msg.text.startswith("title"):
        pass
