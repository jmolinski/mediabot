from __future__ import annotations

import json

from pathlib import Path

import pytest

import youtube_utils


class TestExtractYoutubeId:
    def test_youtu_be_short_link(self) -> None:
        assert youtube_utils.extract_youtube_id("https://youtu.be/abc123") == "abc123"

    def test_watch_url(self) -> None:
        link = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert youtube_utils.extract_youtube_id(link) == "dQw4w9WgXcQ"

    def test_watch_url_with_extra_params(self) -> None:
        link = "https://www.youtube.com/watch?v=abcdef&list=xyz&index=2"
        assert youtube_utils.extract_youtube_id(link) == "abcdef"

    def test_strips_whitespace(self) -> None:
        assert youtube_utils.extract_youtube_id("  https://youtu.be/xyz  ") == "xyz"

    def test_multiple_v_params_raises(self) -> None:
        link = "https://www.youtube.com/watch?v=one&v=two"
        with pytest.raises(AssertionError):
            youtube_utils.extract_youtube_id(link)


class TestFindInfoJsonFilePath:
    def test_finds_matching_info_json(self, tmp_path: Path) -> None:
        mp3 = tmp_path / "song.mp3"
        mp3.write_text("")
        info = tmp_path / "song.info.json"
        info.write_text("{}")
        (tmp_path / "song.jpg").write_text("")

        assert youtube_utils.find_info_json_file_path(mp3) == info

    def test_raises_when_missing(self, tmp_path: Path) -> None:
        mp3 = tmp_path / "song.mp3"
        mp3.write_text("")
        with pytest.raises(IndexError):
            youtube_utils.find_info_json_file_path(mp3)


class TestGetChapterNamesFromInfoJsonFile:
    def test_returns_titles_sorted_by_start_time(self, tmp_path: Path) -> None:
        info = tmp_path / "x.info.json"
        info.write_text(
            json.dumps(
                {
                    "chapters": [
                        {"title": "second", "start_time": 10},
                        {"title": "first", "start_time": 0},
                        {"title": "third", "start_time": 20},
                    ]
                }
            )
        )
        assert youtube_utils.get_chapter_names_from_info_json_file(info) == [
            "first",
            "second",
            "third",
        ]

    def test_empty_chapters(self, tmp_path: Path) -> None:
        info = tmp_path / "x.info.json"
        info.write_text(json.dumps({"chapters": []}))
        assert youtube_utils.get_chapter_names_from_info_json_file(info) == []


class TestSetMetadataFromInfoFile:
    def test_uses_info_title_and_album(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        info = tmp_path / "x.info.json"
        info.write_text(json.dumps({"title": "My Song", "album": "My Album"}))
        mp3 = tmp_path / "x.mp3"

        calls: list[tuple[Path, str, str]] = []
        monkeypatch.setattr(
            youtube_utils.mp3_utils,
            "change_metadata",
            lambda f, field, data: calls.append((f, field, data)),
        )

        youtube_utils.set_metadata_from_info_file(mp3, info)

        assert (mp3, "title", "My Song") in calls
        assert (mp3, "album", "My Album") in calls

    def test_explicit_title_overrides_info(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        info = tmp_path / "x.info.json"
        info.write_text(json.dumps({"title": "Ignored"}))
        mp3 = tmp_path / "x.mp3"

        calls: list[tuple[str, str]] = []
        monkeypatch.setattr(
            youtube_utils.mp3_utils,
            "change_metadata",
            lambda f, field, data: calls.append((field, data)),
        )

        youtube_utils.set_metadata_from_info_file(mp3, info, title="Override")

        assert ("title", "Override") in calls
        # No album key in info -> album metadata not written.
        assert all(field != "album" for field, _ in calls)


class TestGetThumbnailPathForMp3:
    def test_returns_none_when_no_thumbnail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import logging

        monkeypatch.setattr(
            youtube_utils, "get_default_logger", lambda: logging.getLogger("test")
        )

        mp3 = tmp_path / "song.mp3"
        mp3.write_text("")
        (tmp_path / "song.info.json").write_text("{}")

        assert youtube_utils.get_thumbnail_path_for_mp3(mp3) is None

    def test_uses_existing_jpg_and_crops_it(self, tmp_path: Path) -> None:
        from PIL import Image

        mp3 = tmp_path / "song.mp3"
        mp3.write_text("")
        jpg = tmp_path / "song.jpg"
        Image.new("RGB", (200, 100)).save(jpg, format="JPEG")
        (tmp_path / "song.info.json").write_text("{}")

        result = youtube_utils.get_thumbnail_path_for_mp3(mp3)

        assert result == jpg
        with Image.open(jpg) as im:
            assert im.size[0] == im.size[1]  # cropped square

    def test_converts_non_jpg_and_removes_originals(self, tmp_path: Path) -> None:
        from PIL import Image

        mp3 = tmp_path / "song.mp3"
        mp3.write_text("")
        png = tmp_path / "song.png"
        Image.new("RGB", (150, 90)).save(png, format="PNG")

        result = youtube_utils.get_thumbnail_path_for_mp3(mp3)

        assert result is not None
        assert result.suffix == ".jpg"
        assert result.exists()
        assert not png.exists()  # original webp/png removed
