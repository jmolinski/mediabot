from __future__ import annotations

import itertools
import os
import shutil
import traceback

from telegram import Audio, Bot, Update
from telegram.ext import CallbackContext

import mp3_utils
import youtube_utils

from image_utils import (
    DESIRED_THUMBNAIL_FORMAT,
    convert_image_to_format,
    crop_image_to_square,
)
from message import MsgWrapper
from sending_messages import send_reply, send_reply_audio
from settings import get_default_logger
from utils import extract_youtube_id, generate_random_filename

METADATA_TRANSFORMERS = ("title", "artist", "album")
LENGTH_TRANSFORMERS = ("cut", "cuthead")
TRANSFORMERS = METADATA_TRANSFORMERS + LENGTH_TRANSFORMERS


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


async def download_files_from_youtube_if_not_in_cache(links: list[str]) -> list[str]:
    targets = []

    for link in links:
        yt_id = extract_youtube_id(link)

        original_filepath = f"media/{yt_id}.mp3"
        if not os.path.exists(original_filepath):
            youtube_utils.download_song(yt_id)
        assert os.path.exists(original_filepath)

        copy_filepath = original_filepath.replace(yt_id, generate_random_filename())
        shutil.copyfile(original_filepath, copy_filepath)

        targets.append(copy_filepath)

    return targets


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

    return await download_files_from_youtube_if_not_in_cache(
        msg.extract_youtube_links()
    )


def find_transformers(msg: MsgWrapper) -> list[list[str]]:
    nonempty_lines = [
        line.strip().split(" ") for line in msg.text.split("\n") if line.strip()
    ]
    transformers = [line for line in nonempty_lines if line[0] in TRANSFORMERS]

    assert len(transformers) == len(set(t[0] for t in transformers))
    return transformers


def apply_transformer(filepath: str, name: str, args: list[str]) -> list[str]:
    if name in METADATA_TRANSFORMERS:
        mp3_utils.change_metadata(filepath, name, " ".join(args))
        return [filepath]
    elif name == "cut":
        start, end = args
        mp3_utils.cut_audio(filepath, start, end)
        return [filepath]
    elif name == "cuthead":
        assert len(args) <= 1, "Too many arguments for cuthead (expected 0 or 1)"
        seconds = int(args[0]) if args else 5
        filepaths: list[str] = []
        for i in range(1, seconds + 1):
            filepaths.append(
                mp3_utils.cut_audio(filepath, start=i, end=0, overwrite=False)
            )
        os.remove(filepath)
        return filepaths
    else:
        raise Exception("Unknown transformer name: " + name)


def apply_transformers(filepath: str, transformers: list[list[str]]) -> list[str]:
    filepaths = [filepath]
    for name, *args in transformers:
        filepaths = list(
            itertools.chain.from_iterable(
                apply_transformer(filepath, name, args) for filepath in filepaths
            )
        )
    return filepaths


async def handler_message(update: Update, context: CallbackContext) -> None:
    get_default_logger().info("Message received")

    msg = MsgWrapper(update.message)
    if not msg.is_authorized():
        return

    files_to_edit = await fetch_targets(context, msg)

    transformers = find_transformers(msg)

    for target in files_to_edit:
        transformed_target = apply_transformers(target, transformers)

        for f in transformed_target:
            await post_audio_to_telegram(update, context, f)
            os.remove(f)


async def handler_picture(update: Update, context: CallbackContext) -> None:
    get_default_logger().info("Picture received")

    msg = MsgWrapper(update.message)
    if not msg.is_authorized():
        return

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


async def log_error_and_send_info_to_parent(
    update: object, context: CallbackContext
) -> None:
    if not isinstance(update, Update):
        get_default_logger().error(
            f"Unknown event {update} caused error", exc_info=context.error
        )
        return

    get_default_logger().error(f"Update {update} caused error", exc_info=context.error)

    if not update.message:
        return

    try:
        ex = context.error
        assert isinstance(ex, Exception)
        str_exp = "".join(traceback.format_exception(context.error))
        await send_reply(update, context, f"```{str_exp}```", parse_mode="MarkdownV2")
    except Exception as e:
        get_default_logger().error("Error while sending error message: ", exc_info=e)
