from __future__ import annotations

import random
import re
import string
import subprocess
import sys

from pathlib import Path
from typing import Any, TypeVar, cast

from settings import get_default_logger

T = TypeVar("T")

CUSTOM_REACTION_PATTERN = re.compile(r"!(r(eact)?)\s+(.*)")


def split_into_chunks(lst: list[T], n: int) -> list[list[T]]:
    return [lst[i : i + n] for i in range(0, len(lst), n)]


def get_name_from_author_obj(data: dict[Any, Any]) -> str:
    username = data["username"]
    first_name = data["first_name"]
    return cast(str, username or first_name)


def extract_custom_reaction(t: str) -> str | None:
    t = t.strip()
    match = re.match(CUSTOM_REACTION_PATTERN, t)
    if match is None:
        return None

    reaction = match.group(3).strip()
    if not reaction:
        return None

    return reaction


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


def generate_random_filename_in_cache(ext: str = "", length: int = 20) -> Path:
    if ext and not ext.startswith("."):
        ext = "." + ext

    import settings

    while True:
        fname = "".join(
            random.choice(string.ascii_letters + string.digits) for _ in range(length)
        )

        filename = settings.get_settings().cache_dir / (fname + ext)
        if not filename.exists():
            return filename


def run_command(cmd: list[str], expected_code: int = 0) -> subprocess.CompletedProcess:
    get_default_logger().debug(f"Running command: {' '.join(cmd)}")

    ret = subprocess.run(cmd, shell=False, capture_output=True)

    if expected_code != -1 and ret.returncode != expected_code:
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
