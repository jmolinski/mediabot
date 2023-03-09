from __future__ import annotations

import os
import shutil

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


async def fetch_targets(context: CallbackContext, msg: MsgWrapper) -> list[str]:
    if msg.has_parent:
        if not msg.parent_msg.has_audio:
            return []

        audio = msg.parent_msg.audio
        await download_audio_file_if_not_in_cache(context.bot, audio)
        original_filepath = f"media/{audio.file_unique_id}.mp3"
        copy_filepath = original_filepath.replace(
            audio.file_unique_id, generate_random_filename()
        )
        shutil.copyfile(original_filepath, copy_filepath)
        return [copy_filepath]

    return await download_files_from_youtube(msg.extract_youtube_links())


def find_transformers(msg: MsgWrapper) -> list[list[str]]:
    nonempty_lines = [
        line.strip().split(" ") for line in msg.text.split("\n") if line.strip()
    ]
    transformers = [
        line
        for line in nonempty_lines
        if line[0] in ("title", "artist", "album", "cut")
    ]
    for t in transformers:
        assert len(t) > 1

    assert len(transformers) == len(set(t[0] for t in transformers))
    return transformers


def apply_transformer(filepath: str, name: str, args: list[str]) -> None:
    if name in ("title", "artist", "album"):
        mp3_utils.change_metadata(filepath, name, " ".join(args))
    elif name == "cut":
        print(name, args)
    else:
        raise Exception("Unknown transformer name: " + name)


def apply_transformers(filepath: str, transformers: list[list[str]]) -> None:
    for name, *args in transformers:
        apply_transformer(filepath, name, args)


async def handler_message(update: Update, context: CallbackContext) -> None:
    get_default_logger().info("Message received")

    msg = MsgWrapper(update.message)

    files_to_edit = await fetch_targets(context, msg)

    transformers = find_transformers(msg)

    for target in files_to_edit:
        apply_transformers(target, transformers)
        await post_audio_to_telegram(update, context, target)
        os.remove(target)


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
    mp3_utils.set_cover(target, thumbnail)

    await post_audio_to_telegram(update, context, target)

    os.remove(thumbnail)
