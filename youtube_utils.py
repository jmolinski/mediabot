from __future__ import annotations

import os
import subprocess

import mp3_utils

from image_utils import convert_image_to_format, crop_image_to_square
from settings import get_default_logger
from utils import generate_random_filename

DESIRED_THUMBNAIL_FORMAT = "jpg"


def merge_mp3_with_cover(mp3_filepath: str) -> None:
    mp3_basename = os.path.basename(mp3_filepath)
    mp3_dirname = os.path.dirname(mp3_filepath)

    thumbnails = [
        f"{mp3_dirname}/{p}"
        for p in os.listdir(os.path.dirname(mp3_filepath))
        if mp3_basename in p and not p.endswith(".mp3")
    ]
    assert len(thumbnails) > 0

    if any(
        png_thumbnails := [
            t for t in thumbnails if t.endswith(DESIRED_THUMBNAIL_FORMAT)
        ]
    ):
        thumbnail = png_thumbnails[0]
    else:
        thumbnail = convert_image_to_format(thumbnails[0], DESIRED_THUMBNAIL_FORMAT)
        thumbnails.append(thumbnail)

    assert thumbnail.endswith(DESIRED_THUMBNAIL_FORMAT)

    crop_image_to_square(thumbnail)
    mp3_utils.set_cover(mp3_filepath, thumbnail)

    for thumbnail_filepath in thumbnails:
        os.remove(thumbnail_filepath)


def download_song(ytid: str) -> str:
    get_default_logger().info(f"Downloading youtube audio from id: {ytid}")

    output_filepath = rf"media/{generate_random_filename()}.mp3"

    ret = subprocess.call(
        [
            "yt-dlp",
            "-f",
            "bestaudio/best",
            "--extract-audio",
            "--write-thumbnail",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "0",
            "--output",
            output_filepath,
            "--write-thumbnail",
            f"https://www.youtube.com/watch?v={ytid}",
        ],
        shell=False,
    )
    get_default_logger().info(f"Audio from id {ytid} downloaded with return code {ret}")

    assert os.path.exists(output_filepath)

    merge_mp3_with_cover(output_filepath)

    return output_filepath
