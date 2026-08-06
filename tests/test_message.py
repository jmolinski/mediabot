from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest

from telegram import Message as TelegramMessage

from message import MsgWrapper

if TYPE_CHECKING:
    from tests.conftest import FakeSettings


class FakeMessage:
    """Minimal Telegram ``Message`` stand-in.

    ``MsgWrapper`` reads some fields via attribute access (``msg.chat``) and
    others via item access (``msg["from_user"]``), so this fake supports both.
    """

    def __init__(self, **fields: Any) -> None:
        defaults: dict[str, Any] = {
            "message_id": 1,
            "chat": None,
            "reply_to_message": None,
            "text": None,
            "from_user": None,
            "audio": None,
            "photo": None,
        }
        defaults.update(fields)
        self.__dict__.update(defaults)

    def __getitem__(self, key: str) -> Any:
        return self.__dict__[key]


class _Obj:
    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


def wrap(msg: FakeMessage) -> MsgWrapper:
    return MsgWrapper(cast(TelegramMessage, msg))


class TestConstruction:
    def test_none_message_raises(self) -> None:
        with pytest.raises(ValueError):
            MsgWrapper(None)


class TestBasicProperties:
    def test_msg_id_and_chat_id(self) -> None:
        wrapper = wrap(FakeMessage(message_id=42, chat=_Obj(id=99)))
        assert wrapper.msg_id == 42
        assert wrapper.chat_id == 99

    def test_text_stripped(self) -> None:
        assert wrap(FakeMessage(text="  hi there  ")).text == "hi there"

    def test_text_none_returns_empty(self) -> None:
        assert wrap(FakeMessage(text=None)).text == ""

    def test_author(self) -> None:
        msg = FakeMessage(from_user={"username": "alice", "first_name": "A"})
        assert wrap(msg).author == "alice"

    def test_author_id(self) -> None:
        assert wrap(FakeMessage(from_user=_Obj(id=7))).author_id == 7


class TestReplyAndParent:
    def test_is_reply_false(self) -> None:
        assert wrap(FakeMessage()).is_reply is False

    def test_has_parent_and_parent(self) -> None:
        parent = FakeMessage(message_id=5)
        wrapper = wrap(FakeMessage(reply_to_message=parent))
        assert wrapper.is_reply is True
        assert wrapper.has_parent is True
        assert wrapper.parent == 5

    def test_parent_msg_returns_wrapper(self) -> None:
        parent = FakeMessage(message_id=5, text="parent")
        wrapper = wrap(FakeMessage(reply_to_message=parent))
        assert isinstance(wrapper.parent_msg, MsgWrapper)
        assert wrapper.parent_msg.text == "parent"

    def test_parent_asserts_without_parent(self) -> None:
        with pytest.raises(AssertionError):
            _ = wrap(FakeMessage()).parent


class TestMedia:
    def test_has_audio(self) -> None:
        assert wrap(FakeMessage(audio=_Obj(file_id="x"))).has_audio is True
        assert wrap(FakeMessage(audio=None)).has_audio is False

    def test_audio_returns_object(self) -> None:
        audio = _Obj(file_id="x")
        assert wrap(FakeMessage(audio=audio)).audio is audio

    def test_audio_asserts_when_absent(self) -> None:
        with pytest.raises(AssertionError):
            _ = wrap(FakeMessage(audio=None)).audio

    def test_has_picture(self) -> None:
        assert wrap(FakeMessage(photo=[_Obj()])).has_picture is True
        assert wrap(FakeMessage(photo=None)).has_picture is False


class TestIsAuthorized:
    def test_authorize_all(self, fake_settings: FakeSettings) -> None:
        fake_settings.authorize_all = True
        msg = FakeMessage(from_user=_Obj(id=1), chat=_Obj(id=2))
        assert wrap(msg).is_authorized() is True

    def test_authorized_user(self, fake_settings: FakeSettings) -> None:
        fake_settings.authorize_all = False
        fake_settings.authorized_users = [10]
        fake_settings.authorized_chats = []
        msg = FakeMessage(from_user=_Obj(id=10), chat=_Obj(id=999))
        assert wrap(msg).is_authorized() is True

    def test_authorized_chat(self, fake_settings: FakeSettings) -> None:
        fake_settings.authorize_all = False
        fake_settings.authorized_users = []
        fake_settings.authorized_chats = [-5]
        msg = FakeMessage(from_user=_Obj(id=1), chat=_Obj(id=-5))
        assert wrap(msg).is_authorized() is True

    def test_unauthorized(self, fake_settings: FakeSettings) -> None:
        fake_settings.authorize_all = False
        fake_settings.authorized_users = [10]
        fake_settings.authorized_chats = [-5]
        msg = FakeMessage(from_user=_Obj(id=1), chat=_Obj(id=2))
        assert wrap(msg).is_authorized() is False
