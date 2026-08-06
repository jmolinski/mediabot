from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

import telegram_helpers


class FakeMessage:
    """Minimal Telegram ``Message`` stand-in supporting attr and item access."""

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


class FakeFile:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def download_as_bytearray(self, buffer: bytearray) -> None:
        buffer.extend(self._payload)


class TestDownloadFileFromTelegram:
    async def test_returns_bytes(self) -> None:
        bot = AsyncMock()
        bot.get_file.return_value = FakeFile(b"hello")

        result = await telegram_helpers.download_file_from_telegram(bot, "fid")

        assert result == b"hello"
        bot.get_file.assert_awaited_once_with("fid")


class TestDownloadFileIfNotInCache:
    async def test_asserts_extension_has_no_dot(self, fake_settings: Any) -> None:
        with pytest.raises(AssertionError):
            await telegram_helpers.download_file_from_telegram_if_not_in_cache(
                AsyncMock(), "fid", "uid", ".mp3"
            )

    async def test_writes_file_when_missing(
        self, fake_settings: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_download(bot: Any, file_id: str) -> bytes:
            return b"data"

        monkeypatch.setattr(
            telegram_helpers, "download_file_from_telegram", fake_download
        )

        path = await telegram_helpers.download_file_from_telegram_if_not_in_cache(
            AsyncMock(), "fid", "uid", "mp3"
        )
        assert path == fake_settings.cache_dir / "uid.mp3"
        assert path.read_bytes() == b"data"

    async def test_uses_cache_when_present(
        self, fake_settings: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cached = fake_settings.cache_dir / "uid.mp3"
        cached.write_bytes(b"cached")

        called = False

        async def fake_download(bot: Any, file_id: str) -> bytes:
            nonlocal called
            called = True
            return b"new"

        monkeypatch.setattr(
            telegram_helpers, "download_file_from_telegram", fake_download
        )

        path = await telegram_helpers.download_file_from_telegram_if_not_in_cache(
            AsyncMock(), "fid", "uid", "mp3"
        )
        assert path.read_bytes() == b"cached"
        assert called is False


class TestSendMessage:
    async def test_defaults_and_wraps_result(self) -> None:
        bot = AsyncMock()
        bot.send_message.return_value = FakeMessage(message_id=7, chat=None)

        result = await telegram_helpers.send_message(bot, chat_id=5)

        assert result.msg_id == 7
        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["chat_id"] == 5
        assert kwargs["text"] == telegram_helpers.EMPTY_MSG
        assert kwargs["parse_mode"] == "HTML"
        assert "reply_to_message_id" not in kwargs

    async def test_includes_parent_and_markup_and_extra_kwargs(self) -> None:
        bot = AsyncMock()
        bot.send_message.return_value = FakeMessage(message_id=1)
        markup = object()

        await telegram_helpers.send_message(
            bot,
            chat_id=3,
            parent_id=99,
            markup=markup,  # type: ignore[arg-type]
            text="hi",
            parse_mode="MarkdownV2",
        )

        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["reply_to_message_id"] == 99
        assert kwargs["reply_markup"] is markup
        assert kwargs["text"] == "hi"
        assert kwargs["parse_mode"] == "MarkdownV2"


class TestSendReply:
    async def test_replies_to_incoming_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}

        async def fake_send_message(
            bot: Any, chat_id: int, parent_id: Any = None, *a: Any, **k: Any
        ) -> Any:
            captured["chat_id"] = chat_id
            captured["parent_id"] = parent_id
            captured["kwargs"] = k
            return "ok"

        monkeypatch.setattr(telegram_helpers, "send_message", fake_send_message)

        update = type("U", (), {})()
        update.message = FakeMessage(message_id=42, chat=type("C", (), {"id": 8})())
        context = type("Ctx", (), {"bot": AsyncMock()})()

        await telegram_helpers.send_reply(update, context, "hello")

        assert captured["chat_id"] == 8
        assert captured["parent_id"] == 42
        assert captured["kwargs"]["text"] == "hello"


class TestSendReplyAudio:
    async def test_rejects_oversized_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        audio = tmp_path / "big.mp3"
        audio.write_text("x")
        monkeypatch.setattr(
            telegram_helpers.os.path,
            "getsize",
            lambda p: telegram_helpers.TELEGRAM_BOT_MAX_FILE_SIZE + 1,
        )

        update = type("U", (), {})()
        update.message = FakeMessage()

        with pytest.raises(ValueError, match="exceeds Telegram's limit"):
            await telegram_helpers.send_reply_audio(update, audio)

    async def test_happy_path_passes_metadata(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        audio = tmp_path / "song.mp3"
        audio.write_text("x")

        monkeypatch.setattr(
            telegram_helpers.mp3_utils,
            "read_metadata",
            lambda p: {"title": "T", "performer": "P", "duration": 12},
        )
        monkeypatch.setattr(
            telegram_helpers.mp3_utils, "read_cover_image", lambda p: b"cover"
        )

        reply_audio = AsyncMock(return_value=FakeMessage(message_id=1))
        update = type("U", (), {})()
        update.message = type("M", (), {"reply_audio": reply_audio})()

        await telegram_helpers.send_reply_audio(update, audio)

        assert reply_audio.await_args is not None
        kwargs = reply_audio.await_args.kwargs
        assert kwargs["title"] == "T"
        assert kwargs["performer"] == "P"
        assert kwargs["duration"] == 12
        assert kwargs["filename"] == "T"
        assert kwargs["thumbnail"] == b"cover"


class TestLogExceptionAndNotifyChat:
    async def test_sends_formatted_traceback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sent: dict[str, Any] = {}

        async def fake_send_reply(
            update: Any, context: Any, text: str, **kwargs: Any
        ) -> None:
            sent["text"] = text
            sent["kwargs"] = kwargs

        monkeypatch.setattr(telegram_helpers, "send_reply", fake_send_reply)

        await telegram_helpers.log_exception_and_notify_chat(
            object(), object(), ValueError("boom")  # type: ignore[arg-type]
        )

        assert "boom" in sent["text"]
        assert sent["kwargs"]["parse_mode"] == "MarkdownV2"

    async def test_swallows_send_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def failing_send_reply(*a: Any, **k: Any) -> None:
            raise RuntimeError("network down")

        import logging

        monkeypatch.setattr(telegram_helpers, "send_reply", failing_send_reply)
        monkeypatch.setattr(
            telegram_helpers, "get_default_logger", lambda: logging.getLogger("t")
        )

        # Should not raise despite the inner failure.
        await telegram_helpers.log_exception_and_notify_chat(
            object(), object(), ValueError("boom")  # type: ignore[arg-type]
        )


class TestPostAudioToTelegram:
    async def test_delegates_and_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[Path] = []

        async def fake_send_reply_audio(update: Any, audio: Path) -> Any:
            calls.append(audio)
            return None

        monkeypatch.setattr(telegram_helpers, "send_reply_audio", fake_send_reply_audio)

        await telegram_helpers.post_audio_to_telegram(
            object(), object(), Path("/tmp/x.mp3")  # type: ignore[arg-type]
        )
        assert calls == [Path("/tmp/x.mp3")]
