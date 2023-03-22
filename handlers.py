from __future__ import annotations

import itertools
import os
import shutil
import time
import traceback

from pathlib import Path

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
from sending_messages import (
    download_file_from_telegram_if_not_in_cache,
    send_reply,
    send_reply_audio,
)
from settings import get_default_logger, get_settings
from utils import extract_youtube_id, generate_random_filename_in_cache

METADATA_TRANSFORMERS = ("title", "artist", "album")
LENGTH_TRANSFORMERS = ("cut", "cuthead")
TRANSFORMERS = METADATA_TRANSFORMERS + LENGTH_TRANSFORMERS


async def download_audio_file_from_telegram_if_not_in_cache(
    bot: Bot, audio: Audio
) -> Path:
    return await download_file_from_telegram_if_not_in_cache(
        bot, audio.file_id, audio.file_unique_id, "mp3"
    )


async def post_audio_to_telegram(
    update: Update, context: CallbackContext, audio_filepath: Path
) -> Path:
    ret = await send_reply_audio(update, audio_filepath)
    return await download_audio_file_from_telegram_if_not_in_cache(
        context.bot, ret.audio
    )


async def download_files_from_youtube_if_not_in_cache(links: list[str]) -> list[Path]:
    targets = []

    for link in links:
        yt_id = extract_youtube_id(link)

        original_filepath = get_settings().cache_dir / f"{yt_id}.mp3"
        if not original_filepath.exists():
            youtube_utils.download_song(yt_id)
        assert original_filepath.exists()

        copy_filepath = generate_random_filename_in_cache(".mp3")
        shutil.copyfile(original_filepath, copy_filepath)

        targets.append(copy_filepath)

    return targets


async def fetch_targets(context: CallbackContext, msg: MsgWrapper) -> list[Path]:
    if msg.has_parent:
        if not msg.parent_msg.has_audio:
            return []

        audio = msg.parent_msg.audio
        await download_audio_file_from_telegram_if_not_in_cache(context.bot, audio)
        original_filepath = get_settings().cache_dir / f"{audio.file_unique_id}.mp3"
        copy_filepath = generate_random_filename_in_cache(".mp3")
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


def apply_transformer(filepath: Path, name: str, args: list[str]) -> list[Path]:
    if name in METADATA_TRANSFORMERS:
        mp3_utils.change_metadata(filepath, name, " ".join(args))
        return [filepath]
    elif name == "cut":
        start, end = args
        return [mp3_utils.cut_audio(filepath, start, end)]
    elif name == "cuthead":
        assert len(args) <= 1, "Too many arguments for cuthead (expected 0 or 1)"
        seconds = int(args[0]) if args else 5
        filepaths: list[Path] = [
            mp3_utils.cut_audio(filepath, start=i, end=0, overwrite=False)
            for i in range(1, seconds + 1)
        ]
        filepath.unlink()
        return filepaths
    else:
        raise Exception("Unknown transformer name: " + name)


def apply_transformers(filepath: Path, transformers: list[list[str]]) -> list[Path]:
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
    cleanup_cache()

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
    cleanup_cache()

    if not msg.has_parent:
        return

    files_to_edit = await fetch_targets(context, msg)
    if not files_to_edit:
        return
    assert len(files_to_edit) == 1
    target = files_to_edit[0]

    picture_filename = generate_random_filename_in_cache()
    await (await msg.picture).download_to_drive(picture_filename)

    thumbnail = convert_image_to_format(picture_filename, DESIRED_THUMBNAIL_FORMAT)
    picture_filename.unlink()

    crop_image_to_square(thumbnail)
    mp3_utils.set_cover(target, thumbnail)

    await post_audio_to_telegram(update, context, target)

    thumbnail.unlink()


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


def cleanup_cache() -> None:
    cutoff_time = time.time() - get_settings().cache_timeout_seconds

    for filename in get_settings().cache_dir.iterdir():
        if filename.name == ".gitkeep":
            continue
        if filename.stat().st_mtime < cutoff_time:
            filename.unlink()
