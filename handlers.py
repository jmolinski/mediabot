from __future__ import annotations

import itertools
import os
import time

from pathlib import Path

from telegram import Update
from telegram.ext import CallbackContext

import mp3_utils

from media_fetcher import fetch_targets
from message import MsgWrapper
from settings import get_default_logger, get_settings
from telegram_helpers import log_exception_and_notify_chat, post_audio_to_telegram
from utils import url_to_thumbnail_filename

METADATA_TRANSFORMERS = ("title", "artist", "album")
LENGTH_TRANSFORMERS = ("cut", "cuthead")
GENERAL_TRANSFORMERS = ("cover", "replacetitle")
TRANSFORMERS = METADATA_TRANSFORMERS + LENGTH_TRANSFORMERS + GENERAL_TRANSFORMERS


def find_transformers(text: str) -> list[list[str]]:
    nonempty_lines = [
        line.strip().split(" ") for line in text.split("\n") if line.strip()
    ]
    transformers = [line for line in nonempty_lines if line[0] in TRANSFORMERS]

    assert len(transformers) == len(set(t[0] for t in transformers))
    return transformers


def apply_transformer(filepath: Path, name: str, args: list[str]) -> list[Path]:
    if name in METADATA_TRANSFORMERS:
        mp3_utils.change_metadata(filepath, name, " ".join(args))
        return [filepath]
    elif name == "cover":
        picture_url = args[0]
        thumbnail_filepath = url_to_thumbnail_filename(picture_url)
        mp3_utils.set_cover(filepath, thumbnail_filepath)
        return [filepath]
    elif name == "replacetitle":
        # format: replacetitle a;b
        arg = " ".join(args).strip()
        if arg.endswith(";"):
            old_part, new_part = arg.strip(";"), ""
        else:
            old_part, new_part = arg.split(";")
        old_title = mp3_utils.read_metadata(filepath)["title"]
        new_title = old_title.replace(old_part, new_part).strip()
        mp3_utils.change_metadata(filepath, "title", new_title)
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


async def react_to_command(
    update: Update, context: CallbackContext, extra_text: str = ""
) -> None:
    msg = MsgWrapper(update.message)
    if not msg.is_authorized():
        return
    cleanup_cache()

    files_to_edit = await fetch_targets(update, context, msg)

    msg_text = msg.text + "\n" + extra_text
    transformers = find_transformers(msg_text)

    for target in files_to_edit:
        transformed_target = apply_transformers(target, transformers)

        for f in transformed_target:
            await post_audio_to_telegram(update, context, f)
            os.remove(f)


async def handler_message(update: Update, context: CallbackContext) -> None:
    get_default_logger().info("Message received")

    await react_to_command(update, context)


async def handler_picture(update: Update, context: CallbackContext) -> None:
    get_default_logger().info("Picture received")

    picture_url = (await MsgWrapper(update.message).picture).file_path

    await react_to_command(update, context, extra_text=f"cover {picture_url}")


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

    assert isinstance(context.error, Exception)
    await log_exception_and_notify_chat(update, context, context.error)


def cleanup_cache() -> None:
    cutoff_time = time.time() - get_settings().cache_timeout_seconds

    for filename in get_settings().cache_dir.iterdir():
        if filename.name == ".gitkeep":
            continue
        if filename.stat().st_mtime < cutoff_time:
            filename.unlink()
