from __future__ import annotations

import re

from pathlib import Path
from typing import Any

import pytest

import media_fetcher


class TestServicePatterns:
    @pytest.mark.parametrize(
        "url",
        [
            "https://artist.bandcamp.com/album/my-album",
            "https://my-band.bandcamp.com/album/some-record",
        ],
    )
    def test_bandcamp_playlist_matches(self, url: str) -> None:
        assert re.match(media_fetcher.BANDCAMP_PLAYLIST_PATTERN, url)

    def test_bandcamp_song_matches(self) -> None:
        assert re.match(
            media_fetcher.BANDCAMP_SONG_PATTERN,
            "https://artist.bandcamp.com/track/a-song",
        )

    def test_bandcamp_song_does_not_match_album(self) -> None:
        assert not re.match(
            media_fetcher.BANDCAMP_SONG_PATTERN,
            "https://artist.bandcamp.com/album/a-record",
        )

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/playlist?list=PL123",
            "https://music.youtube.com/playlist?list=abc-DEF",
            "http://youtube.com/playlist?list=xyz",
        ],
    )
    def test_youtube_playlist_matches(self, url: str) -> None:
        assert re.match(media_fetcher.YOUTUBE_PLAYLIST_PATTERN, url)

    @pytest.mark.parametrize(
        "url",
        [
            "https://youtu.be/abc123",
            "https://www.youtube.com/watch?v=abc123",
            "https://music.youtube.com/watch?v=abc123&list=xyz",
        ],
    )
    def test_youtube_song_matches_some_pattern(self, url: str) -> None:
        assert any(re.match(p, url) for p in media_fetcher.YOUTUBE_SONG_PATTERNS)

    def test_soundcloud_playlist_matches(self) -> None:
        assert re.match(
            media_fetcher.SOUNDCLOUD_PLAYLIST_PATTERNS,
            "https://soundcloud.com/user/sets/my-set",
        )

    def test_soundcloud_song_matches(self) -> None:
        assert re.match(
            media_fetcher.SOUNDCLOUD_SONG_PATTERNS,
            "https://soundcloud.com/user/a-track",
        )


class TestExtractVideoLinks:
    async def test_extracts_matching_song_links(self) -> None:
        text = (
            "check this https://youtu.be/aaaa and "
            "https://www.youtube.com/watch?v=bbbb plus some noise"
        )
        links = await media_fetcher.extract_video_links(
            text, media_fetcher.YOUTUBE_SONG_PATTERNS, []
        )
        assert links == [
            "https://youtu.be/aaaa",
            "https://www.youtube.com/watch?v=bbbb",
        ]

    async def test_ignores_non_matching_links(self) -> None:
        text = "https://example.com/not-a-song https://youtu.be/xyz"
        links = await media_fetcher.extract_video_links(
            text, media_fetcher.YOUTUBE_SONG_PATTERNS, []
        )
        assert links == ["https://youtu.be/xyz"]

    async def test_strips_list_query_parameter(self) -> None:
        text = "https://music.youtube.com/watch?v=abcd&list=PLxyz"
        links = await media_fetcher.extract_video_links(
            text, media_fetcher.YOUTUBE_SONG_PATTERNS, []
        )
        assert len(links) == 1
        assert "list=" not in links[0]
        assert "v=abcd" in links[0]

    async def test_expands_playlists(self, monkeypatch: pytest.MonkeyPatch) -> None:
        text = "https://www.youtube.com/playlist?list=PL123"

        monkeypatch.setattr(
            media_fetcher.youtube_utils,
            "playlist_url_to_video_urls",
            lambda url: ["https://youtu.be/one", "https://youtu.be/two"],
        )

        links = await media_fetcher.extract_video_links(
            text, [], [media_fetcher.YOUTUBE_PLAYLIST_PATTERN]
        )
        assert links == ["https://youtu.be/one", "https://youtu.be/two"]


class TestCollectLinkTargets:
    async def test_collects_across_services(self) -> None:
        text = (
            "https://youtu.be/aaaa "
            "https://artist.bandcamp.com/track/song "
            "https://soundcloud.com/user/track"
        )
        links = await media_fetcher.collect_link_targets(text)
        assert "https://youtu.be/aaaa" in links
        assert "https://artist.bandcamp.com/track/song" in links
        assert "https://soundcloud.com/user/track" in links

    async def test_no_links_returns_empty(self) -> None:
        assert await media_fetcher.collect_link_targets("just some text") == []


class TestDownloadSongFromUrlIfNotInCache:
    def test_downloads_when_not_cached(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cached = tmp_path / "sig.mp3"  # does not exist yet
        monkeypatch.setattr(
            media_fetcher.utils, "cache_path_for_mp3_url", lambda link: cached
        )

        def fake_ytdl(link: str, split_chapters: bool) -> list[Path]:
            cached.write_text("")  # simulate download creating the file
            return [cached]

        monkeypatch.setattr(
            media_fetcher.youtube_utils, "ytdl_download_song", fake_ytdl
        )

        result = media_fetcher._download_song_from_url_if_not_in_cache(
            "https://youtu.be/x", split_chapters=False
        )
        assert result == [cached]

    def test_uses_cache_when_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cached = tmp_path / "sig.mp3"
        cached.write_text("cached")
        monkeypatch.setattr(
            media_fetcher.utils, "cache_path_for_mp3_url", lambda link: cached
        )

        def fail_ytdl(link: str, split_chapters: bool) -> list[Path]:
            raise AssertionError("should not download when cached")

        monkeypatch.setattr(
            media_fetcher.youtube_utils, "ytdl_download_song", fail_ytdl
        )

        result = media_fetcher._download_song_from_url_if_not_in_cache(
            "https://youtu.be/x", split_chapters=False
        )
        assert result == [cached]

    def test_split_chapters_returns_all_songs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cached = tmp_path / "sig.mp3"
        chapters = [tmp_path / "c1.mp3", tmp_path / "c2.mp3"]
        monkeypatch.setattr(
            media_fetcher.utils, "cache_path_for_mp3_url", lambda link: cached
        )
        monkeypatch.setattr(
            media_fetcher.youtube_utils,
            "ytdl_download_song",
            lambda link, split_chapters: chapters,
        )

        result = media_fetcher._download_song_from_url_if_not_in_cache(
            "https://youtu.be/x", split_chapters=True
        )
        assert result == chapters


class TestDownloadAudioFromUrlIfNotInCache:
    async def test_copies_each_downloaded_file(
        self, fake_settings: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        src = fake_settings.cache_dir / "orig.mp3"
        src.write_text("audio")

        monkeypatch.setattr(
            media_fetcher,
            "_download_song_from_url_if_not_in_cache",
            lambda link, split_chapters: [src],
        )

        result = await media_fetcher.download_audio_from_url_if_not_in_cache(
            object(),  # type: ignore[arg-type]
            object(),  # type: ignore[arg-type]
            ["https://youtu.be/x"],
            split_chapters=False,
        )

        assert len(result) == 1
        assert result[0] != src
        assert result[0].read_text() == "audio"


class TestFetchParentMessageTarget:
    async def test_returns_empty_without_audio_parent(self) -> None:
        result = await media_fetcher.fetch_parent_message_target(
            object(), _NoParent()  # type: ignore[arg-type]
        )
        assert result == []

    async def test_copies_parent_audio(
        self, fake_settings: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original: Path = fake_settings.cache_dir / "uid.mp3"
        original.write_text("parent-audio")

        async def fake_download(bot: Any, audio: Any) -> Path:
            return original

        monkeypatch.setattr(
            media_fetcher,
            "download_audio_file_from_telegram_if_not_in_cache",
            fake_download,
        )

        context = type("Ctx", (), {"bot": object()})()
        msg = _AudioParent(file_unique_id="uid")

        result = await media_fetcher.fetch_parent_message_target(
            context, msg  # type: ignore[arg-type]
        )

        assert len(result) == 1
        assert result[0].read_text() == "parent-audio"
        assert result[0] != original


class _NoParent:
    has_parent = False


class _AudioParent:
    def __init__(self, file_unique_id: str) -> None:
        self.has_parent = True
        audio = type("A", (), {"file_unique_id": file_unique_id})()
        self.parent_msg = type("P", (), {"has_audio": True, "audio": audio})()


class TestFetchTargets:
    async def test_prefers_parent_target(self, monkeypatch: pytest.MonkeyPatch) -> None:
        parent = [Path("/tmp/parent.mp3")]

        async def fake_parent(context: Any, msg: Any) -> list[Path]:
            return parent

        monkeypatch.setattr(media_fetcher, "fetch_parent_message_target", fake_parent)

        msg = type("M", (), {"text": "ignored"})()
        result = await media_fetcher.fetch_targets(
            object(), object(), msg, split_chapters=False  # type: ignore[arg-type]
        )
        assert result == parent

    async def test_falls_back_to_links(self, monkeypatch: pytest.MonkeyPatch) -> None:
        downloaded = [Path("/tmp/a.mp3")]

        async def fake_parent(context: Any, msg: Any) -> list[Path]:
            return []

        async def fake_collect(text: str) -> list[str]:
            return ["https://youtu.be/x"]

        async def fake_download(
            update: Any, context: Any, links: list[str], split_chapters: bool
        ) -> list[Path]:
            assert links == ["https://youtu.be/x"]
            return downloaded

        monkeypatch.setattr(media_fetcher, "fetch_parent_message_target", fake_parent)
        monkeypatch.setattr(media_fetcher, "collect_link_targets", fake_collect)
        monkeypatch.setattr(
            media_fetcher, "download_audio_from_url_if_not_in_cache", fake_download
        )

        msg = type("M", (), {"text": "https://youtu.be/x"})()
        result = await media_fetcher.fetch_targets(
            object(), object(), msg, split_chapters=False  # type: ignore[arg-type]
        )
        assert result == downloaded
