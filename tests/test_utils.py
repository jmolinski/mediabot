from __future__ import annotations

import hashlib

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import utils

if TYPE_CHECKING:
    from tests.conftest import FakeSettings


class TestSplitIntoChunks:
    def test_splits_evenly(self) -> None:
        assert utils.split_into_chunks([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]

    def test_last_chunk_is_shorter(self) -> None:
        assert utils.split_into_chunks([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]

    def test_chunk_larger_than_list(self) -> None:
        assert utils.split_into_chunks([1, 2], 5) == [[1, 2]]

    def test_empty_list(self) -> None:
        assert utils.split_into_chunks([], 3) == []


class TestGetNameFromAuthorObj:
    def test_prefers_username(self) -> None:
        data = {"username": "alice", "first_name": "Alice B"}
        assert utils.get_name_from_author_obj(data) == "alice"

    def test_falls_back_to_first_name_when_username_missing(self) -> None:
        data = {"username": None, "first_name": "Bob"}
        assert utils.get_name_from_author_obj(data) == "Bob"

    def test_empty_username_falls_back(self) -> None:
        data = {"username": "", "first_name": "Carol"}
        assert utils.get_name_from_author_obj(data) == "Carol"


class TestTimestampToSeconds:
    def test_seconds_only(self) -> None:
        assert utils.timestamp_to_seconds("42") == 42

    def test_minutes_and_seconds(self) -> None:
        assert utils.timestamp_to_seconds("1:30") == 90

    def test_hours_minutes_seconds(self) -> None:
        assert utils.timestamp_to_seconds("1:02:03") == 3723

    def test_leading_zeros_are_handled(self) -> None:
        assert utils.timestamp_to_seconds("01:05") == 65

    def test_all_zero_component(self) -> None:
        # "00" -> lstrip("0") == "" -> falls back to 0
        assert utils.timestamp_to_seconds("00:00") == 0

    def test_too_many_parts_raises(self) -> None:
        with pytest.raises(AssertionError):
            utils.timestamp_to_seconds("1:2:3:4")


class TestUrlSignature:
    def test_matches_md5_of_stripped_url(self) -> None:
        url = "https://example.com/song"
        expected = hashlib.md5(url.encode()).hexdigest()
        assert utils.url_signature(url) == expected

    def test_strips_surrounding_whitespace(self) -> None:
        assert utils.url_signature("  https://a.com  ") == utils.url_signature(
            "https://a.com"
        )


class TestCachePathForUrl:
    def test_uses_settings_cache_dir_and_signature(
        self, fake_settings: FakeSettings
    ) -> None:
        url = "https://example.com/audio"
        path = utils.cache_path_for_url(url, "mp3")
        assert path.parent == fake_settings.cache_dir
        assert path.name == f"{utils.url_signature(url)}.mp3"

    def test_normalizes_extension_without_dot(
        self, fake_settings: FakeSettings
    ) -> None:
        path = utils.cache_path_for_url("https://a.com", "jpg")
        assert path.suffix == ".jpg"

    def test_accepts_extension_with_dot(self, fake_settings: FakeSettings) -> None:
        path = utils.cache_path_for_url("https://a.com", ".png")
        assert path.suffix == ".png"

    def test_no_extension(self, fake_settings: FakeSettings) -> None:
        path = utils.cache_path_for_url("https://a.com")
        assert path.suffix == ""

    def test_mp3_helper(self, fake_settings: FakeSettings) -> None:
        url = "https://a.com/x"
        assert utils.cache_path_for_mp3_url(url) == utils.cache_path_for_url(
            url, ".mp3"
        )


class TestGenerateRandomFilenameInCache:
    def test_filename_shape(self, fake_settings: FakeSettings) -> None:
        path = utils.generate_random_filename_in_cache("mp3")
        assert path.parent == fake_settings.cache_dir
        assert path.name.startswith("tmp_")
        assert path.suffix == ".mp3"
        assert not path.exists()

    def test_extension_normalized(self, fake_settings: FakeSettings) -> None:
        assert utils.generate_random_filename_in_cache("jpg").suffix == ".jpg"
        assert utils.generate_random_filename_in_cache(".png").suffix == ".png"

    def test_no_extension(self, fake_settings: FakeSettings) -> None:
        assert utils.generate_random_filename_in_cache().suffix == ""

    def test_returns_unique_names(self, fake_settings: FakeSettings) -> None:
        names = {utils.generate_random_filename_in_cache("mp3").name for _ in range(20)}
        assert len(names) > 1

    def test_skips_existing_file(
        self, fake_settings: FakeSettings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Force the first candidate name to collide with an existing file so the
        # ``while`` loop must iterate at least once.
        # random char count == length - len("tmp_") - 4, so length=10 -> 2 chars.
        collisions = iter(["A", "A", "B", "B"])
        monkeypatch.setattr(utils.random, "choice", lambda _seq: next(collisions))

        existing = fake_settings.cache_dir / "tmp_AA.mp3"
        existing.write_text("x")

        path = utils.generate_random_filename_in_cache("mp3", length=10)
        assert path.name == "tmp_BB.mp3"


class TestRemoveQueryParameterFromUrl:
    def test_removes_named_parameter(self) -> None:
        url = "https://youtube.com/watch?v=abc&list=xyz"
        result = utils.remove_query_parameter_from_url(url, "list")
        assert "list=" not in result
        assert "v=abc" in result

    def test_keeps_other_parameters(self) -> None:
        url = "https://a.com/p?a=1&b=2"
        result = utils.remove_query_parameter_from_url(url, "a")
        assert "b=2" in result
        assert "a=1" not in result

    def test_missing_parameter_is_noop(self) -> None:
        url = "https://a.com/p?a=1"
        result = utils.remove_query_parameter_from_url(url, "nope")
        assert "a=1" in result


class TestEscapeMarkdownV2:
    def test_escapes_special_characters(self) -> None:
        assert utils._escape_markdown_v2("a.b") == "a\\.b"
        assert utils._escape_markdown_v2("a>b") == "a\\>b"

    def test_leaves_plain_letters_untouched(self) -> None:
        assert utils._escape_markdown_v2("hello world") == "hello world"

    def test_escapes_multiple(self) -> None:
        assert utils._escape_markdown_v2("!#") == "\\!\\#"


class TestDownloadUrlToCache:
    def test_rejects_non_https(self, fake_settings: FakeSettings) -> None:
        with pytest.raises(AssertionError):
            utils.download_url_to_cache("http://insecure.com/a")

    def test_downloads_to_expected_path(
        self, fake_settings: FakeSettings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        url = "https://example.com/pic.jpg"

        def fake_urlretrieve(src: str, dest: str) -> None:
            Path(dest).write_text("data")

        monkeypatch.setattr(utils.urllib.request, "urlretrieve", fake_urlretrieve)

        path = utils.download_url_to_cache(url)
        assert path == utils.cache_path_for_url(url)
        assert path.read_text() == "data"
