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


def find_info_json_file_path(mp3_path: Path) -> Path:
    return [
        p
        for p in mp3_path.parent.glob(f"{mp3_path.stem}.*")
        if p.name.endswith(".info.json")
    ][0]


def get_chapter_names_from_info_json_file(info_json_path: Path) -> list[str]:
    found_metadata = json.loads(info_json_path.read_text())
    chapters = found_metadata["chapters"]
    chapters.sort(key=lambda c: c["start_time"])
    return [c["title"] for c in chapters]


def set_metadata_from_info_file(
    mp3_path: Path, info_json_path: Path, title: str | None = None
) -> None:
    found_metadata = json.loads(info_json_path.read_text())

    if title is None:
        title = found_metadata["title"]

    mp3_utils.change_metadata(mp3_path, "title", title)
    if "album" in found_metadata:
        mp3_utils.change_metadata(mp3_path, "album", found_metadata["album"])


def get_thumbnail_path_for_mp3(mp3_path: Path) -> Path | None:
    thumbnails = [
        p
        for p in mp3_path.parent.glob(f"{mp3_path.stem}.*")
        if not p.name.endswith(".info.json") and not p.name.endswith(".mp3")
    ]

    if len(thumbnails) == 0:
        get_default_logger().info(f"No thumbnails found for {mp3_path}")
        return None

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

    for thumbnail_filepath in thumbnails:
        if thumbnail_filepath != thumbnail:
            os.remove(thumbnail_filepath)

    return thumbnail


def ytdl_download_song(url: str, split_chapters: bool) -> list[Path]:
    output_filepath = cache_path_for_mp3_url(url)

    get_default_logger().info(
        f"Downloading youtube audio from url: {url} with filename {output_filepath}"
    )

    output_filepath_str = output_filepath.as_posix()

    split_chapters_args = [
        "--split-chapters",
        "--output",
        f"chapter:{output_filepath_str}.%(section_number)s.chapter.mp3",
    ]

    run_command(
        [
            "yt-dlp",
            "-f",
            "bestaudio/best",
            "--extract-audio",
            "--write-thumbnail",
            "--write-info-json",
            "--no-write-comments",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "0",
            "--output",
            output_filepath_str,
            *(split_chapters_args if split_chapters else []),
            url,
        ],
    )

    assert output_filepath.exists()
    get_default_logger().info(f"Audio from url {url} downloaded")

    info_json_file = find_info_json_file_path(output_filepath)
    thumbnail_image_file = get_thumbnail_path_for_mp3(output_filepath)

    if not split_chapters:
        if thumbnail_image_file is not None:
            mp3_utils.set_cover(output_filepath, thumbnail_image_file)
        set_metadata_from_info_file(output_filepath, info_json_file)
        results = [output_filepath]
    else:
        results = []
        chapter_titles = get_chapter_names_from_info_json_file(info_json_file)
        for chapter_idx, chapter_title in enumerate(chapter_titles, start=1):
            filename = Path(output_filepath_str + f".{chapter_idx}.chapter.mp3")
            if thumbnail_image_file is not None:
                mp3_utils.set_cover(filename, thumbnail_image_file)
            set_metadata_from_info_file(filename, info_json_file, title=chapter_title)
            results.append(filename)

    info_json_file.unlink()
    if thumbnail_image_file is not None:
        thumbnail_image_file.unlink()

    return results


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
        ["yt-dlp", "--skip-download", "--flat-playlist", playlist_url, "-j"],
        allow_errors=True,
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
