from __future__ import annotations

from typing import cast

from telegram import Audio
from telegram import Message as TelegramMessage

from utils import get_name_from_author_obj


class MsgWrapper:
    msg: TelegramMessage

    def __init__(self, msg: TelegramMessage | None) -> None:
        if msg is None:
            raise ValueError("Message is None")

        self.msg = msg

    @property
    def is_reply(self) -> bool:
        return self.msg["reply_to_message"] is not None

    @property
    def msg_id(self) -> int:
        return cast(int, self.msg.message_id)

    @property
    def chat_id(self) -> int:
        return cast(int, self.msg.chat.id)

    @property
    def has_parent(self) -> bool:
        return self.is_reply and self.msg.reply_to_message is not None

    @property
    def parent(self) -> int:
        assert self.has_parent and self.msg.reply_to_message is not None
        return cast(int, self.msg.reply_to_message.message_id)

    @property
    def parent_msg(self) -> MsgWrapper:
        assert self.has_parent
        return MsgWrapper(self.msg.reply_to_message)

    @property
    def text(self) -> str:
        assert self.msg.text is not None
        return cast(str, self.msg.text.strip())

    @property
    def author(self) -> str:
        return get_name_from_author_obj(cast(dict, self.msg["from_user"]))

    @property
    def author_id(self) -> int:
        assert self.msg.from_user is not None
        return cast(int, self.msg.from_user.id)

    @property
    def has_audio(self) -> bool:
        return self.msg.audio is not None

    @property
    def audio(self) -> Audio:
        assert self.has_audio
        return cast(Audio, self.msg.audio)

    def extract_youtube_links(self) -> list[str]:
        return [
            p
            for p in self.text.split()
            if "https" in p and ("youtube.com" in p or "youtu.be" in p)
        ]
