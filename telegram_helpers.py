from __future__ import annotations

import os
import traceback

from pathlib import Path
from typing import Any

from telegram import Audio, Bot, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext

import mp3_utils

from message import MsgWrapper
from settings import get_default_logger, get_settings

EMPTY_MSG = "\xad\xad"


TELEGRAM_BOT_MAX_FILE_SIZE = 50_000_000  # 50 MB


async def download_file_from_telegram_if_not_in_cache(
    bot: Bot, file_id: str, file_unique_id: str, ext: str
) -> Path:
    assert not ext.startswith(".")
    path = get_settings().cache_dir / f"{file_unique_id}.{ext}"
    if not path.exists():
        path.write_bytes(await download_file_from_telegram(bot, file_id))
    return path


async def download_file_from_telegram(bot: Bot, file_id: str) -> bytes:
    file_data = await bot.get_file(file_id)

    buffer = bytearray()
    await file_data.download_as_bytearray(buffer)
    return bytes(buffer)


async def send_message(
    bot: Bot,
    chat_id: int,
    parent_id: int | None = None,
    markup: InlineKeyboardMarkup | None = None,
    text: str | None = None,
    **kwargs: Any,
) -> MsgWrapper:
    if text is None:
        text = EMPTY_MSG

    base_args = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    if parent_id:
        base_args["reply_to_message_id"] = parent_id
    if markup:
        base_args["reply_markup"] = markup

    if kwargs:
        base_args.update(kwargs)

    sent_msg = MsgWrapper(await bot.send_message(**base_args))

    return sent_msg


async def send_reply(
    update: Update,
    context: CallbackContext,
    text: str,
    **kwargs: Any,
) -> MsgWrapper:
    parent_msg = MsgWrapper(update.message)
    reply_msg = await send_message(
        context.bot,
        parent_msg.chat_id,
        parent_msg.msg_id,
        None,
        text=text,
        **kwargs,
    )

    return reply_msg


async def send_reply_audio(
    update: Update,
    audio: Path,
    thumbnail: str | bytes | None = None,
    **kwargs: Any,
) -> MsgWrapper:
    assert update.message is not None

    filesize = os.path.getsize(audio)
    if filesize > TELEGRAM_BOT_MAX_FILE_SIZE:
        raise ValueError(
            f"Audio file size {audio} exceeds Telegram's limit "
            f"of 50 MB (has {filesize/1_000_000} mb)"
        )

    metadata = mp3_utils.read_metadata(audio)

    if "title" in metadata:
        metadata["filename"] = metadata["title"]

    if thumbnail is None:
        thumbnail = mp3_utils.read_cover_image(audio)
    if thumbnail:
        metadata["thumbnail"] = thumbnail

    metadata = {
        k: v
        for k, v in metadata.items()
        if k in ("title", "performer", "thumbnail", "filename", "duration")
    }

    return MsgWrapper(
        # TODO reply media group
        await update.message.reply_audio(
            audio=audio,
            **metadata,
            write_timeout=60,
            read_timeout=60,
            pool_timeout=60,
            connect_timeout=60,
            **kwargs,
        )
    )


async def log_exception_and_notify_chat(
    update: Update, context: CallbackContext, exc: Exception
) -> None:
    try:
        str_exp = "".join(traceback.format_exception(exc))
        await send_reply(update, context, f"```{str_exp}```", parse_mode="MarkdownV2")
    except Exception as e:
        get_default_logger().error("Error while sending error message: ", exc_info=e)


async def download_audio_file_from_telegram_if_not_in_cache(
    bot: Bot, audio: Audio
) -> Path:
    return await download_file_from_telegram_if_not_in_cache(
        bot, audio.file_id, audio.file_unique_id, "mp3"
    )


async def post_audio_to_telegram(
    update: Update, context: CallbackContext, audio_filepath: Path
) -> None:
    await send_reply_audio(update, audio_filepath)
    # ret = await send_reply_audio(update, audio_filepath)
    # return await download_audio_file_from_telegram_if_not_in_cache(
    #    context.bot, ret.audio
    # )
    return None
