from __future__ import annotations

import math

from pathlib import Path
from typing import Any, cast

import eyed3

from utils import generate_random_filename_in_cache, run_command, timestamp_to_seconds


def change_metadata(file: Path, field_name: str, data: str) -> None:
    temp_filename = generate_random_filename_in_cache("mp3")

    run_command(
        [
            "ffmpeg",
            "-i",
            file.as_posix(),
            "-metadata",
            rf"{field_name}={data}",
            "-codec",
            "copy",
            temp_filename.as_posix(),
        ],
    )

    temp_filename.rename(file)


def set_cover(filepath: Path, cover_filepath: Path) -> None:
    # source: https://stackoverflow.com/a/18718265

    temp_filename = generate_random_filename_in_cache("mp3")

    run_command(
        [
            "ffmpeg",
            "-i",
            filepath.as_posix(),
            "-i",
            cover_filepath.as_posix(),
            "-map",
            "0:0",
            "-map",
            "1:0",
            "-c",
            "copy",
            "-id3v2_version",
            "3",
            "-metadata:s:v",
            "title=Album cover",
            "-metadata:s:v",
            "comment=Cover (front)",
            temp_filename.as_posix(),
        ],
    )

    temp_filename.rename(filepath)


def read_cover_image(filepath: Path) -> bytes | None:
    audio_file = eyed3.load(filepath.as_posix())

    try:
        return cast(bytes, audio_file.tag.images.get("Cover (front)").image_data)
    except Exception:
        pass  # not an issue

    images = list(audio_file.tag.images)
    if images:
        return cast(bytes, images[0].image_data)
    else:
        return None


def copy_cover_image(src: Path, dest: Path) -> None:
    image = read_cover_image(src)
    if not image:
        return

    temp_cover_file = generate_random_filename_in_cache(".jpg")
    temp_cover_file.write_bytes(image)
    set_cover(dest, temp_cover_file)
    temp_cover_file.unlink()


def read_metadata(filepath: Path) -> dict[str, Any]:
    audio_file = eyed3.load(filepath.as_posix())

    metadata = {
        "duration": audio_file.info.time_secs,
    }
    if audio_file.tag.title:
        metadata["title"] = audio_file.tag.title
    if audio_file.tag.album:
        metadata["album"] = audio_file.tag.album
    if audio_file.tag.artist:
        metadata["performer"] = audio_file.tag.artist

    return metadata


def cut_audio(
    filepath: Path, start: str | int, end: str | int, overwrite: bool = True
) -> Path:
    start, end = str(start).strip(), str(end).strip()

    start_sec = timestamp_to_seconds(start) if ":" in start else int(start)
    end_sec = timestamp_to_seconds(end) if ":" in end else int(end)

    if start_sec < 0:
        start_sec += math.ceil(read_metadata(filepath)["duration"])
    if end_sec <= 0:
        end_sec += math.ceil(read_metadata(filepath)["duration"])

    duration_s = end_sec - start_sec

    temp_filename = generate_random_filename_in_cache("mp3")

    run_command(
        [
            "ffmpeg",
            "-ss",
            str(start_sec),
            "-t",
            str(duration_s),
            "-i",
            filepath.as_posix(),
            "-acodec",
            "copy",
            temp_filename.as_posix(),
        ],
    )

    copy_cover_image(filepath, temp_filename)

    if overwrite:
        temp_filename.rename(filepath)
        return filepath
    else:
        return temp_filename
