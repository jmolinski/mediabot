from __future__ import annotations

from pathlib import Path

import pytest

import handlers


class TestFindTransformers:
    def test_collects_known_transformers(self) -> None:
        text = "title My Song\nartist Someone\ncut 0 30"
        result = handlers.find_transformers(text)
        assert result["title"] == [["My", "Song"]]
        assert result["artist"] == [["Someone"]]
        assert result["cut"] == [["0", "30"]]

    def test_ignores_unknown_lines(self) -> None:
        text = "notatransformer foo\ntitle X"
        result = handlers.find_transformers(text)
        assert "notatransformer" not in result
        assert result["title"] == [["X"]]

    def test_skips_blank_lines(self) -> None:
        text = "\n\ntitle X\n   \n"
        assert handlers.find_transformers(text)["title"] == [["X"]]

    def test_repeated_transformer_accumulates(self) -> None:
        text = "replacetitle a;b\nreplacetitle c;d"
        assert handlers.find_transformers(text)["replacetitle"] == [
            ["a;b"],
            ["c;d"],
        ]

    def test_empty_text(self) -> None:
        assert handlers.find_transformers("") == {}


class TestApplyTransformerMetadata:
    def test_calls_change_metadata(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fp = tmp_path / "song.mp3"
        calls: list[tuple[str, str]] = []
        monkeypatch.setattr(
            handlers.mp3_utils,
            "change_metadata",
            lambda f, field, data: calls.append((field, data)),
        )

        result = handlers.apply_transformer(fp, "title", [["Hello", "World"]])

        assert result == [fp]
        assert calls == [("title", "Hello World")]

    def test_metadata_used_more_than_once_raises(self, tmp_path: Path) -> None:
        with pytest.raises(AssertionError):
            handlers.apply_transformer(tmp_path / "s.mp3", "title", [["a"], ["b"]])


class TestApplyTransformerReplaceTitle:
    def test_replaces_substring(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fp = tmp_path / "s.mp3"
        monkeypatch.setattr(
            handlers.mp3_utils,
            "read_metadata",
            lambda f: {"title": "hello world"},
        )
        written: list[str] = []
        monkeypatch.setattr(
            handlers.mp3_utils,
            "change_metadata",
            lambda f, field, data: written.append(data),
        )

        handlers.apply_transformer(fp, "replacetitle", [["world;there"]])
        assert written == ["hello there"]

    def test_trailing_semicolon_removes_part(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fp = tmp_path / "s.mp3"
        monkeypatch.setattr(
            handlers.mp3_utils,
            "read_metadata",
            lambda f: {"title": "hello world"},
        )
        written: list[str] = []
        monkeypatch.setattr(
            handlers.mp3_utils,
            "change_metadata",
            lambda f, field, data: written.append(data),
        )

        handlers.apply_transformer(fp, "replacetitle", [["hello ;"]])
        assert written == ["world"]


class TestApplyTransformerCut:
    def test_delegates_to_cut_audio(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fp = tmp_path / "s.mp3"
        out = tmp_path / "cut.mp3"
        calls: list[tuple[Path, str, str]] = []

        def fake_cut(f: Path, start: str, end: str) -> Path:
            calls.append((f, start, end))
            return out

        monkeypatch.setattr(handlers.mp3_utils, "cut_audio", fake_cut)

        result = handlers.apply_transformer(fp, "cut", [["10", "20"]])
        assert result == [out]
        assert calls == [(fp, "10", "20")]


class TestApplyTransformerCutHead:
    def test_default_five_seconds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fp = tmp_path / "s.mp3"
        fp.write_text("")
        produced = []

        def fake_cut(f: Path, start: int, end: int, overwrite: bool) -> Path:
            p = tmp_path / f"part{start}.mp3"
            produced.append(start)
            return p

        monkeypatch.setattr(handlers.mp3_utils, "cut_audio", fake_cut)

        result = handlers.apply_transformer(fp, "cuthead", [[]])
        assert produced == [1, 2, 3, 4, 5]
        assert len(result) == 5
        assert not fp.exists()  # original removed

    def test_explicit_seconds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fp = tmp_path / "s.mp3"
        fp.write_text("")
        monkeypatch.setattr(
            handlers.mp3_utils,
            "cut_audio",
            lambda f, start, end, overwrite: tmp_path / f"p{start}.mp3",
        )
        result = handlers.apply_transformer(fp, "cuthead", [["2"]])
        assert len(result) == 2

    def test_too_many_args_raises(self, tmp_path: Path) -> None:
        with pytest.raises(AssertionError):
            handlers.apply_transformer(tmp_path / "s.mp3", "cuthead", [["1", "2"]])


class TestApplyTransformerCover:
    def test_sets_cover(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fp = tmp_path / "s.mp3"
        thumb = tmp_path / "thumb.jpg"
        monkeypatch.setattr(handlers, "url_to_thumbnail_filename", lambda url: thumb)
        set_calls: list[tuple[Path, Path]] = []
        monkeypatch.setattr(
            handlers.mp3_utils,
            "set_cover",
            lambda f, cover: set_calls.append((f, cover)),
        )

        result = handlers.apply_transformer(fp, "cover", [["http://img"]])
        assert result == [fp]
        assert set_calls == [(fp, thumb)]


class TestApplyTransformerSplitChapters:
    def test_is_noop_returning_filepath(self, tmp_path: Path) -> None:
        fp = tmp_path / "s.mp3"
        assert handlers.apply_transformer(fp, "splitchapters", [[]]) == [fp]


class TestApplyTransformerUnknown:
    def test_raises(self, tmp_path: Path) -> None:
        with pytest.raises(Exception, match="Unknown transformer"):
            handlers.apply_transformer(tmp_path / "s.mp3", "bogus", [[]])


class TestApplyTransformers:
    def test_applies_in_sequence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fp = tmp_path / "s.mp3"
        recorded: list[str] = []
        monkeypatch.setattr(
            handlers.mp3_utils,
            "change_metadata",
            lambda f, field, data: recorded.append(f"{field}={data}"),
        )

        result = handlers.apply_transformers(fp, {"title": [["A"]], "artist": [["B"]]})
        assert result == [fp]
        assert recorded == ["title=A", "artist=B"]


class TestPrepareTransformers:
    def test_downloads_cover_thumbnails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        thumb = tmp_path / "thumb.jpg"
        thumb.write_text("")
        seen: list[str] = []

        def fake_url_to_thumb(url: str) -> Path:
            seen.append(url)
            return thumb

        monkeypatch.setattr(handlers, "url_to_thumbnail_filename", fake_url_to_thumb)

        handlers.prepare_transformers({"cover": [["http://img"]]})
        assert seen == ["http://img"]

    def test_asserts_when_thumbnail_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        missing = tmp_path / "nope.jpg"
        monkeypatch.setattr(handlers, "url_to_thumbnail_filename", lambda url: missing)
        with pytest.raises(AssertionError):
            handlers.prepare_transformers({"cover": [["http://img"]]})

    def test_no_cover_is_noop(self) -> None:
        handlers.prepare_transformers({"title": [["x"]]})
