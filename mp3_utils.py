from __future__ import annotations

import math
import os

from typing import Any, cast

import eyed3

from utils import generate_random_filename, run_command, timestamp_to_seconds


def change_metadata(filename: str, field_name: str, data: str) -> None:
    temp_filename = generate_random_filename() + ".mp3"

    run_command(
        [
            "ffmpeg",
            "-i",
            filename,
            "-metadata",
            rf"{field_name}={data}",
            "-codec",
            "copy",
            temp_filename,
        ],
    )

    run_command(["mv", temp_filename, filename])


def set_cover(filepath: str, cover_filepath: str) -> None:
    # source: https://stackoverflow.com/a/18718265

    temp_filename = generate_random_filename() + ".mp3"

    run_command(
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
            "-metadata:s:v",
            "title=Album cover",
            "-metadata:s:v",
            "comment=Cover (front)",
            temp_filename,
        ],
    )

    run_command(["mv", temp_filename, filepath])


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


def copy_cover_image(src: str, dest: str) -> None:
    image = read_cover_image(src)
    if not image:
        return

    temp_cover_filename = generate_random_filename() + ".jpg"
    with open(temp_cover_filename, "wb") as f:
        f.write(image)

    set_cover(dest, temp_cover_filename)
    os.remove(temp_cover_filename)


def read_metadata(filepath: str) -> dict[str, Any]:
    audio_file = eyed3.load(filepath)

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
    filepath: str, start: str | int, end: str | int, overwrite: bool = True
) -> str:
    if start == "0":
        start = 0
    if str(end).startswith("-") or end in ("0", 0):
        end = math.ceil(read_metadata(filepath)["duration"]) + int(end)

    start_s = start if isinstance(start, int) else timestamp_to_seconds(start)
    end_s = end if isinstance(end, int) else timestamp_to_seconds(end)
    duration_s = end_s - start_s

    temp_filename = generate_random_filename() + ".mp3"

    run_command(
        [
            "ffmpeg",
            "-ss",
            str(start_s),
            "-t",
            str(duration_s),
            "-i",
            filepath,
            "-acodec",
            "copy",
            temp_filename,
        ],
    )

    copy_cover_image(filepath, temp_filename)

    if overwrite:
        run_command(["mv", temp_filename, filepath])
        return filepath
    else:
        return temp_filename
