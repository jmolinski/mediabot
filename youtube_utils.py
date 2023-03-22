from __future__ import annotations

import json
import os

from pathlib import Path

import mp3_utils

from image_utils import (
    DESIRED_THUMBNAIL_FORMAT,
    convert_image_to_format,
    crop_image_to_square,
)
from settings import get_default_logger, get_settings
from utils import run_command


def set_metadata_from_info_file(mp3_filepath: Path) -> None:
    info_json_filepath = mp3_filepath.with_name(mp3_filepath.name + ".info.json")

    title = json.loads(info_json_filepath.read_text())["title"]

    mp3_utils.change_metadata(mp3_filepath, "title", title)

    info_json_filepath.unlink()


def merge_mp3_with_cover(mp3_path: Path) -> None:
    thumbnails = [
        p
        for p in mp3_path.parent.glob(f"{mp3_path.name}.*")
        if not p.name.endswith(".info.json")
    ]

    assert len(thumbnails) > 0

    if any(
        desired_format_thumbnails := [
            t for t in thumbnails if t.suffix[1:] == DESIRED_THUMBNAIL_FORMAT
        ]
    ):
        thumbnail = desired_format_thumbnails[0]
    else:
        thumbnail = convert_image_to_format(thumbnails[0], DESIRED_THUMBNAIL_FORMAT)
        thumbnails.append(thumbnail)

    assert thumbnail.suffix[1:] == DESIRED_THUMBNAIL_FORMAT

    crop_image_to_square(thumbnail)
    mp3_utils.set_cover(mp3_path, thumbnail)

    for thumbnail_filepath in thumbnails:
        os.remove(thumbnail_filepath)


def download_song(ytid: str) -> Path:
    get_default_logger().info(f"Downloading youtube audio from id: {ytid}")

    output_filepath = get_settings().cache_dir / f"{ytid}.mp3"

    run_command(
        [
            "yt-dlp",
            "-f",
            "bestaudio/best",
            "--extract-audio",
            "--write-thumbnail",
            "--write-info-json",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "0",
            "--output",
            output_filepath.as_posix(),
            "--write-thumbnail",
            f"https://www.youtube.com/watch?v={ytid}",
        ],
    )
    get_default_logger().info(f"Audio from id {ytid} downloaded")

    assert output_filepath.exists()

    merge_mp3_with_cover(output_filepath)
    set_metadata_from_info_file(output_filepath)

    return output_filepath
