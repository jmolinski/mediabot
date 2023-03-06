from __future__ import annotations

from typing import cast

from telegram import Message as TelegramMessage

from utils import get_name_from_author_obj


class MsgWrapper:
    msg: TelegramMessage

    def __init__(self, msg: TelegramMessage) -> None:
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
    def parent(self) -> int | None:
        if self.is_reply:
            assert self.msg.reply_to_message is not None
            return cast(int, self.msg.reply_to_message.message_id)
        return None

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
