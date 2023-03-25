from __future__ import annotations

import hashlib
import os
import random
import string
import subprocess
import sys
import urllib.parse
import urllib.request

from pathlib import Path
from typing import Any, TypeVar, cast

from image_utils import convert_raw_picture_to_thumbnail_format_and_shape
from settings import get_default_logger, get_settings

T = TypeVar("T")


def split_into_chunks(lst: list[T], n: int) -> list[list[T]]:
    return [lst[i : i + n] for i in range(0, len(lst), n)]


def get_name_from_author_obj(data: dict[Any, Any]) -> str:
    username = data["username"]
    first_name = data["first_name"]
    return cast(str, username or first_name)


def generate_random_filename_in_cache(ext: str = "", length: int = 20) -> Path:
    if ext and not ext.startswith("."):
        ext = "." + ext

    tmp_ = "tmp_"
    length -= len(tmp_)
    assert length > 0

    import settings

    while True:
        fname = tmp_ + "".join(
            random.choice(string.ascii_letters + string.digits)
            for _ in range(length - 4)
        )

        filename = settings.get_settings().cache_dir / (fname + ext)
        if not filename.exists():
            return filename


def run_command(
    cmd: list[str],
    expected_code: int = 0,
    allow_errors: bool = False,
    as_shell: bool = False,
    stdin: bytes | None = None,
) -> subprocess.CompletedProcess:
    get_default_logger().debug(f"Running command: {' '.join(cmd)}")

    ret = subprocess.run(cmd, shell=as_shell, capture_output=True, input=stdin)

    if not allow_errors and ret.returncode != expected_code:
        print(ret.stdout)
        print(ret.stderr, file=sys.stderr)

        raise RuntimeError(f"Command {cmd} failed with code {ret.returncode}")

    return ret


def timestamp_to_seconds(timestamp: str) -> int:
    parts = [int(x.lstrip("0") or 0) for x in timestamp.split(":")]
    assert len(parts) in (1, 2, 3)
    parts = parts[::-1]

    seconds = 0
    for i, x in enumerate(parts):
        seconds += x * 60**i

    return seconds


def url_signature(url: str) -> str:
    return hashlib.md5(url.strip().encode()).hexdigest()


def cache_path_for_mp3_url(url: str) -> Path:
    return cache_path_for_url(url, ".mp3")


def cache_path_for_url(url: str, ext: str = "") -> Path:
    url_sig = url_signature(url)
    ext = ext if ext.startswith(".") else "." + ext
    return get_settings().cache_dir / f"{url_sig}{ext}"


def remove_query_parameter_from_url(url: str, parameter: str) -> str:
    # remove a query parameter from the url
    # source: https://stackoverflow.com/a/1208857
    u = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(u.query, keep_blank_values=True)
    query.pop(parameter, None)
    u = u._replace(query=urllib.parse.urlencode(query, True))
    return urllib.parse.urlunparse(u)


def download_url_to_cache(url: str) -> Path:
    assert url.startswith("https")
    output_filepath = cache_path_for_url(url)
    urllib.request.urlretrieve(url, output_filepath)
    return output_filepath


def url_to_thumbnail_filename(picture_url: str) -> Path:
    expected_filename = cache_path_for_url(picture_url)
    if expected_filename.exists():
        return expected_filename

    picture_filename = download_url_to_cache(picture_url)
    thumbnail = convert_raw_picture_to_thumbnail_format_and_shape(picture_filename)
    os.rename(thumbnail, picture_filename)
    assert expected_filename == picture_filename
    return picture_filename
