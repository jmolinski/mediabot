from __future__ import annotations

from typing import Any

from telegram import Bot, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext

import mp3_utils

from message import MsgWrapper

EMPTY_MSG = "\xad\xad"


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
    audio: str,
    thumbnail: str | bytes | None = None,
    **kwargs: Any,
) -> MsgWrapper:
    assert update.message is not None

    metadata = mp3_utils.read_metadata(audio)

    if "title" in metadata:
        metadata["filename"] = metadata["title"]

    if thumbnail is None:
        thumbnail = mp3_utils.read_cover_image(audio)
    if thumbnail:
        metadata["thumb"] = thumbnail

    metadata = {
        k: v
        for k, v in metadata.items()
        if k in ("title", "performer", "thumb", "filename")
    }

    return MsgWrapper(
        await update.message.reply_audio(
            audio=audio,
            **metadata,
            write_timeout=60,
            read_timeout=60,
            pool_timeout=60,
            **kwargs,
        )
    )
