from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import mp3_utils


@pytest.fixture
def cut_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Stub out ffmpeg, temp-file creation and cover copying for cut_audio."""
    state: dict[str, Any] = {"commands": [], "duration": 100.0}

    temp = tmp_path / "tmp_out.mp3"

    def fake_gen(ext: str = "") -> Path:
        temp.write_text("temp")
        return temp

    def fake_run(cmd: list[str], *a: Any, **k: Any) -> None:
        state["commands"].append(cmd)

    monkeypatch.setattr(mp3_utils, "generate_random_filename_in_cache", fake_gen)
    monkeypatch.setattr(mp3_utils, "run_command", fake_run)
    monkeypatch.setattr(mp3_utils, "copy_cover_image", lambda src, dest: None)
    monkeypatch.setattr(
        mp3_utils, "read_metadata", lambda fp: {"duration": state["duration"]}
    )
    state["temp"] = temp
    return state


def _ss_t(cmd: list[str]) -> tuple[str, str]:
    return cmd[cmd.index("-ss") + 1], cmd[cmd.index("-t") + 1]


class TestCutAudio:
    def test_integer_seconds(self, tmp_path: Path, cut_env: dict[str, Any]) -> None:
        src = tmp_path / "song.mp3"
        src.write_text("orig")
        result = mp3_utils.cut_audio(src, 10, 30)

        ss, t = _ss_t(cut_env["commands"][0])
        assert (ss, t) == ("10", "20")
        assert result == src  # overwrite=True renames temp onto src

    def test_timestamp_format(self, tmp_path: Path, cut_env: dict[str, Any]) -> None:
        src = tmp_path / "song.mp3"
        src.write_text("orig")
        mp3_utils.cut_audio(src, "0:10", "1:00")
        ss, t = _ss_t(cut_env["commands"][0])
        assert (ss, t) == ("10", "50")

    def test_negative_start_offsets_from_duration(
        self, tmp_path: Path, cut_env: dict[str, Any]
    ) -> None:
        src = tmp_path / "song.mp3"
        src.write_text("orig")
        cut_env["duration"] = 100.0
        mp3_utils.cut_audio(src, -20, 0)
        ss, t = _ss_t(cut_env["commands"][0])
        # start = -20 + 100 = 80, end = 0 + 100 = 100 -> duration 20
        assert (ss, t) == ("80", "20")

    def test_no_overwrite_returns_temp(
        self, tmp_path: Path, cut_env: dict[str, Any]
    ) -> None:
        src = tmp_path / "song.mp3"
        src.write_text("orig")
        result = mp3_utils.cut_audio(src, 0, 5, overwrite=False)
        assert result == cut_env["temp"]
        assert src.read_text() == "orig"  # source untouched


class _FakeImage:
    def __init__(self, data: bytes) -> None:
        self.image_data = data


class _FakeImages:
    def __init__(self, front: bytes | None, others: list[bytes]) -> None:
        self._front = _FakeImage(front) if front is not None else None
        self._others = [_FakeImage(o) for o in others]

    def get(self, key: str) -> _FakeImage:
        if self._front is None:
            raise AttributeError
        return self._front

    def __iter__(self) -> Any:
        return iter(self._others if self._front is None else [self._front])


class _FakeTag:
    def __init__(
        self,
        *,
        title: str | None = None,
        album: str | None = None,
        artist: str | None = None,
        images: _FakeImages | None = None,
    ) -> None:
        self.title = title
        self.album = album
        self.artist = artist
        self.images = images


class _FakeAudioFile:
    def __init__(self, tag: _FakeTag, time_secs: float = 123.0) -> None:
        self.tag = tag
        self.info = type("Info", (), {"time_secs": time_secs})()


class TestReadMetadata:
    def test_reads_all_present_fields(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tag = _FakeTag(title="T", album="Al", artist="Ar")
        monkeypatch.setattr(
            mp3_utils.eyed3, "load", lambda p: _FakeAudioFile(tag, time_secs=200.0)
        )
        result = mp3_utils.read_metadata(tmp_path / "x.mp3")
        assert result == {
            "duration": 200.0,
            "title": "T",
            "album": "Al",
            "performer": "Ar",
        }

    def test_omits_missing_optional_fields(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tag = _FakeTag(title=None, album=None, artist=None)
        monkeypatch.setattr(
            mp3_utils.eyed3, "load", lambda p: _FakeAudioFile(tag, time_secs=5.0)
        )
        assert mp3_utils.read_metadata(tmp_path / "x.mp3") == {"duration": 5.0}


class TestReadCoverImage:
    def test_returns_front_cover(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tag = _FakeTag(images=_FakeImages(front=b"front", others=[]))
        monkeypatch.setattr(mp3_utils.eyed3, "load", lambda p: _FakeAudioFile(tag))
        assert mp3_utils.read_cover_image(tmp_path / "x.mp3") == b"front"

    def test_falls_back_to_first_image(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tag = _FakeTag(images=_FakeImages(front=None, others=[b"other"]))
        monkeypatch.setattr(mp3_utils.eyed3, "load", lambda p: _FakeAudioFile(tag))
        assert mp3_utils.read_cover_image(tmp_path / "x.mp3") == b"other"

    def test_returns_none_when_no_images(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tag = _FakeTag(images=_FakeImages(front=None, others=[]))
        monkeypatch.setattr(mp3_utils.eyed3, "load", lambda p: _FakeAudioFile(tag))
        assert mp3_utils.read_cover_image(tmp_path / "x.mp3") is None
