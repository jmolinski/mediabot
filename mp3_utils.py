from __future__ import annotations

import subprocess

from typing import Any, cast

import eyed3


def change_metadata(filename: str, field_name: str, data: str) -> None:
    ret = subprocess.call(
        [
            "ffmpeg",
            "-i",
            filename,
            "-metadata",
            rf"{field_name}={data}",
            "-codec",
            "copy",
            "temp.mp3",
        ],
        shell=False,
    )
    assert ret == 0

    ret = subprocess.call(
        ["mv", "temp.mp3", filename],
        shell=False,
    )
    assert ret == 0


def set_cover(filepath: str, cover_filepath: str) -> None:
    # source: https://stackoverflow.com/a/18718265

    ret = subprocess.call(
        [
            "ffmpeg",
            "-i",
            filepath,
            "-i",
            cover_filepath,
            "-map",
            "0:0",
            "-map",
            "1:0",
            "-c",
            "copy",
            "-id3v2_version",
            "3",
            # "-metadata:s:v",
            # "title=Album cover",
            "-metadata:s:v",
            "comment=Cover (front)",
            "temp.mp3",
        ],
        shell=False,
    )
    assert ret == 0

    ret = subprocess.call(
        ["mv", "temp.mp3", filepath],
        shell=False,
    )
    assert ret == 0


def read_cover_image(filepath: str) -> bytes | None:
    audio_file = eyed3.load(filepath)

    try:
        return cast(bytes, audio_file.tag.images.get("Cover (front)").image_data)
    except Exception:
        pass  # not an issue

    images = list(audio_file.tag.images)
    if images:
        return cast(bytes, images[0].image_data)
    else:
        return None


def read_metadata(filepath: str) -> dict[str, Any]:
    audio_file = eyed3.load(filepath)

    metadata = {}
    if audio_file.tag.title:
        metadata["title"] = audio_file.tag.title
    if audio_file.tag.album:
        metadata["album"] = audio_file.tag.album
    if audio_file.tag.artist:
        metadata["performer"] = audio_file.tag.artist

    return metadata
