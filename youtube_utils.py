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
from settings import get_default_logger
from utils import cache_path_for_mp3_url, run_command


def set_metadata_from_info_file(mp3_path: Path) -> None:
    info_json_path = [
        p
        for p in mp3_path.parent.glob(f"{mp3_path.stem}.*")
        if p.name.endswith(".info.json")
    ][0]

    found_metadata = json.loads(info_json_path.read_text())

    mp3_utils.change_metadata(mp3_path, "title", found_metadata["title"])
    if "album" in found_metadata:
        mp3_utils.change_metadata(mp3_path, "album", found_metadata["album"])

    info_json_path.unlink()


def merge_mp3_with_cover(mp3_path: Path) -> None:
    thumbnails = [
        p
        for p in mp3_path.parent.glob(f"{mp3_path.stem}.*")
        if not p.name.endswith(".info.json") and not p.name.endswith(".mp3")
    ]

    if len(thumbnails) == 0:
        get_default_logger().info(f"No thumbnails found for {mp3_path}")
        return

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


def ytdl_download_song(url: str) -> Path:
    output_filepath = cache_path_for_mp3_url(url)

    get_default_logger().info(
        f"Downloading youtube audio from url: {url} with filename {output_filepath}"
    )

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
            url,
        ],
    )

    assert output_filepath.exists()
    get_default_logger().info(f"Audio from url {url} downloaded")

    merge_mp3_with_cover(output_filepath)
    set_metadata_from_info_file(output_filepath)

    return output_filepath


def extract_youtube_id(link: str) -> str:
    link = link.strip()

    if "youtu.be" in link:
        return link.split("/")[-1]

    link = link.split("/")[-1].split("?")[-1]
    ids = [
        ytid
        for (argname, ytid) in [x.split("=") for x in link.split("&")]
        if argname == "v"
    ]
    assert len(ids) == 1
    return ids[0]


def playlist_url_to_video_urls(playlist_url: str) -> list[str]:
    p1 = run_command(
        ["yt-dlp", "--skip-download", playlist_url, "-j"], allow_errors=True
    )
    p2 = run_command(["jq", "-r", ".webpage_url"], stdin=p1.stdout)

    # Validate URLs
    possible_links = p2.stdout.decode("utf-8").split("\n")
    links = [
        url
        for url in possible_links
        if url.startswith("https") and "playlist" not in url
    ]
    return links
